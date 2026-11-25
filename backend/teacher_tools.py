"""Assistência ao docente com dados observados, sem inferências clínicas nem envio automático."""
import csv
from datetime import date
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .auth import require
from .db import one, rows, session
from .pedagogy import check_subject, performance
from .insights import class_observations

router=APIRouter(prefix='/api/teacher-tools',tags=['Assistente pedagógico'])


def owned_lesson(lesson_id, user):
    lesson=one('''SELECT l.*,c.school_id,c.name class_name
      FROM lesson_schedule l JOIN classes c ON c.id=l.class_id WHERE l.id=?''',(lesson_id,))
    if not lesson:raise HTTPException(404,'Aula não encontrada.')
    check_subject(user,lesson['class_id'],lesson['subject'])
    if user['role']=='prof' and lesson['teacher_id']!=user['id']:
        raise HTTPException(403,'Este planejamento pertence a outro professor.')
    return lesson


@router.get('/lesson/{lesson_id}')
def lesson_assistant(lesson_id:str,user=Depends(require('coord','prof'))):
    lesson=owned_lesson(lesson_id,user)
    observations=class_observations(lesson['class_id'],lesson['subject'],
                                     user['id'] if user['role']=='prof' else '')
    priorities=observations['weak_topics']
    focus=next((x for x in priorities if x['topic']==lesson['topic']),None)
    if not focus: focus=priorities[0] if priorities else None
    topic=focus['topic'] if focus else lesson['topic']
    explanations=[]
    if focus:
        average=f"{focus['mean']:.1f}" if focus['mean'] is not None else 'indisponível'
        explanations.append(f"Resultados em {topic}: média {average}; {focus['below']} estudante(s) abaixo do critério de atenção.")
        explanations.append(focus['reason'])
    else:
        explanations.append('Não há evidência suficiente para afirmar que o tópico seja crítico.')
    available=rows('''SELECT q.id,q.title,q.topic,q.difficulty FROM questions q
       WHERE q.status='published' AND q.rights_status IN ('demo','authorized')
       AND q.discipline=? AND q.correct_letter IN ('A','B','C','D','E')
       AND (q.school_id IS NULL OR q.school_id='' OR q.school_id=?)
       AND (q.creator_id IS NULL OR q.creator_id='' OR q.creator_id=?)
       ORDER BY CASE WHEN q.topic=? THEN 0 ELSE 1 END,q.id LIMIT 5''',
       (lesson['subject'],lesson['school_id'],user['id'],topic))
    steps=[
        {'minutes':5,'title':'Ativação individual', 'activity':f'Uma questão curta sobre {topic}; cada aluno registra sua justificativa.'},
        {'minutes':10,'title':'Retomada no quadro', 'activity':'Compare soluções e explicite o raciocínio necessário, sem expor alunos individualmente.'},
        {'minutes':15,'title':'Prática individual', 'activity':'Duas questões graduais; permita que o aluno corrija o próprio raciocínio com orientação.'},
        {'minutes':5,'title':'Verificação de saída', 'activity':'Uma questão nova com resposta individual para observar a compreensão depois da revisão.'},
    ]
    plan='\n'.join(f"{x['minutes']} min · {x['title']}: {x['activity']}" for x in steps)
    return {'lesson_id':lesson_id,'class_id':lesson['class_id'],'subject':lesson['subject'],
            'class_name':lesson['class_name'],'scheduled_topic':lesson['topic'],'focus_topic':topic,
            'reasons':explanations,'steps':steps,'plan':plan,'question_suggestions':available,
            'note':'Proposta de apoio. O professor deve revisar antes de aplicar; não há formação de grupos.'}


class PlanInput(BaseModel):
    plan:str=Field(min_length=20,max_length=3000)


@router.post('/lesson/{lesson_id}/apply')
def apply_lesson(lesson_id:str,body:PlanInput,user=Depends(require('prof'))):
    lesson=owned_lesson(lesson_id,user)
    with session() as db:
        db.execute('UPDATE lesson_schedule SET plan=? WHERE id=? AND teacher_id=?',
                   (body.plan,lesson_id,user['id']))
    return {'ok':True,'lesson_id':lesson_id,'message':'Plano salvo em Minha semana após confirmação.'}


@router.get('/feedback')
def feedback(class_id:str,subject:str,student_id:str,user=Depends(require('coord','prof'))):
    check_subject(user,class_id,subject)
    student=one('''SELECT u.name FROM users u JOIN enrollments e ON e.user_id=u.id
      WHERE e.class_id=? AND u.id=?''',(class_id,student_id))
    if not student:raise HTTPException(404,'Estudante não matriculado nessa turma.')
    data=performance(class_id,subject)
    student_data=next(s for s in data['students'] if s['id']==student_id)
    heat=next((s['topics'] for s in data['topic_heatmap'] if s['student_id']==student_id),{})
    strengths=sorted(((t,v) for t,v in heat.items() if v>=data['school_threshold']),
                     key=lambda x:-x[1])[:2]
    reviews=sorted(((t,v) for t,v in heat.items() if v<data['school_threshold']),
                   key=lambda x:x[1])[:2]
    text=(f"Olá, {student['name'].split()[0]}! Nas avaliações registradas em {subject}, "
          + (f"você demonstrou bons resultados em {', '.join(x[0] for x in strengths)}. " if strengths else '')
          + (f"Podemos retomar {', '.join(x[0] for x in reviews)} e verificar juntos outras estratégias de resolução. " if reviews else
             'Vamos acompanhar as próximas atividades para identificar os assuntos que precisam de revisão. ')
          + 'O objetivo é compreender melhor os conceitos, não se definir por uma nota. O que você achou mais difícil?')
    return {'student_id':student_id,'student_name':student['name'],'subject':subject,
            'average':student_data['average'],'strengths':[x[0] for x in strengths],
            'review_topics':[x[0] for x in reviews], 'draft':text,
            'status':'rascunho','note':'Nenhuma mensagem é enviada automaticamente. Revise o texto e as evidências antes de compartilhar.'}


@router.get('/report.csv')
def class_report(class_id:str,subject:str,user=Depends(require('coord','prof'))):
    check_subject(user,class_id,subject)
    data=performance(class_id,subject)
    output=StringIO()
    writer=csv.writer(output)
    # Evita execução de fórmulas de CSV/planilha em nomes e tópicos cadastrados.
    def cell(value):
        if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):
            return "'"+value
        return value
    writer.writerow(['Cognix · Relatório pedagógico',date.today().isoformat(),cell(subject)])
    writer.writerow(['Critério de atenção',data['school_threshold']])
    writer.writerow(['Tópico','Média observada','Estudantes abaixo do critério','Variação'])
    for t in data['topics']:
        writer.writerow([cell(t['topic']),t['stats']['mean'],t['below'],t['trend']])
    writer.writerow([])
    writer.writerow(['Aluno(a)','Média parcial','Acompanhamento'])
    alerts={x['student_id'] for x in data['falls']}
    for s in data['students']:
        writer.writerow([cell(s['name']),s['average'],
                         'Queda recente' if s['id'] in alerts else
                         'Atenção à média' if s['average'] is not None and s['average']<data['school_threshold'] else ''])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="cognix-relatorio-{class_id}.csv"',
        'Cache-Control':'no-store'})
