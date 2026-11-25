"""Evidências pedagógicas observadas em avaliações discretas, sem extrapolação temporal.

As notas são uma fonte de evidência, não uma medida da capacidade do estudante.
Toda seleção é limitada no servidor às atribuições e à escola autenticada.
"""
from collections import defaultdict
from datetime import date
from statistics import mean
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .auth import require
from .access import assert_school
from .db import rows, one, session
from .pedagogy import calc, check_subject, school_limits

router=APIRouter(prefix='/api/pedagogy',tags=['Evidências de aprendizagem'])
PERIODS={'avaliacao','semana','quinzena','mes','bimestre','semestre'}
LEVELS={'nao_observado','em_desenvolvimento','com_apoio','autonomia','transferencia'}
COMPETENCIES={'conceito','aplicacao','autonomia','transferencia','erros'}


def combinations(user,school,class_id=''):
    if not school:raise HTTPException(422,'Selecione uma escola.')
    assert_school(user,school)
    if user['role']=='prof':
        out=rows('''SELECT DISTINCT a.class_id,a.subject,c.name class_name,c.grade
             FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
             WHERE a.teacher_id=? AND c.school_id=? ORDER BY c.name,a.subject''',
             (user['id'],school))
    else:
        out=rows('''SELECT DISTINCT a.class_id,a.subject,c.name class_name,c.grade
             FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
             JOIN coordinator_schools cs ON cs.school_id=c.school_id
             WHERE cs.user_id=? AND c.school_id=? ORDER BY c.name,a.subject''',
             (user['id'],school))
    if class_id:
        if not any(x['class_id']==class_id for x in out):
            raise HTTPException(403,'Turma não vinculada à sua instituição ou atribuição.')
        out=[x for x in out if x['class_id']==class_id]
    return out


def period_key(raw,assessment,kind):
    """Sem data, a observação só participa do agrupamento por avaliação."""
    if kind=='avaliacao':return (raw or 'Sem data')+' · '+assessment
    try:d=date.fromisoformat(raw)
    except (TypeError,ValueError):return None
    if kind=='semana':
        iso=d.isocalendar()
        return f'{iso.year}-S{iso.week:02d}'
    if kind=='quinzena':return f'{d.year}-{d.month:02d} · '+('1ª quinzena' if d.day<=15 else '2ª quinzena')
    if kind=='mes':return f'{d.year}-{d.month:02d}'
    if kind=='bimestre':return f'{d.year} · {((d.month-1)//2)+1}º bimestre'
    return f'{d.year} · {((d.month-1)//6)+1}º semestre'


@router.get('/evidence')
def evidence(school:str,class_id:str='',topic:str='',period:str='avaliacao',
             user=Depends(require('coord','prof'))):
    if period not in PERIODS:raise HTTPException(422,'Período de agrupamento inválido.')
    combos=combinations(user,school,class_id)
    available_topics=set()
    raw=[]
    for combo in combos:
        for item in rows('''SELECT g.student_id,g.assessment,g.topic,g.score,a.scheduled_on
            FROM grade_topics g JOIN assessments a
            ON a.class_id=g.class_id AND a.subject=g.subject AND a.name=g.assessment
            JOIN enrollments e ON e.class_id=g.class_id AND e.user_id=g.student_id
            WHERE g.class_id=? AND g.subject=?''',(combo['class_id'],combo['subject'])):
            key=combo['subject']+'::'+item['topic']
            available_topics.add((key,combo['subject'],item['topic']))
            raw.append({**item,'subject':combo['subject'],'class_id':combo['class_id'],
                        'topic_key':key})
    topic_options=[{'key':key,'subject':subject,'topic':name}
                   for key,subject,name in sorted(available_topics)]
    if topic and topic not in {x['key'] for x in topic_options}:
        raise HTTPException(422,'Tópico indisponível nessa turma ou instituição.')
    scoped=[x for x in raw if not topic or x['topic_key']==topic]
    grouped=defaultdict(list)
    evidence_by_topic=defaultdict(list)
    period_by_topic=defaultdict(lambda:defaultdict(list))
    for x in scoped:
        evidence_by_topic[x['topic_key']].append(x)
        label=period_key(x['scheduled_on'],x['assessment'],period)
        if label is not None:
            grouped[label].append(x)
            period_by_topic[x['topic_key']][label].append(x['score'])
    timeline=[{'period':k,'mean':round(mean(y['score'] for y in v),2),
               'count':len(v),'students':len({y['student_id'] for y in v}),
               'min':min(y['score'] for y in v),'max':max(y['score'] for y in v)}
              for k,v in sorted(grouped.items())]
    period_distributions=[{'assessment':k,'stats':calc([y['score'] for y in v])}
                          for k,v in sorted(grouped.items())]
    topics=[]
    for key,values in evidence_by_topic.items():
        by_event=defaultdict(list)
        for x in values:
            by_event[(x['scheduled_on'] or '',x['assessment'])].append(x['score'])
        points=[mean(v) for _,v in sorted(by_event.items())]
        variation=round(points[-1]-points[0],2) if len(points)>1 else None
        # A média de referência pode variar entre instituições; não é uma meta
        # universal de aprendizagem nem substitui as evidências qualitativas.
        first_class=next(x['class_id'] for x in values)
        reference,_=school_limits(first_class)
        weak=sum(v<reference for v in points)
        status=('Evidências insuficientes' if len(points)<2 else
                'Dificuldade persistente' if weak>=2 else
                'Evolução observada' if variation is not None and variation>=1 else
                'Oscilação entre avaliações' if len(points)>2 and max(points)-min(points)>=2 else
                'Acompanhamento contínuo')
        subject,name=key.split('::',1)
        topics.append(dict(key=key,subject=subject,topic=name,mean=round(mean(x['score'] for x in values),2),
            count=len(values),students=len({x['student_id'] for x in values}),
            assessments=len(by_event),trend=variation,weak_periods=weak,
            classification=status))
    topics.sort(key=lambda x:(0 if x['classification']=='Dificuldade persistente' else 1,
                              x['mean'],x['topic']))
    heatmap=[{'key':x['key'],'topic':x['topic'],'subject':x['subject'],
              'periods':{t['period']:round(mean(period_by_topic[x['key']][t['period']]),2)
                         if period_by_topic[x['key']].get(t['period']) else None
                         for t in timeline[-8:]}}
             for x in topics[:10]]
    practices=[]
    for x in combos:
        practices.extend(rows('''SELECT a.id,a.correct,q.topic,q.discipline
           FROM attempts a JOIN questions q ON q.id=a.question_id
           JOIN enrollments e ON e.user_id=a.user_id AND e.class_id=?
           WHERE a.school_id=? AND q.discipline=?
             AND (q.school_id IS NULL OR q.school_id='' OR q.school_id=?)''',
           (x['class_id'],school,x['subject'],school)))
    unique_practice={x['id']:x for x in practices}
    practice_stats=defaultdict(lambda:{'attempts':0,'misses':0})
    for x in unique_practice.values():
        key=x['discipline']+'::'+x['topic']
        if topic and topic!=key:continue
        practice_stats[key]['attempts']+=1
        practice_stats[key]['misses']+=0 if x['correct'] else 1
    activity=[dict(key=k,**v) for k,v in sorted(practice_stats.items(),key=lambda x:-x[1]['misses'])]
    # Provas criadas e vinculadas às avaliações: evidências complementares.
    # Só são incluídas as provas do próprio docente, ou as da escola administrada.
    exam_topics=[]
    applied_exams=[]
    for combo in combos:
        teacher_filter=' AND ex.creator_id=?' if user['role']=='prof' else ''
        args=[combo['class_id'],combo['subject']]
        if user['role']=='prof':args.append(user['id'])
        exam_topics.extend(rows('''SELECT q.topic,COUNT(*) quantity
            FROM exam_sets ex JOIN exam_items ei ON ei.exam_id=ex.id
            JOIN questions q ON q.id=ei.question_id
            WHERE ex.class_id=? AND ex.subject=?'''+teacher_filter+
            ' GROUP BY q.topic ORDER BY quantity DESC',args))
        applied_exams.extend(rows('''SELECT ex.applied_assessment assessment,
            AVG(g.score) grade_mean, COUNT(DISTINCT g.student_id) students
            FROM exam_sets ex JOIN grades g ON g.class_id=ex.class_id
             AND g.subject=ex.subject AND g.assessment=ex.applied_assessment
            WHERE ex.class_id=? AND ex.subject=? AND ex.applied_assessment!='' '''+
            teacher_filter+' GROUP BY ex.applied_assessment',args))
    observations=[]
    interventions=[]
    for x in combos:
        observations.extend(rows('''SELECT o.id,o.subject,o.topic,o.competency,o.evidence_level,
               o.observed_on,o.note,u.name student_name
           FROM competency_observations o JOIN users u ON u.id=o.student_id
           WHERE o.class_id=? AND o.subject=? ORDER BY o.observed_on DESC LIMIT 80''',
           (x['class_id'],x['subject'])))
        interventions.extend(rows('''SELECT id,subject,topic,activity,applied_on,notes
           FROM pedagogical_interventions WHERE class_id=? AND subject=?
           ORDER BY applied_on DESC LIMIT 40''',(x['class_id'],x['subject'])))
    if topic:
        observations=[o for o in observations if o['subject']+'::'+o['topic']==topic]
        interventions=[i for i in interventions if i['subject']+'::'+i['topic']==topic]
    effects=[]
    for intervention in interventions:
        subset=[x for x in scoped if x['subject']==intervention['subject']
                and x['topic']==intervention['topic'] and x['scheduled_on']]
        before=[x['score'] for x in subset if x['scheduled_on']<intervention['applied_on']]
        after=[x['score'] for x in subset if x['scheduled_on']>intervention['applied_on']]
        effects.append({**intervention,'before':round(mean(before),2) if before else None,
                        'after':round(mean(after),2) if after else None,
                        'status':'Comparação descritiva, não demonstra causalidade' if len(before)>=3 and len(after)>=3
                        else 'Dados insuficientes para comparar antes e depois'})
    all_scores=[x['score'] for x in scoped]
    summary_stats=calc(all_scores)
    unique_students=len({x['student_id'] for x in scoped})
    student_topic=defaultdict(lambda:defaultdict(list))
    for x in scoped:student_topic[x['student_id']][x['topic_key']].append(x['score'])
    student_ids=list(student_topic)
    names={}
    if student_ids:
        placeholders=','.join('?' for _ in student_ids)
        names={x['id']:x['name'] for x in rows('SELECT id,name FROM users WHERE id IN ('+placeholders+')',student_ids)}
    student_heatmap=[]
    for student_id,by_topic in student_topic.items():
        values=[v for scores in by_topic.values() for v in scores]
        student_heatmap.append({'name':names.get(student_id,'Estudante'),
            'average':round(mean(values),2),
            'topics':{key:round(mean(scores),2) for key,scores in by_topic.items()}})
    student_heatmap.sort(key=lambda x:(x['average'],x['name']))
    return {'school_id':school,'class_id':class_id,'topic':topic,'period':period,
       'school_threshold':school_limits(combos[0]['class_id'])[0] if combos else None,
       'classes':list({x['class_id']:dict(id=x['class_id'],name=x['class_name'],grade=x['grade'])
                       for x in combos}.values()),'topic_options':topic_options,
       'statistics':summary_stats,'student_count':unique_students,'observations_count':len(scoped),
       'topics':topics,'timeline':timeline,'period_heatmap':heatmap,
       'period_distributions':period_distributions,'student_heatmap':student_heatmap,
       'scores':all_scores,'practice':activity,
       'exam_patterns':exam_topics[:30],'applied_exam_results':applied_exams[:30],
       'qualitative':observations[:60],'interventions':effects[:40],
       'warning':('Sem registros para o período escolhido: os intervalos não são preenchidos artificialmente.'
                  if not timeline else
                  'Indicadores de avaliação e prática são evidências, não um índice de capacidade do aluno.'),
       'basis':{'assessments':len({(x['class_id'],x['subject'],x['assessment']) for x in scoped}),
                'dated':sum(bool(x['scheduled_on']) for x in scoped),
                'unstructured':len(observations)}}


def _validate_scope(user,school,class_id,subject,topic):
    combos=combinations(user,school,class_id)
    if not any(x['subject']==subject for x in combos):
        raise HTTPException(403,'Disciplina não autorizada para esta turma.')
    check_subject(user,class_id,subject)
    if not topic.strip():raise HTTPException(422,'Informe o tópico observado.')


class CompetencyObservation(BaseModel):
    school_id:str
    class_id:str
    subject:str
    student_id:str
    topic:str=Field(min_length=2,max_length=120)
    competency:str
    evidence_level:str
    observed_on:str
    note:str=Field('',max_length=800)


@router.post('/evidence/observations')
def add_observation(body:CompetencyObservation,user=Depends(require('coord','prof'))):
    _validate_scope(user,body.school_id,body.class_id,body.subject,body.topic)
    if body.competency not in COMPETENCIES or body.evidence_level not in LEVELS:
        raise HTTPException(422,'Competência ou classificação não reconhecida.')
    try:date.fromisoformat(body.observed_on)
    except ValueError:raise HTTPException(422,'Data inválida.')
    if not one('SELECT 1 FROM enrollments WHERE class_id=? AND user_id=?',
               (body.class_id,body.student_id)):
        raise HTTPException(403,'Aluno não matriculado na turma.')
    id=secrets.token_hex(12)
    with session() as db:
        db.execute('''INSERT INTO competency_observations
            (id,school_id,class_id,subject,student_id,observer_id,topic,competency,evidence_level,observed_on,note)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            (id,body.school_id,body.class_id,body.subject,body.student_id,user['id'],
             body.topic.strip(),body.competency,body.evidence_level,body.observed_on,body.note))
    return {'ok':True,'id':id}


class Intervention(BaseModel):
    school_id:str
    class_id:str
    subject:str
    topic:str=Field(min_length=2,max_length=120)
    activity:str=Field(min_length=5,max_length=500)
    applied_on:str
    notes:str=Field('',max_length=800)


@router.post('/evidence/interventions')
def add_intervention(body:Intervention,user=Depends(require('coord','prof'))):
    _validate_scope(user,body.school_id,body.class_id,body.subject,body.topic)
    try:date.fromisoformat(body.applied_on)
    except ValueError:raise HTTPException(422,'Data inválida.')
    id=secrets.token_hex(12)
    with session() as db:
        db.execute('''INSERT INTO pedagogical_interventions
            (id,school_id,class_id,subject,topic,creator_id,activity,applied_on,notes)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (id,body.school_id,body.class_id,body.subject,body.topic,user['id'],
             body.activity.strip(),body.applied_on,body.notes))
    return {'ok':True,'id':id}
