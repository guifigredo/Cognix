"""Experiência personalizada nativa do aluno: boletim, metas, revisão e questionário vocacional ilustrativo."""
from collections import defaultdict
import math, json, secrets, statistics
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from .auth import require
from .access import assert_school, subjects_for
from .db import rows,one,session
from .pedagogy import performance
router=APIRouter(prefix='/api/student',tags=['Aluno'])

class Goal(BaseModel):
    school_id:str
    topic:str=Field(min_length=2,max_length=90)
    target:int=Field(5,ge=1,le=200)
class Preferences(BaseModel):
    school_id:str
    values:list[str]|None=None
    subjects:list[str]|None=None
    activities:list[str]|None=None
    environments:list[str]|None=None
    hours:int|None=Field(None,ge=1,le=40)
    problem:str|None=Field(None,max_length=400)
    performance_weight:int|None=Field(None,ge=0,le=100)
    objective:str|None=None
    focus_topics:list[str]|None=None
    study_days:list[str]|None=None
    study_style:str|None=None
    feedback:dict|None=None
class CourseFeedback(BaseModel):
    school_id:str
    course_id:str
    choice:str
class Reason(BaseModel):
    reason:str=Field('',max_length=100)

VALUES=['Ajudar pessoas','Criatividade','Estabilidade','Trabalhar com tecnologia',
        'Pesquisa e descoberta','Liderar equipes','Contato com a natureza','Justiça social']
ACTIVITIES=['Resolver problemas com cálculos','Programar e lidar com tecnologia',
 'Fazer experimentos','Entender o corpo humano','Natureza e meio ambiente',
 'Ler, escrever e argumentar','Entender a sociedade e a política',
 'Cuidar e ajudar pessoas','Criar e comunicar ideias','Mapas, cidades e território']
ENVIRONMENTS=['Escritório','Laboratório','Hospital ou clínica','Ao ar livre',
 'Sala de aula','Trabalho remoto','Indústria ou obra']
OBJECTIVES={'Ainda não sei':{},'Medicina e saúde':{'Natureza':1.6,'Exatas':1.1},
 'Engenharias e exatas':{'Exatas':1.6,'Natureza':1.3},
 'Direito e humanas':{'Humanas':1.6,'Linguagens':1.4},
 'Comunicação e letras':{'Linguagens':1.6,'Humanas':1.2}}
STUDY_DAYS=['Seg','Ter','Qua','Qui','Sex','Sáb']
STUDY_STYLES={'misto':'Teoria e questões','questoes':'Mais questões','guiada':'Revisão guiada'}
COURSES=[
 ('eng','Engenharias',['Matemática','Física'],['Resolver problemas com cálculos','Programar e lidar com tecnologia','Fazer experimentos'],['Trabalhar com tecnologia','Liderar equipes'],['Indústria ou obra','Escritório'],'Cálculo, física, materiais e projetos.','Indústria, energia, infraestrutura e projetos.'),
 ('comp','Computação e ciência de dados',['Matemática'],['Programar e lidar com tecnologia','Resolver problemas com cálculos'],['Trabalhar com tecnologia','Criatividade','Pesquisa e descoberta'],['Trabalho remoto','Escritório'],'Programação, algoritmos, estatística e bancos de dados.','Software, ciência de dados, pesquisa e empreendedorismo.'),
 ('fisest','Física e Estatística',['Matemática','Física'],['Resolver problemas com cálculos','Fazer experimentos'],['Pesquisa e descoberta','Trabalhar com tecnologia'],['Laboratório','Sala de aula'],'Física experimental, probabilidade e modelagem.','Pesquisa, ensino, análise de dados e institutos de estatística.'),
 ('saude','Medicina e Saúde',['Biologia','Química'],['Entender o corpo humano','Cuidar e ajudar pessoas','Fazer experimentos'],['Ajudar pessoas','Pesquisa e descoberta'],['Hospital ou clínica','Laboratório'],'Anatomia, fisiologia, bioquímica e prática clínica.','Medicina, enfermagem, nutrição, farmácia e saúde pública.'),
 ('bio','Ciências Biológicas e Ambientais',['Biologia','Química','Geografia'],['Natureza e meio ambiente','Fazer experimentos'],['Contato com a natureza','Pesquisa e descoberta'],['Ao ar livre','Laboratório'],'Genética, ecologia, botânica e meio ambiente.','Pesquisa, conservação, biotecnologia e gestão ambiental.'),
 ('quim','Química e Farmácia',['Química','Biologia'],['Fazer experimentos','Resolver problemas com cálculos'],['Pesquisa e descoberta','Estabilidade'],['Laboratório','Indústria ou obra'],'Química orgânica, análise e processos industriais.','Indústria, controle de qualidade e farmácia.'),
 ('dir','Direito',['Linguagens','Geografia','História'],['Ler, escrever e argumentar','Entender a sociedade e a política'],['Justiça social','Liderar equipes'],['Escritório'],'Direito constitucional, civil, penal e filosofia.','Advocacia, serviço público, mediação e consultoria.'),
 ('letras','Letras e Comunicação',['Linguagens','Português'],['Ler, escrever e argumentar','Criar e comunicar ideias'],['Criatividade','Justiça social'],['Sala de aula','Trabalho remoto'],'Linguística, literatura, redação e comunicação.','Jornalismo, ensino, edição, tradução e publicidade.'),
 ('geo','Geografia, Arquitetura e Urbanismo',['Geografia','Matemática'],['Mapas, cidades e território','Natureza e meio ambiente','Criar e comunicar ideias'],['Criatividade','Contato com a natureza'],['Escritório','Ao ar livre'],'Cartografia, planejamento urbano, desenho e geoprocessamento.','Urbanismo, arquitetura, cartografia e projetos.')]

def area_of(subject):
    n=subject.casefold()
    if 'matem' in n or 'estat' in n:return 'Exatas'
    if any(x in n for x in ('fís','fisica','quím','quimica','biolog','ciências da natureza')):return 'Natureza'
    if any(x in n for x in ('histór','historia','geograf','sociolog','filosof','human')):return 'Humanas'
    return 'Linguagens'

def profile_from(pref):
    feedback=json.loads(pref['feedback_json']) if pref else {}
    if not isinstance(feedback,dict):feedback={}
    return {'values':json.loads(pref['values_json']) if pref else [],
      'hours':pref['hours'] if pref else 4,
      'subjects':feedback.get('subjects',[]),'activities':feedback.get('activities',[]),
      'environments':feedback.get('environments',[]),'problem':feedback.get('problem',''),
      'performance_weight':feedback.get('performance_weight',20),
      'objective':feedback.get('objective','Ainda não sei'),
      'focus_topics':feedback.get('focus_topics',[]),
      'study_days':feedback.get('study_days',['Seg','Ter','Qua','Qui','Sex']),
      'study_style':feedback.get('study_style','misto'),
      'career_feedback':feedback.get('careers',{}),'feedback':feedback}

def owned_school(user,school):
    if not school: raise HTTPException(422,'Escolha sua escola.')
    assert_school(user,school)
    return school

def personal(user,school):
    owned_school(user,school)
    configured=one('SELECT settings_json FROM school_configuration WHERE school_id=?',(school,))
    try: grade_target=float(json.loads(configured['settings_json']).get('mediaAprov',6)) if configured else 6.0
    except (ValueError,TypeError,KeyError): grade_target=6.0
    classes=rows('''SELECT c.id,c.name,c.grade FROM classes c JOIN enrollments e ON e.class_id=c.id
      WHERE e.user_id=? AND c.school_id=? ORDER BY c.grade,c.name''',(user['id'],school))
    grades=[];curriculum=[];topics=defaultdict(lambda: {'grades':[],'practice':[]})
    for c in classes:
        subs=rows('SELECT DISTINCT subject FROM teaching_assignments WHERE class_id=? ORDER BY subject',(c['id'],))
        for sub in subs:
            report=performance(c['id'],sub['subject'])
            person=next((x for x in report['students'] if x['id']==user['id']),None)
            if not person:continue
            avs=report['assessments']
            scored=[(a,person['grades'][a['name']]) for a in avs if person['grades'].get(a['name']) is not None]
            pending=[a for a in avs if person['grades'].get(a['name']) is None]
            weighted=sum(v*a['weight'] for a,v in scored)
            total=sum(a['weight'] for a in avs)
            future=sum(a['weight'] for a in pending)
            minimum=(grade_target*total-weighted)/future if future>0 else None
            needed=('Já atingiu a média' if minimum is not None and minimum<=0 else
                    'Meta inalcançável apenas com as avaliações pendentes' if minimum is not None and minimum>10 else None)
            grade={'class_id':c['id'],'class_name':c['name'],'grade':c['grade'],
                   'school_id':school,'subject':sub['subject'],'average':person['average'],
                   'assessments':[dict(name=a['name'],weight=a['weight'],date=a['scheduled_on'],
                           topics=a['topics'],score=person['grades'].get(a['name'])) for a in avs],
                   'needed':round(max(0,minimum),2) if minimum is not None else None,
                   'needed_message':needed,'remaining':len(pending)}
            grades.append(grade)
            curriculum.append({'class_id':c['id'],'subject':sub['subject'],'class_name':c['name']})
    gt=rows('''SELECT g.topic,g.subject,g.score FROM grade_topics g JOIN classes c ON c.id=g.class_id
      JOIN enrollments e ON e.class_id=g.class_id AND e.user_id=g.student_id
      WHERE g.student_id=? AND c.school_id=?''',(user['id'],school))
    for r in gt:topics[(r['subject'],r['topic'])]['grades'].append(r['score'])
    pract=rows('''SELECT a.id,a.correct,a.reason,a.created_at,q.topic,q.discipline,q.difficulty
       FROM attempts a JOIN questions q ON q.id=a.question_id
       WHERE a.user_id=? AND a.school_id=?
       ORDER BY a.created_at DESC LIMIT 400''',(user['id'],school))
    for p in pract:
        if p['discipline'] in subjects_for(user,school):
            topics[(p['discipline'],p['topic'])]['practice'].append(p)
    goals=rows('SELECT topic,target FROM student_goals WHERE student_id=? AND school_id=?',(user['id'],school))
    goal_map={x['topic']:x['target'] for x in goals}
    topic_metrics=[]
    for (sub,topic),v in topics.items():
        g=v['grades'];p=v['practice'];acc=round(100*sum(x['correct'] for x in p)/len(p),1) if p else None
        avg=round(statistics.mean(g),2) if g else None
        # Prioridade calculada de notas e respostas; sem alegar predição de aprovação.
        gap=max(0,grade_target-(avg if avg is not None else grade_target))
        low_acc=(100-acc)/100 if acc is not None else 0
        priority=round(gap+2*low_acc,2)
        topic_metrics.append({'subject':sub,'topic':topic,'average':avg,'accuracy':acc,
           'answers':len(p),'misses':sum(not x['correct'] for x in p),
           'priority_score':priority,'goal':goal_map.get(topic,5)})
    topic_metrics.sort(key=lambda x:(-x['priority_score'],x['topic']))
    pref=one('SELECT * FROM student_preferences WHERE student_id=? AND school_id=?',(user['id'],school))
    preferences=profile_from(pref)
    # Histórico longitudinal real do banco fictício, por estudante e escola.
    # Os rótulos da 9ª, 1ª e 2ª séries são os mesmos do HTML original.
    authorized=set(subjects_for(user,school))
    mappings=rows('SELECT DISTINCT discipline,topic FROM questions WHERE topic != ""')
    by_topic={x['topic']:x['discipline'] for x in mappings if x['discipline'] in authorized}
    for sub,topic in topics.keys():
        if sub in authorized:by_topic[topic]=sub
    past=rows('''SELECT grade_label,topic,score FROM topic_history_scoped
                  WHERE school_id=? AND student_id=?''',(school,user['id']))
    longitudinal={}
    for h in past:
        sub=by_topic.get(h['topic'])
        if not sub:continue
        key=(sub,h['topic'])
        longitudinal.setdefault(key,{})[h['grade_label']]=h['score']
    for (sub,topic),v in topics.items():
        if v['grades'] and sub in authorized:
            longitudinal.setdefault((sub,topic),{})['Atual']=round(statistics.mean(v['grades']),2)
    years=['9º ano','1ª série','2ª série','Atual']
    history=[]
    for (sub,topic),values in longitudinal.items():
        samples=[(i,values.get(y)) for i,y in enumerate(years) if values.get(y) is not None]
        if not samples:continue
        domain=sum(v*(i+1) for i,v in samples)/sum(i+1 for i,v in samples)
        trend=samples[-1][1]-samples[0][1] if len(samples)>1 else None
        priority='alta' if domain<5.5 or (trend is not None and trend<=-1.5) else 'média' if domain<7 else 'baixa'
        history.append({'subject':sub,'topic':topic,'years':{y:values.get(y) for y in years},
          'domain':round(domain,2),'trend':round(trend,2) if trend is not None else None,'priority':priority})
    history.sort(key=lambda x:({'alta':0,'média':1,'baixa':2}[x['priority']],x['domain']))
    history_map={(x['subject'],x['topic']):x for x in history}
    weighted=OBJECTIVES.get(preferences['objective'],{})
    for metric in topic_metrics:
        h=history_map.get((metric['subject'],metric['topic']))
        why=[]
        if metric['average'] is not None and metric['average']<grade_target:
            why.append(f"Notas de avaliações no tópico: média {metric['average']:.1f}")
        if metric['answers']>=2 and metric['accuracy'] is not None and metric['accuracy']<65:
            why.append(f"Prática: {metric['misses']} erro(s) em {metric['answers']} respostas")
        if h and h['trend'] is not None and h['trend']<=-1:
            why.append(f"Variação do histórico: {h['trend']:+.1f} pontos")
        if not why:
            why.append('Poucas evidências ou resultados que merecem acompanhamento; não define capacidade')
        if metric['topic'] in preferences['focus_topics']:
            why.append('Você selecionou este conteúdo como foco pessoal de estudo')
        area=area_of(metric['subject'])
        weight=weighted.get(area,1)
        metric.update(area=area,reasons=why,history_priority=h['priority'] if h else None,
            evidence_count=metric['answers']+(1 if metric['average'] is not None else 0),
            objective_weight=weight,
            personalized_priority=round((metric['priority_score']+(.7 if h and h['priority']=='alta' else 0)+
                (1.4 if metric['topic'] in preferences['focus_topics'] else 0))*weight,2))
    topic_metrics.sort(key=lambda x:(-x['personalized_priority'],x['topic']))
    grouped=defaultdict(list)
    for item in grades:
        if item['average'] is not None:
            grouped[area_of(item['subject'])].append(item['average'])
    area_averages=[{'area':area,'average':round(statistics.mean(grouped[area]),2) if grouped[area] else None,
                    'subjects':len(grouped[area])} for area in ('Exatas','Natureza','Humanas','Linguagens')]
    practice_count=len(pract); practice_hits=sum(x['correct'] for x in pract)
    return {'school_id':school,'longitudinal':history,'history_years':years,'classes':classes,'curriculum':curriculum,
       'grades':grades,'topics':topic_metrics,'goals':goals,'preferences':preferences,
       'areas':area_averages,'objectives':list(OBJECTIVES),
       'practice':{'n':practice_count,'correct':practice_hits,
                   'accuracy':round(100*practice_hits/practice_count,1) if practice_count else None,
                   'recent':[r for r in pract[:20] if r['discipline'] in subjects_for(user,school)]},
       'study_plan':study_plan(topic_metrics,preferences['hours']),
       'demo_note':'Notas e histórico originais fictícios; recomendações heurísticas para demonstração.'}

def study_plan(metrics,hours):
    priority=metrics[:4]
    if not priority:return []
    splits=[max(15,round((hours*60)/max(1,len(priority))/5)*5) for _ in priority]
    return [{'week':i+1,'topic':t['topic'],'subject':t['subject'],
             'minutes':splits[i],'area':t.get('area',''),
             'reason':'; '.join(t.get('reasons',[])),
             'task':'Rever teoria, resolver questões do banco e registrar dúvidas e estratégias'}
            for i,t in enumerate(priority)]

@router.get('/dashboard')
def dashboard(school:str,user=Depends(require('aluno'))):
    return personal(user,school)

@router.get('/schedule')
def student_schedule(school:str,user=Depends(require('aluno'))):
    owned_school(user,school)
    lessons=rows('''SELECT c.id class_id,c.name class_name,l.subject,l.weekday,l.slot,l.room,
      l.topic,l.plan,l.status FROM lesson_schedule l
      JOIN classes c ON c.id=l.class_id
      JOIN enrollments e ON e.class_id=c.id
      WHERE e.user_id=? AND c.school_id=? ORDER BY l.weekday,l.slot''',(user['id'],school))
    evaluations=rows('''SELECT c.name class_name,a.subject,a.name,a.scheduled_on,a.weight
      FROM assessments a JOIN classes c ON c.id=a.class_id
      JOIN enrollments e ON e.class_id=c.id
      WHERE e.user_id=? AND c.school_id=? ORDER BY a.scheduled_on,a.name''',(user['id'],school))
    return {'lessons':lessons,'assessments':evaluations}

@router.post('/goals')
def goals(body:Goal,user=Depends(require('aluno'))):
    owned_school(user,body.school_id)
    with session() as db:db.execute('''INSERT INTO student_goals(student_id,school_id,topic,target)
        VALUES(?,?,?,?) ON CONFLICT(student_id,school_id,topic) DO UPDATE SET target=excluded.target''',
        (user['id'],body.school_id,body.topic.strip(),body.target))
    return {'ok':True}

@router.post('/preferences')
def preferences(body:Preferences,user=Depends(require('aluno'))):
    owned_school(user,body.school_id)
    old=one('SELECT * FROM student_preferences WHERE student_id=? AND school_id=?',(user['id'],body.school_id))
    previous=profile_from(old)
    chosen=list(dict.fromkeys(x for x in (body.values if body.values is not None else previous['values']) if x in VALUES))
    updated=dict(previous['feedback'])
    for key,selection,allowed in (
      ('subjects',body.subjects,set(subjects_for(user,body.school_id))),
      ('activities',body.activities,set(ACTIVITIES)),
      ('environments',body.environments,set(ENVIRONMENTS))):
        if selection is not None:
            updated[key]=list(dict.fromkeys(x for x in selection if x in allowed))[:25]
    if body.problem is not None:updated['problem']=body.problem.strip()
    if body.performance_weight is not None:updated['performance_weight']=body.performance_weight
    if body.objective is not None:
        if body.objective not in OBJECTIVES:raise HTTPException(422,'Objetivo de estudo inválido.')
        updated['objective']=body.objective
    if body.focus_topics is not None:
        updated['focus_topics']=list(dict.fromkeys(x.strip() for x in body.focus_topics
            if isinstance(x,str) and 1<len(x.strip())<=120))[:3]
    if body.study_days is not None:
        updated['study_days']=[day for day in STUDY_DAYS if day in body.study_days]
    if body.study_style is not None:
        if body.study_style not in STUDY_STYLES:raise HTTPException(422,'Modo de estudo inválido.')
        updated['study_style']=body.study_style
    if body.feedback is not None:
        updated.update({k:v for k,v in body.feedback.items() if k not in
                        {'subjects','activities','environments','careers','objective','performance_weight',
                         'problem','focus_topics','study_days','study_style'}})
    hours=body.hours if body.hours is not None else previous['hours']
    with session() as db:db.execute('''INSERT INTO student_preferences(student_id,school_id,values_json,hours,feedback_json)
        VALUES(?,?,?,?,?) ON CONFLICT(student_id,school_id) DO UPDATE SET values_json=excluded.values_json,
        hours=excluded.hours,feedback_json=excluded.feedback_json''',
        (user['id'],body.school_id,json.dumps(chosen,ensure_ascii=False),hours,
         json.dumps(updated,ensure_ascii=False)))
    return {'ok':True,'values':chosen,'hours':hours,'profile':updated}

@router.get('/vocational')
def vocational(school:str,user=Depends(require('aluno'))):
    data=personal(user,school)
    profile=data['preferences']
    subject_grades={x['subject']:x['average'] for x in data['grades'] if x['average'] is not None}
    general=statistics.mean(subject_grades.values()) if subject_grades else None
    available=set(x['subject'] for x in data['grades'])
    weight=profile['performance_weight']/100
    careers=[]
    for cid,name,subjects,activities,values,environments,graduation,work in COURSES:
        liked_subjects=[x for x in subjects if x in profile['subjects']]
        liked_activities=[x for x in activities if x in profile['activities']]
        liked_values=[x for x in values if x in profile['values']]
        liked_places=[x for x in environments if x in profile['environments']]
        related=[subject_grades[x] for x in subjects if x in subject_grades]
        avg=statistics.mean(related) if related else None
        taste=min(1,len(liked_subjects)*.22+len(liked_activities)*.21+
                    len(liked_values)*.18+len(liked_places)*.12)
        # Nenhum dado de nota produz equivalência entre desempenho e aptidão.
        performance=0.5 if avg is None or general is None else max(0,min(1,(avg-general+2)/4))
        score=round(100*(taste*(1-weight)+performance*weight))
        reasons=[]
        if liked_subjects:reasons.append('Você gosta de '+', '.join(liked_subjects))
        if liked_activities:reasons.append('Você demonstrou curiosidade em '+', '.join(liked_activities))
        if liked_values:reasons.append('Você valoriza '+', '.join(liked_values))
        if liked_places:reasons.append('Você prefere ambientes como '+', '.join(liked_places))
        if avg is not None:reasons.append(f'As médias nas disciplinas relacionadas somam uma evidência de estudo ({avg:.1f}); não definem aptidão')
        if not reasons:reasons=['Explore esta carreira e registre seus interesses para personalizar as sugestões']
        practice=[x for x in data['topics'] if x['subject'] in subjects][:3]
        careers.append({'id':cid,'name':name,'subjects':subjects,'graduation':graduation,
            'work':work,'score':score,'taste_score':round(taste*100),
            'performance_score':round(performance*100),
            'reasons':reasons,'feedback':profile['career_feedback'].get(cid,''),
            'preparation':practice})
    order={'sim':0,'mais':1,'':2,'nao':3}
    careers.sort(key=lambda x:(order.get(x['feedback'],2),-x['score'],x['name']))
    marked=[x for x in careers if x['feedback'] in ('sim','mais')]
    suggested_topics=[]
    used=set()
    for career in marked:
        for topic in career['preparation']:
            key=(topic['subject'],topic['topic'])
            if key not in used:
                used.add(key)
                suggested_topics.append({'subject':topic['subject'],'topic':topic['topic'],
                     'career':career['name'],'reasons':topic['reasons']})
    return {'values':VALUES,'activities':ACTIVITIES,'environments':ENVIRONMENTS,
        'subjects':sorted(available),'profile':profile,'courses':careers,
        'study_topics':suggested_topics[:8],
        'message':'Exploração orientativa de interesses, não teste vocacional validado nem indicação de aptidão.'}

@router.post('/vocational/feedback')
def career_feedback(body:CourseFeedback,user=Depends(require('aluno'))):
    owned_school(user,body.school_id)
    if body.course_id not in {x[0] for x in COURSES} or body.choice not in {'sim','mais','nao',''}:
        raise HTTPException(422,'Carreira ou resposta inválida.')
    current=one('SELECT * FROM student_preferences WHERE student_id=? AND school_id=?',(user['id'],body.school_id))
    profile=profile_from(current)
    feedback=dict(profile['feedback'])
    choices=dict(feedback.get('careers',{}))
    if body.choice:choices[body.course_id]=body.choice
    else:choices.pop(body.course_id,None)
    feedback['careers']=choices
    with session() as db:
        db.execute('''INSERT INTO student_preferences(student_id,school_id,values_json,hours,feedback_json)
            VALUES(?,?,?,?,?) ON CONFLICT(student_id,school_id) DO UPDATE SET feedback_json=excluded.feedback_json''',
            (user['id'],body.school_id,json.dumps(profile['values'],ensure_ascii=False),
             profile['hours'],json.dumps(feedback,ensure_ascii=False)))
    return {'ok':True,'feedback':choices}

@router.post('/practice/reason/{attempt_id}')
def save_reason(attempt_id:str,body:Reason,user=Depends(require('aluno'))):
    valid=['Não sabia o conteúdo','Erro de cálculo','Interpretação do enunciado','Falta de atenção','Tempo','']
    if body.reason not in valid:raise HTTPException(422,'Motivo não reconhecido.')
    with session() as db:
        cur=db.execute('UPDATE attempts SET reason=? WHERE id=? AND user_id=? AND correct=0',
                       (body.reason,attempt_id,user['id']))
        if not cur.rowcount:raise HTTPException(404,'Erro de prática não encontrado.')
    return {'ok':True}

@router.get('/practice/queue')
def practice_queue(school:str,topic:str='',limit:int=Query(8,ge=1,le=25),user=Depends(require('aluno'))):
    owned_school(user,school)
    allowed=subjects_for(user,school)
    if not allowed:return {'items':[],'topic':topic}
    query='SELECT id,source,discipline,topic,difficulty,title,context,prompt,alternatives_json,media_json FROM questions WHERE status="published" AND rights_status IN ("authorized","demo") AND creator_id IS NULL AND (school_id IS NULL OR school_id=?) AND correct_letter!="" AND discipline IN ('+','.join('?'*len(allowed))+')'
    args=[school]+list(allowed)
    if topic:
        query+=' AND topic=?';args.append(topic)
    # Reduz repetições e mescla a ordem, de forma determinística por tentativa.
    query+=' ORDER BY RANDOM() LIMIT ?';args.append(limit)
    data=rows(query,args)
    for r in data:
        r['alternatives']=json.loads(r.pop('alternatives_json'))
        r['media']=json.loads(r.pop('media_json'))
    return {'items':data,'topic':topic}
