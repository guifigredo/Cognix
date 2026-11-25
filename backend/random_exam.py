"""Sorteio personalizável de provas com catálogo central, sem depender do LLM.

A mesma regra pedagógica do protótipo antigo, agora auditada no servidor:
- percentuais de dificuldade;
- tópicos/tipos de questão;
- preferência por tópicos críticos da turma;
- nenhuma duplicação e acesso limitado a vínculo docente/escola;
- item de prova com pontuação individual.
"""
import json
import math
import secrets
import random
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .auth import require
from .db import rows, one, session
from .access import assert_class, assert_subject

router = APIRouter(prefix='/api/exam-builder', tags=['Provas personalizáveis'])
RNG = random.SystemRandom()
DIFS = ('fácil', 'média', 'difícil')
TYPES = ('multipla', 'vf', 'discursiva')

class RandomExamInput(BaseModel):
    class_id: str
    subject: str
    title: str = Field(min_length=3, max_length=120)
    topics: list[str] = Field(default_factory=list, max_length=30)
    types: list[str] = Field(default_factory=lambda: ['multipla', 'vf', 'discursiva'], min_length=1)
    count: int = Field(default=6, ge=2, le=20)
    easy_percent: int = Field(default=40, ge=0, le=100)
    medium_percent: int = Field(default=40, ge=0, le=100)
    hard_percent: int = Field(default=20, ge=0, le=100)
    total_points: float = Field(default=10, gt=0, le=100)
    focus_weak_topics: bool = True
    instructions: str = Field(default='Leia com atenção e justifique quando solicitado.', max_length=1200)


def _access(user, class_id, subject):
    cls = assert_class(user, class_id)
    assert_subject(user, subject, cls['school_id'])
    if user['role'] == 'prof':
        can = one('SELECT 1 FROM teaching_assignments WHERE teacher_id=? AND class_id=? AND subject=?',
                  (user['id'], class_id, subject))
        if not can:
            raise HTTPException(403, 'Esta matéria não está atribuída a você nesta turma.')
    return cls


def _kind(question):
    try:
        length = len(json.loads(question['alternatives_json'] or '[]'))
    except (ValueError, TypeError):
        length = 0
    return 'discursiva' if length < 2 else 'vf' if length == 2 else 'multipla'


def _available(subject, user, school):
    return rows("""SELECT q.id,COALESCE(NULLIF(q.discipline,''),qc.discipline) discipline,
       COALESCE(NULLIF(qc.topic,''),q.topic) topic,
       COALESCE(NULLIF(qc.difficulty,''),q.difficulty) difficulty,
       q.alternatives_json,q.correct_letter,q.source
      FROM questions q LEFT JOIN question_school_classifications qc
      ON qc.question_id=q.id AND qc.school_id=?
      WHERE (q.discipline=? OR qc.discipline=?) AND q.status='published'
        AND q.rights_status IN ('authorized','demo')
        AND (q.school_id IS NULL OR q.school_id=?)
        AND (
          (NOT EXISTS (SELECT 1 FROM question_records r WHERE r.question_id=q.id)
            AND (q.creator_id IS NULL OR q.creator_id=?))
          OR EXISTS (SELECT 1 FROM question_records r JOIN question_collections col ON col.id=r.collection_id
                WHERE r.question_id=q.id AND ((col.kind='personal' AND col.owner_id=?)
                OR (col.kind='school' AND col.school_id=?)))
        ) ORDER BY q.id""",
        (school,subject,subject,school,user['id'],user['id'],school))


def _limits(percents, n):
    # Método de maiores restos: soma sempre n, mesmo com percentuais não exatos.
    p = [max(0, x) for x in percents]
    total = sum(p)
    if total == 0:
        raise HTTPException(422, 'Pelo menos um percentual de dificuldade deve ser maior que zero.')
    targets = [n * x / total for x in p]
    floors = [math.floor(x) for x in targets]
    order = sorted(range(3), key=lambda i: targets[i] - floors[i], reverse=True)
    for i in order[:n - sum(floors)]:
        floors[i] += 1
    return dict(zip(DIFS, floors))


def _weak_topics(class_id, subject):
    school = one('SELECT school_id FROM classes WHERE id=?', (class_id,))
    limit = 6.0
    if school:
        cfg = one('SELECT settings_json FROM school_configuration WHERE school_id=?', (school['school_id'],))
        if cfg:
            try:
                obj = json.loads(cfg['settings_json'])
                limit = float(obj.get('mediaAprov', obj.get('passing_grade', limit)))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
    return {r['topic'] for r in rows('''SELECT topic,AVG(score) mean_score
              FROM grade_topics WHERE class_id=? AND subject=? GROUP BY topic HAVING AVG(score) < ?''',
                                     (class_id, subject, limit))}


@router.get('/options')
def exam_options(class_id: str, subject: str, user=Depends(require('coord', 'prof'))):
    _access(user, class_id, subject)
    cls=one('SELECT school_id FROM classes WHERE id=?',(class_id,))
    qs = _available(subject,user,cls['school_id'])
    topics = {}
    difficulties = {d: 0 for d in DIFS}
    types = {t: 0 for t in TYPES}
    for q in qs:
        tp = q['topic'] or 'Geral'
        topics[tp] = topics.get(tp, 0) + 1
        d = q['difficulty'] if q['difficulty'] in DIFS else 'média'
        difficulties[d] += 1
        types[_kind(q)] += 1
    return {'total': len(qs), 'topics': sorted([{'topic': k, 'count': v} for k, v in topics.items()], key=lambda x: x['topic']),
            'difficulties': difficulties, 'types': types,
            'critical_topics': sorted(_weak_topics(class_id, subject))}


@router.post('/random')
def create_random_exam(body: RandomExamInput, user=Depends(require('coord', 'prof'))):
    cls = _access(user, body.class_id, body.subject)
    if any(x not in TYPES for x in body.types):
        raise HTTPException(422, 'Um dos tipos de questão não é reconhecido.')
    goals = _limits([body.easy_percent, body.medium_percent, body.hard_percent], body.count)
    pool = [x for x in _available(body.subject,user,cls['school_id'])
            if _kind(x) in body.types and (not body.topics or x['topic'] in body.topics)]
    if not pool:
        raise HTTPException(422, 'Nenhuma questão publicada e autorizada atende aos filtros selecionados.')
    RNG.shuffle(pool)
    weak = _weak_topics(body.class_id, body.subject) if body.focus_weak_topics else set()
    if weak:
        # Preserva a distribuição de dificuldade e prioriza conteúdos de aprendizagem crítica.
        pool.sort(key=lambda q: 0 if q['topic'] in weak else 1)
    chosen, used = [], set()
    for diff in DIFS:
        matching = [q for q in pool if q['id'] not in used and
                    (q['difficulty'] if q['difficulty'] in DIFS else 'média') == diff]
        for q in matching[:goals[diff]]:
            chosen.append(q)
            used.add(q['id'])
    for q in pool:
        if len(chosen) >= body.count:
            break
        if q['id'] not in used:
            chosen.append(q)
            used.add(q['id'])
    chosen.sort(key=lambda q: DIFS.index(q['difficulty']) if q['difficulty'] in DIFS else 1)
    # Fechar a soma exatamente, sem perdas por arredondamento dos itens.
    units = round(body.total_points * 100)
    base, extra = divmod(units, len(chosen))
    points = [(base + (1 if i < extra else 0)) / 100 for i in range(len(chosen))]
    exam_id = secrets.token_hex(12)
    meta = {'source': 'random-bank', 'school_id': cls['school_id'],
            'topics': body.topics, 'types': body.types, 'goals': goals,
            'focus_weak_topics': body.focus_weak_topics,
            'instructions': body.instructions, 'requested_count': body.count}
    with session() as db:
        db.execute('''INSERT INTO exam_sets(id,creator_id,class_id,subject,title,total_points,
                      generation_mode,configuration_json) VALUES(?,?,?,?,?,?,?,?)''',
                   (exam_id, user['id'], body.class_id, body.subject, body.title,
                    float(body.total_points), 'random-bank', json.dumps(meta, ensure_ascii=False)))
        for pos, q in enumerate(chosen):
            db.execute('INSERT INTO exam_items(exam_id,question_id,position,points) VALUES(?,?,?,?)',
                       (exam_id, q['id'], pos, points[pos]))
        db.execute('INSERT INTO activity_log(user_id,action) VALUES(?,?)',
                   (user['id'], f'Sorteou prova com {len(chosen)} questões de {body.subject} para {cls["school_id"]}'))
    summary = {d: sum(1 for q in chosen if (q['difficulty'] if q['difficulty'] in DIFS else 'média') == d) for d in DIFS}
    missing = body.count - len(chosen)
    return {'id': exam_id, 'count': len(chosen), 'requested': body.count,
            'missing': missing, 'distribution': summary, 'total_points': body.total_points,
            'message': (f'Banco com {len(chosen)} questões compatíveis; faltaram {missing} questões para atingir a quantidade solicitada.'
                        if missing else 'Prova sorteada e salva a partir do banco central de questões.')}


@router.post('/preview')
def preview_random_exam(body: RandomExamInput, user=Depends(require('coord','prof'))):
    """Sorteia apenas em memoria. Nenhuma prova e salva sem confirmacao."""
    from .insights import class_observations
    cls=_access(user,body.class_id,body.subject)
    if any(t not in TYPES for t in body.types):
        raise HTTPException(422,'Tipo de questão não reconhecido.')
    goals=_limits([body.easy_percent,body.medium_percent,body.hard_percent],body.count)
    pool=[q for q in _available(body.subject,user,cls['school_id'])
          if _kind(q) in body.types and (not body.topics or q['topic'] in body.topics)]
    if not pool:
        raise HTTPException(422,'Nenhuma questão autorizada atende aos filtros.')
    insights=class_observations(body.class_id,body.subject,
                                user['id'] if user['role']=='prof' else '')
    seen=rows('''SELECT ei.question_id,COUNT(*) n FROM exam_items ei
        JOIN exam_sets ex ON ex.id=ei.exam_id
        WHERE ex.creator_id=? AND ex.class_id=? AND ex.subject=?
        GROUP BY ei.question_id''',(user['id'],body.class_id,body.subject))
    repetition={r['question_id']:r['n'] for r in seen}
    rank={topic:i for i,topic in enumerate(insights['priorities'])}
    RNG.shuffle(pool)
    # A nota, a pratica, o cronograma e as provas anteriores alteram o sorteio
    # da conta logada. Nao ha treino externo com identificacao de alunos.
    pool.sort(key=lambda q:(
        -((10-rank[q['topic']]) if body.focus_weak_topics and q['topic'] in rank else 0),
        repetition.get(q['id'],0)))
    chosen=[];used=set()
    for difficulty in DIFS:
        options=[q for q in pool if q['id'] not in used
                 and (q['difficulty'] if q['difficulty'] in DIFS else 'média')==difficulty]
        for q in options[:goals[difficulty]]:
            chosen.append(q);used.add(q['id'])
    for q in pool:
        if len(chosen)>=body.count:break
        if q['id'] not in used:
            chosen.append(q);used.add(q['id'])
    ids=[q['id'] for q in chosen]
    placeholders=','.join('?' for _ in ids)
    details={q['id']:q for q in rows('''SELECT id,title,context,prompt,alternatives_json,
         media_json,correct_letter,topic,difficulty,source FROM questions WHERE id IN ('''+placeholders+')',ids)}
    units=round(body.total_points*100)
    base,extra=divmod(units,len(chosen))
    items=[]
    for i,qid in enumerate(ids):
        q=details[qid]
        q['alternatives']=json.loads(q.pop('alternatives_json') or '[]')
        q['media']=json.loads(q.pop('media_json') or '[]')
        q['points']=(base+(1 if i<extra else 0))/100
        items.append(q)
    return {'saved':False,'items':items,'count':len(items),'requested':body.count,
            'missing':body.count-len(items),'total_points':body.total_points,
            'class_id':body.class_id,'subject':body.subject,'school_id':cls['school_id'],
            'title':body.title,'instructions':body.instructions,
            'personalization':{
                'critical_topics':insights['priorities'][:5],
                'previous_exams_considered':sum(repetition.values()),
                'basis':'Notas por tópico, respostas, cronograma e provas anteriores deste professor'},
            'message':'Prévia gerada. Edite, sorteie novamente ou descarte; nada foi salvo ainda.'}


@router.get('/candidates')
def replacement_candidates(class_id:str,subject:str,current_id:str='',
                           user=Depends(require('coord','prof'))):
    cls=_access(user,class_id,subject)
    result=[]
    for q in _available(subject,user,cls['school_id']):
        if q['id']==current_id:continue
        detail=one('SELECT id,title,topic,difficulty FROM questions WHERE id=?',(q['id'],))
        if detail:result.append(detail)
    return {'items':result[:250]}
