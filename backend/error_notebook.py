"""Caderno de erros a partir das respostas efetivamente registradas no Cognix.

Alternativas incorretas são observações; causas só são exibidas quando
explicitamente anotadas por um educador autorizado da instituição.
"""
from collections import defaultdict, Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import require
from .db import rows, one, session
from .pedagogy import check_subject

router=APIRouter(prefix='/api/teacher-tools',tags=['Caderno de erros'])


@router.get('/error-notebook')
def notebook(class_id:str,subject:str,topic:str='',user=Depends(require('coord','prof'))):
    school=check_subject(user,class_id,subject)['school_id']
    answers=rows('''SELECT a.id,a.question_id,a.chosen_letter,a.correct,q.title,q.topic,
          q.correct_letter,q.prompt,a.user_id
      FROM attempts a JOIN enrollments e ON e.user_id=a.user_id
      JOIN questions q ON q.id=a.question_id JOIN classes c ON c.id=e.class_id
      WHERE e.class_id=? AND a.school_id=c.school_id AND q.discipline=?
        AND (q.school_id IS NULL OR q.school_id='' OR q.school_id=c.school_id)
        AND (q.creator_id IS NULL OR q.creator_id='')
        AND (?='' OR q.topic=?)
      ORDER BY a.created_at DESC''',(class_id,subject,topic,topic))
    tags=rows('SELECT question_id,letter,description FROM question_error_tags WHERE school_id=?',(school,))
    explanations={(t['question_id'],t['letter']):t['description'] for t in tags}
    by_question=defaultdict(list)
    for ans in answers:by_question[ans['question_id']].append(ans)
    items=[]
    for question_id,events in by_question.items():
        first=events[0];choice_counts=Counter(x['chosen_letter'] for x in events)
        misses=sum(not x['correct'] for x in events)
        items.append({'question_id':question_id,'title':first['title'] or first['prompt'][:110],
          'topic':first['topic'] or 'Não classificado','correct_letter':first['correct_letter'],
          'attempts':len(events),'students':len({x['user_id'] for x in events}),
          'misses':misses,'accuracy':round(100*(len(events)-misses)/len(events),1),
          'choices':dict(choice_counts),
          'hypotheses':{letter:explanations.get((question_id,letter),'')
                        for letter in choice_counts if letter!=first['correct_letter']}})
    items.sort(key=lambda x:(-x['misses'],x['accuracy'],x['title']))
    by_topic=defaultdict(lambda:{'attempts':0,'misses':0})
    for item in items:
        by_topic[item['topic']]['attempts']+=item['attempts']
        by_topic[item['topic']]['misses']+=item['misses']
    topics=[{'topic':topic,**v,'accuracy':round(100*(v['attempts']-v['misses'])/v['attempts'],1)}
            for topic,v in by_topic.items()]
    return {'class_id':class_id,'subject':subject,'topic':topic,'attempts':len(answers),
       'students':len({x['user_id'] for x in answers}),'questions':items[:60],
       'topics':sorted(topics,key=lambda x:x['accuracy']),
       'note':'Cada tentativa conta como resposta; um estudante pode responder várias vezes. As hipóteses são registradas pelo professor e não comprovam a causa do erro.'}


class Misconception(BaseModel):
    letter:str=Field(min_length=1,max_length=1)
    description:str=Field(min_length=5,max_length=220)


@router.post('/error-notebook/{question_id}/hypothesis')
def annotate(question_id:str,class_id:str,subject:str,body:Misconception,
             user=Depends(require('coord','prof'))):
    school=check_subject(user,class_id,subject)['school_id']
    q=one('''SELECT id,correct_letter,discipline FROM questions WHERE id=?
            AND (creator_id IS NULL OR creator_id='')
            AND (school_id IS NULL OR school_id='' OR school_id=?)''',(question_id,school))
    if not q or q['discipline']!=subject:
        raise HTTPException(404,'Questão não encontrada na disciplina.')
    # Não permite anotar uma questão fora do universo das tentativas desta turma.
    if not one('''SELECT 1 FROM attempts a JOIN enrollments e ON e.user_id=a.user_id
      WHERE e.class_id=? AND a.school_id=? AND a.question_id=?''',(class_id,school,question_id)):
        raise HTTPException(404,'Questão sem respostas nesta turma.')
    letter=body.letter.strip().upper()
    if letter not in 'ABCDE' or letter==q['correct_letter']:
        raise HTTPException(422,'Selecione uma alternativa incorreta A, B, C, D ou E.')
    with session() as db:
        db.execute('''INSERT INTO question_error_tags
          (school_id,question_id,letter,description,author_id) VALUES(?,?,?,?,?)
          ON CONFLICT(school_id,question_id,letter) DO UPDATE SET
          description=excluded.description,author_id=excluded.author_id,updated_at=CURRENT_TIMESTAMP''',
          (school,question_id,letter,body.description.strip(),user['id']))
    return {'ok':True}
