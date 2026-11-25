"""Análise pedagógica compartilhada: notas, dispersão, diagnóstico e trilha longitudinal.
Sem leitura de dados de outras escolas; estatísticas sobre demonstração não são previsões clínicas.
"""
from collections import Counter, defaultdict
import math, statistics, json
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import secrets
from .auth import current_user, require
from .access import assert_class, assert_school, assert_subject, allowed_schools, subjects_for
from .db import rows, one, session

router=APIRouter(prefix='/api/pedagogy', tags=['Pedagogia'])

def check_subject(user,cls,subject):
    c=assert_class(user,cls)
    if user['role']=='prof' and not one('SELECT 1 FROM teaching_assignments WHERE teacher_id=? AND class_id=? AND subject=?', (user['id'],cls,subject)):
        raise HTTPException(403,'Você não leciona esta disciplina nesta turma.')
    if user['role']=='coord' and not one('SELECT 1 FROM assessments WHERE class_id=? AND subject=? UNION SELECT 1 FROM teaching_assignments WHERE class_id=? AND subject=? LIMIT 1',(cls,subject,cls,subject)):
        raise HTTPException(404,'Disciplina não cadastrada na turma.')
    if user['role']=='aluno' and not one('SELECT 1 FROM enrollments e JOIN teaching_assignments a ON a.class_id=e.class_id WHERE e.user_id=? AND e.class_id=? AND a.subject=?',(user['id'],cls,subject)):
        raise HTTPException(403,'Disciplina fora da matrícula.')
    return c

def calc(values):
    a=[float(x) for x in values if x is not None and math.isfinite(float(x))]
    n=len(a)
    if not n: return {'n':0,'mean':None,'median':None,'mode':None,'variance':None,'sd':None,'dm':None,'cv':None,'min':None,'max':None,'amplitude':None,'q1':None,'q3':None,'iqr':None,'skew':None}
    a.sort(); mu=statistics.mean(a)
    # Interpolação linear: mesmo critério do HTML de origem.
    def quantile(p):
        idx=(n-1)*p;lo=math.floor(idx);hi=math.ceil(idx)
        return a[lo]+(a[hi]-a[lo])*(idx-lo)
    variance=sum((x-mu)**2 for x in a)/(n-1) if n>=2 else None
    sd=math.sqrt(variance) if variance is not None else None
    freq=Counter(round(x*2)/2 for x in a)
    most=max(freq.values()); mode=min(k for k,v in freq.items() if v==most)
    skew=(n/((n-1)*(n-2))*sum(((x-mu)/sd)**3 for x in a)) if n>2 and sd and sd>0 else None
    q1,q3=quantile(.25),quantile(.75)
    return dict(n=n,mean=round(mu,4),median=statistics.median(a),mode=mode,
                variance=round(variance,4) if variance is not None else None,
                sd=round(sd,4) if sd is not None else None,
                dm=round(sum(abs(x-mu) for x in a)/n,4),
                cv=round(100*sd/mu,3) if sd is not None and mu else None,
                min=min(a),max=max(a),amplitude=max(a)-min(a),q1=q1,q3=q3,iqr=q3-q1,
                skew=round(skew,4) if skew is not None else None)

def school_limits(class_id):
    """Usa os parâmetros da instituição, não uma média mínima fixa."""
    conf=one('''SELECT sc.settings_json FROM classes c LEFT JOIN school_configuration sc
      ON sc.school_id=c.school_id WHERE c.id=?''',(class_id,))
    try: settings=json.loads(conf['settings_json'] or '{}') if conf else {}
    except (ValueError,TypeError): settings={}
    try:
        approval=float(settings.get('mediaAprov',6))
        recovery=float(settings.get('mediaRec',4))
        if not (math.isfinite(approval) and math.isfinite(recovery)
                and 0 <= recovery <= approval <= 10):
            raise ValueError('Configuração de média inválida.')
        return approval,recovery
    except (ValueError,TypeError):
        return 6.0,4.0

def performance(cls,subject):
    threshold,recovery=school_limits(cls)
    assessments=rows('SELECT id,name,weight,scheduled_on,topics_json FROM assessments WHERE class_id=? AND subject=? ORDER BY CASE WHEN scheduled_on="" THEN 1 ELSE 0 END,scheduled_on,name',(cls,subject))
    for a in assessments:
        try:a['topics']=json.loads(a.pop('topics_json'))
        except Exception:a['topics']=[]
    grades=rows('SELECT student_id,assessment,score FROM grades WHERE class_id=? AND subject=?',(cls,subject))
    students=rows('''SELECT u.id,u.name FROM users u JOIN enrollments e ON e.user_id=u.id WHERE e.class_id=? ORDER BY u.name''',(cls,))
    weights={a['name']:a['weight'] for a in assessments}
    lookup={(g['student_id'],g['assessment']):g['score'] for g in grades}
    grades_by_student={}
    averages=[]
    for s in students:
        available={a['name']:lookup.get((s['id'],a['name'])) for a in assessments}
        num=sum(v*weights.get(k,1) for k,v in available.items() if v is not None)
        den=sum(weights.get(k,1) for k,v in available.items() if v is not None)
        avg=round(num/den,4) if den>0 else None
        grades_by_student[s['id']]=available
        s['average']=avg
        s['grades']=available
        if avg is not None:averages.append(avg)
    metrics=calc(averages)
    evolution=[dict(assessment=a['name'],date=a['scheduled_on'],stats=calc([lookup.get((s['id'],a['name'])) for s in students])) for a in assessments]
    topics=rows('''SELECT g.topic,g.student_id,g.assessment,g.score FROM grade_topics g
          JOIN enrollments e ON e.class_id=g.class_id AND e.user_id=g.student_id
          JOIN assessments a ON a.class_id=g.class_id AND a.subject=g.subject
                 AND a.name=g.assessment
          WHERE g.class_id=? AND g.subject=?''',(cls,subject))
    topic_scores=defaultdict(lambda:defaultdict(list)); topic_series=defaultdict(lambda:defaultdict(list))
    for item in topics:
        topic_scores[item['topic']][item['student_id']].append(item['score'])
        topic_series[item['topic']][item['assessment']].append(item['score'])
    top=[]
    for topic,by_st in topic_scores.items():
        student_averages=[statistics.mean(v) for v in by_st.values() if v]
        descriptors=calc(student_averages)
        series=[{'assessment':a['name'],'mean':round(statistics.mean(topic_series[topic][a['name']]),3)}
                for a in assessments if topic_series[topic][a['name']]]
        trend=round(series[-1]['mean']-series[0]['mean'],3) if len(series)>1 else None
        top.append(dict(topic=topic,stats=descriptors,below=sum(x<threshold for x in student_averages),
             pct_below=round(100*sum(x<threshold for x in student_averages)/len(student_averages),1),
             trend=trend,series=series))
    top.sort(key=lambda t:t['stats']['mean'] if t['stats']['mean'] is not None else 99)
    # Mapa de calor aluno × tópico: médias efetivamente registradas em grade_topics.
    # Só é exposto pelas rotas de professor/coordenação após check_subject().
    topic_heatmap=[{'student_id':s['id'],'name':s['name'],
        'topics':{topic:round(statistics.mean(by_student[s['id']]),2)
                  for topic,by_student in topic_scores.items() if by_student.get(s['id'])}}
        for s in students]
    # alerta de queda ≥2,5 pontos em comparação com as avaliações anteriores com nota
    falls=[]
    for s in students:
        previous=[]
        for a in assessments:
            val=s['grades'].get(a['name'])
            if val is None:continue
            if previous:
                delta=statistics.mean(previous)-val
                if delta>=2.5:
                    falls.append(dict(student_id=s['id'],student_name=s['name'],assessment=a['name'],
                                      previous=round(statistics.mean(previous),2),current=val,drop=round(delta,2)))
            previous.append(val)
    falls.sort(key=lambda x:-x['drop'])
    return dict(assessments=assessments,students=students,stats=metrics,
                evolution=evolution,topics=top,topic_heatmap=topic_heatmap,falls=falls,
                school_threshold=threshold,school_recovery=recovery,
                status='demo' if any(a['id'].startswith('legacy-') for a in assessments) else 'live')

@router.get('/matrix')
def matrix(class_id:str,subject:str,user=Depends(require('coord','prof'))):
    cls=check_subject(user,class_id,subject)
    r=performance(class_id,subject)
    return dict(class_id=class_id,subject=subject,school_id=cls['school_id'],**r)

@router.get('/analysis')
def analysis(class_id:str,subject:str,user=Depends(require('coord','prof'))):
    cls=check_subject(user,class_id,subject)
    data=performance(class_id,subject)
    weak=[t for t in data['topics'] if t['stats']['mean'] is not None and t['stats']['mean']<data['school_threshold']]
    attention=[]
    if weak:
        p=weak[0];attention.append(f"Retomar {p['topic']}: média {p['stats']['mean']:.1f} e {p['pct_below']:.0f}% abaixo de {data['school_threshold']:.1f}.")
    if data['stats']['cv'] is not None and data['stats']['cv']>30:
        attention.append('Dispersão elevada (CV acima de 30%): propor atividades diferenciadas por nível.')
    if data['falls']:
        attention.append(f"Conversar individualmente com {len(data['falls'])} aluno(s) após queda de pelo menos 2,5 pontos.")
    if not attention:attention=['Desempenho sem alertas automáticos graves nas avaliações registradas.']
    schedule=rows('''SELECT id,weekday,slot,room,topic,plan,status,notes FROM lesson_schedule WHERE class_id=? AND subject=? ORDER BY weekday,slot''',(class_id,subject))
    for a in schedule:
        if a['topic'] in {w['topic'] for w in weak}:
            a['suggestion']='Conteúdo crítico: diagnóstico curto de pré-requisitos e lista progressiva de exercícios.'
        else:a['suggestion']='Manter plano e reservar 10 minutos para revisão do tópico de menor média.' if weak else 'Ampliar desafios e revisar dúvidas.'
    return dict(class_id=class_id,subject=subject,school_id=cls['school_id'],
                recommendations=attention,schedule=schedule,**data)

@router.get('/institution')
def institution(school:str,user=Depends(require('coord'))):
    assert_school(user,school)
    assignments=rows('''SELECT DISTINCT a.class_id,a.subject,c.name class_name,u.name teacher_name FROM teaching_assignments a
        JOIN classes c ON c.id=a.class_id JOIN users u ON u.id=a.teacher_id
        WHERE c.school_id=? ORDER BY c.name,a.subject''',(school,))
    unique={(x['class_id'],x['subject']):x for x in assignments}
    summaries=[]; attention=[]
    for (cls,sub),r in unique.items():
        data=performance(cls,sub)
        vals=[x['average'] for x in data['students'] if x['average'] is not None]
        summaries.append({**r,'average':data['stats']['mean'],'student_count':len(data['students']),
          'approved_pct':round(100*sum(v>=data['school_threshold'] for v in vals)/len(vals),1) if vals else None,
          'school_threshold':data['school_threshold'],
          'falls':len(data['falls']),'critical':sum(x['stats']['mean']<data['school_threshold'] for x in data['topics'])})
        attention.extend([dict(**f,class_name=r['class_name'],subject=sub) for f in data['falls']])
    from .insights import teacher_attention
    attention_view=teacher_attention(list(unique.values()))
    return dict(school_id=school,classes=len({r['class_id'] for r in unique.values()}),
        enrollments=one('''SELECT COUNT(DISTINCT e.user_id) n FROM enrollments e JOIN classes c ON c.id=e.class_id WHERE c.school_id=?''',(school,))['n'],
        subjects=summaries,alerts=attention[:25],
        students_to_follow=attention_view['students_to_follow'][:50],
        critical_topics=attention_view['critical_topics'][:50])

@router.get('/trail')
def trail(class_id:str,subject:str,student_id:str,user=Depends(current_user)):
    cls=check_subject(user,class_id,subject)
    if not (one('SELECT grade FROM classes WHERE id=?',(class_id,)) or {}).get('grade','').startswith('3ª'):
        raise HTTPException(403,'A Trilha ENEM é exclusiva da 3ª série do Ensino Médio.')
    if user['role']=='aluno' and student_id!=user['id']:
        raise HTTPException(403,'Histórico individual indisponível.')
    if not one('SELECT 1 FROM enrollments WHERE user_id=? AND class_id=?',(student_id,class_id)):
        raise HTTPException(404,'Aluno não matriculado nessa turma.')
    hist=rows('''SELECT grade_label,topic,score FROM topic_history_scoped
                   WHERE student_id=? AND school_id=?''',(student_id,cls['school_id']))
    current=rows('''SELECT topic,AVG(score) mean FROM grade_topics WHERE student_id=? AND class_id=? AND subject=? GROUP BY topic''',
       (student_id,class_id,subject))
    # Restringe o histórico à matéria avaliada: evita expor outras áreas no painel do professor.
    canonical=set(x['topic'] for x in rows('SELECT DISTINCT topic FROM grade_topics WHERE class_id=? AND subject=?',(class_id,subject)))
    canonical.update(x['topic'] for x in current)
    all_data=defaultdict(dict)
    for h in hist:
        if h['topic'] in canonical:all_data[h['topic']][h['grade_label']]=h['score']
    for c in current:all_data[c['topic']]['Atual']=round(c['mean'],2)
    sequence=['9º ano','1ª série','2ª série','Atual']
    result=[]
    for topic,years in all_data.items():
        vals=[years.get(y) for y in sequence]
        seen=[(i,v) for i,v in enumerate(vals) if v is not None]
        priority=sum(v*(i+1) for i,v in seen)/sum(i+1 for i,v in seen) if seen else None
        trend=seen[-1][1]-seen[0][1] if len(seen)>1 else None
        urgency='alta' if priority is not None and (priority<5.5 or (trend is not None and trend<=-1.5)) else 'média' if priority is not None and priority<7 else 'baixa'
        result.append({'topic':topic,'series':dict(zip(sequence,vals)),'domain':round(priority,2) if priority is not None else None,
                       'trend':round(trend,2) if trend is not None else None,'priority':urgency})
    result.sort(key=lambda x:(['alta','média','baixa'].index(x['priority']),x['domain'] or 99))
    return {'student_id':student_id,'subject':subject,'school_id':cls['school_id'],
            'years':sequence,'topics':result,'origin':'Histórico fictício original; notas atuais do SQLite'}

@router.get('/trail-overview')
def trail_overview(class_id:str,subject:str,user=Depends(require('coord','prof'))):
    cls=check_subject(user,class_id,subject)
    if not (one('SELECT grade FROM classes WHERE id=?',(class_id,)) or {}).get('grade','').startswith('3ª'):
        raise HTTPException(403,'A Trilha ENEM é exclusiva da 3ª série do Ensino Médio.')
    students=performance(class_id,subject)['students']
    aggregate=defaultdict(lambda:defaultdict(list))
    priorities=defaultdict(list)
    for student in students:
        record=trail(class_id,subject,student['id'],user)
        for topic in record['topics']:
            for year,value in topic['series'].items():
                if value is not None:aggregate[topic['topic']][year].append(value)
            if topic['domain'] is not None:priorities[topic['topic']].append(topic['domain'])
    years=['9º ano','1ª série','2ª série','Atual']
    topics=[]
    for name,by_year in aggregate.items():
        series={year:round(statistics.mean(by_year[year]),2) if by_year[year] else None for year in years}
        vals=[(i,v) for i,v in enumerate(series.values()) if v is not None]
        domain=round(statistics.mean(priorities[name]),2) if priorities[name] else None
        trend=round(vals[-1][1]-vals[0][1],2) if len(vals)>1 else None
        urgency='alta' if domain is not None and (domain<5.5 or trend is not None and trend<=-1.5) else 'média' if domain is not None and domain<7 else 'baixa'
        topics.append(dict(topic=name,series=series,domain=domain,trend=trend,
                           priority=urgency,students=len(priorities[name])))
    topics.sort(key=lambda x:(['alta','média','baixa'].index(x['priority']),x['domain'] if x['domain'] is not None else 99))
    return dict(class_id=class_id,school_id=cls['school_id'],subject=subject,
                student_count=len(students),years=years,topics=topics,
                origin='Médias agregadas do histórico longitudinal e notas atuais; dados demonstrativos.')

# Agenda e avaliação persistidas no mesmo banco que alimenta os painéis.
class LessonUpdate(BaseModel):
    topic:str=Field(min_length=2,max_length=120)
    plan:str=Field('',max_length=3000)
    status:str='planejada'
    notes:str=Field('',max_length=3000)
class LessonCreate(LessonUpdate):
    class_id:str
    subject:str
    weekday:int=Field(ge=0,le=4)
    slot:int=Field(ge=0,le=15)
    room:str=Field('',max_length=80)
class AssessmentInput(BaseModel):
    class_id:str
    subject:str
    name:str=Field(min_length=2,max_length=80)
    weight:float=Field(1,gt=0,le=100)
    scheduled_on:str=''
    topics:list[str]=Field(default_factory=list,max_length=25)
class SettingsInput(BaseModel):
    school_id:str
    mediaAprov:float=Field(6,ge=0,le=10)
    mediaRec:float=Field(4,ge=0,le=10)
    anoLetivo:int=Field(2026,ge=2020,le=2100)

@router.get('/schedule')
def schedule(school:str='',user=Depends(require('coord','prof'))):
    if school:assert_school(user,school)
    if user['role']=='coord':
        where='''JOIN coordinator_schools z ON z.school_id=c.school_id WHERE z.user_id=?'''
        vals=[user['id']]
    else:
        where='''JOIN teaching_assignments x ON x.class_id=a.class_id AND x.subject=a.subject
                JOIN school_memberships m ON m.user_id=x.teacher_id AND m.school_id=c.school_id AND m.status='active'
                WHERE x.teacher_id=? AND a.teacher_id=?'''
        vals=[user['id'],user['id']]
    if school:where+=' AND c.school_id=?';vals.append(school)
    return rows('''SELECT DISTINCT a.*,c.name class_name,c.school_id,s.name school_name,u.name teacher_name
       FROM lesson_schedule a JOIN classes c ON c.id=a.class_id
       JOIN schools s ON s.id=c.school_id JOIN users u ON u.id=a.teacher_id '''+where+
       ' ORDER BY weekday,slot,c.name',vals)

@router.post('/schedule')
def create_lesson(body:LessonCreate,user=Depends(require('prof'))):
    """Cria atividade persistida, vinculada à atribuição do docente à turma."""
    if body.status not in ('planejada','dada','cancelada'):
        raise HTTPException(422,'Situação inválida.')
    check_subject(user,body.class_id,body.subject)
    if one('''SELECT 1 FROM lesson_schedule WHERE class_id=? AND subject=?
              AND teacher_id=? AND weekday=? AND slot=?''',
           (body.class_id,body.subject,user['id'],body.weekday,body.slot)):
        raise HTTPException(409,'Já existe uma aula desta disciplina e turma nesse horário. Edite o registro existente.')
    lesson_id='lesson-'+secrets.token_hex(10)
    with session() as db:
        db.execute('''INSERT INTO lesson_schedule
          (id,class_id,subject,teacher_id,weekday,slot,room,topic,plan,status,notes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
          (lesson_id,body.class_id,body.subject,user['id'],body.weekday,body.slot,
           body.room,body.topic.strip(),body.plan,body.status,body.notes))
    saved=one('SELECT * FROM lesson_schedule WHERE id=?',(lesson_id,))
    if not saved:raise HTTPException(500,'A atividade não pôde ser confirmada no banco.')
    return {'ok':True,'lesson':saved,'message':'Atividade criada e gravada no cronograma.'}

@router.patch('/schedule/{lesson_id}')
def update_lesson(lesson_id:str,body:LessonUpdate,user=Depends(require('coord','prof'))):
    if body.status not in ('planejada','dada','cancelada'):raise HTTPException(422,'Situação inválida.')
    lesson=one('SELECT * FROM lesson_schedule WHERE id=?',(lesson_id,))
    if not lesson:raise HTTPException(404,'Aula não encontrada.')
    check_subject(user,lesson['class_id'],lesson['subject'])
    if user['role']=='prof' and user['id']!=lesson['teacher_id']:
        raise HTTPException(403,'Somente o docente responsável pela aula pode editar este plano.')
    with session() as db:db.execute('''UPDATE lesson_schedule SET topic=?,plan=?,status=?,notes=? WHERE id=?''',
       (body.topic.strip(),body.plan,body.status,body.notes,lesson_id))
    saved=one('SELECT id,class_id,subject,topic,plan,status,notes FROM lesson_schedule WHERE id=?',(lesson_id,))
    if not saved or saved['topic']!=body.topic.strip() or saved['plan']!=body.plan or saved['status']!=body.status:
        raise HTTPException(500,'A alteração não pôde ser confirmada no banco de dados.')
    return {'ok':True,'lesson':saved,'message':'Planejamento gravado e confirmado no banco.'}

@router.get('/assessments')
def assessments(class_id:str,subject:str,user=Depends(require('coord','prof'))):
    check_subject(user,class_id,subject)
    data=rows('SELECT * FROM assessments WHERE class_id=? AND subject=? ORDER BY scheduled_on,name',(class_id,subject))
    for x in data:
        try:x['topics']=json.loads(x.pop('topics_json'))
        except Exception:x['topics']=[]
    return data

@router.post('/assessments')
def add_assessment(body:AssessmentInput,user=Depends(require('coord'))):
    check_subject(user,body.class_id,body.subject)
    if body.scheduled_on and (len(body.scheduled_on)!=10 or body.scheduled_on[4]!='-' or body.scheduled_on[7]!='-'):
        raise HTTPException(422,'Data inválida.')
    if one('SELECT id FROM assessments WHERE class_id=? AND subject=? AND name=?',
           (body.class_id,body.subject,body.name.strip())):raise HTTPException(409,'Avaliação já cadastrada.')
    with session() as db:db.execute('''INSERT INTO assessments(id,class_id,subject,name,weight,scheduled_on,topics_json,origin)
       VALUES(?,?,?,?,?,?,?,?)''',(secrets.token_hex(12),body.class_id,body.subject,body.name.strip(),body.weight,
         body.scheduled_on,json.dumps(body.topics,ensure_ascii=False),'Cognix'))
    return {'ok':True}

@router.get('/configuration')
def configuration(school:str,user=Depends(require('coord','prof'))):
    assert_school(user,school)
    found=one('SELECT settings_json FROM school_configuration WHERE school_id=?',(school,))
    data=json.loads(found['settings_json']) if found else {}
    return dict(school_id=school,mediaAprov=data.get('mediaAprov',6),mediaRec=data.get('mediaRec',4),
      anoLetivo=data.get('anoLetivo',2026),calendario=data.get('avaliacoes',{}).get('calendario',[]),
      horarios=data.get('avaliacoes',{}).get('horarios',[]))

@router.patch('/configuration')
def update_config(body:SettingsInput,user=Depends(require('coord'))):
    assert_school(user,body.school_id)
    if body.mediaRec>body.mediaAprov:raise HTTPException(422,'Média de recuperação acima da aprovação.')
    saved=one('SELECT settings_json FROM school_configuration WHERE school_id=?',(body.school_id,))
    data=json.loads(saved['settings_json']) if saved else {}
    data.update({'mediaAprov':body.mediaAprov,'mediaRec':body.mediaRec,'anoLetivo':body.anoLetivo})
    with session() as db:db.execute('''INSERT INTO school_configuration(school_id,settings_json)
      VALUES(?,?) ON CONFLICT(school_id) DO UPDATE SET settings_json=excluded.settings_json''',
       (body.school_id,json.dumps(data,ensure_ascii=False)))
    return {'ok':True}

@router.get('/my-classes-summary')
def my_class_summary(school:str='',user=Depends(require('prof'))):
    if school:assert_school(user,school)
    items=rows('''SELECT DISTINCT x.class_id,x.subject,c.name class_name,c.school_id
      FROM teaching_assignments x JOIN classes c ON c.id=x.class_id
      JOIN school_memberships m ON m.user_id=x.teacher_id AND m.school_id=c.school_id AND m.status='active'
      WHERE x.teacher_id=? AND (?='' OR c.school_id=?) ORDER BY c.school_id,c.name,x.subject''',
      (user['id'],school,school))
    result=[]
    for x in items:
        d=performance(x['class_id'],x['subject'])
        result.append(dict(**x,students=len(d['students']),mean=d['stats']['mean'],sd=d['stats']['sd'],
          critical_topics=len([t for t in d['topics'] if t['stats']['mean'] is not None and t['stats']['mean']<d['school_threshold']]),
          falls=len(d['falls'])))
    return result

@router.get('/attention')
def attention(school:str='',user=Depends(require('prof','coord'))):
    from .insights import teacher_attention
    if school:assert_school(user,school)
    if user['role']=='prof':
        assignments=rows('''SELECT DISTINCT a.class_id,a.subject,c.name class_name,c.school_id
           FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
           JOIN school_memberships m ON m.user_id=a.teacher_id AND m.school_id=c.school_id AND m.status='active'
           WHERE a.teacher_id=? AND (?='' OR c.school_id=?)
           ORDER BY c.name,a.subject''',(user['id'],school,school))
    else:
        assignments=rows('''SELECT DISTINCT a.class_id,a.subject,c.name class_name,c.school_id
           FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
           JOIN coordinator_schools cs ON cs.school_id=c.school_id
           WHERE cs.user_id=? AND (?='' OR c.school_id=?)
           ORDER BY c.name,a.subject''',(user['id'],school,school))
    return teacher_attention(assignments,user['id'] if user['role']=='prof' else '')

@router.get('/observations')
def observations(class_id:str,subject:str,user=Depends(require('prof','coord'))):
    from .insights import class_observations
    check_subject(user,class_id,subject)
    return class_observations(class_id,subject,user['id'] if user['role']=='prof' else '')
