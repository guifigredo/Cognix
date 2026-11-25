"""Fidelidade ao HTML original: Estúdio clássico montado por escola e sessão.

O Estúdio é um espaço de demonstração isolado por usuário/escola: grava suas edições
em studio_states, não altera matrículas, notas e questões autorizadas do SQLite.
O painel moderno é a fonte de dados compartilhados/permite atribuição real.
"""
import json
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .auth import current_user
from .db import ROOT, one, rows, session
from .access import allowed_schools, assert_school, subjects_for
from .permissions import is_ai_generated
from .seed_legacy import TEACHERS, sid

router=APIRouter(tags=['Estúdio clássico'])
SOURCE=json.loads((ROOT/'data/legacy_full_demo.json').read_text(encoding='utf8'))
REVERSE={account[0]:key for key,account in TEACHERS.items()}
REVERSE['teacher-physics-x']='prof-caio'


def legacy_profile(user):
    if user['role']=='coord':return 'coord'
    if user['role']=='aluno':return 'aluno'
    return REVERSE.get(user['id'],'prof-'+user['id'])


def legacy_id(user):
    if user['id']=='student-demo':return 'm0'
    if user['id'].startswith('legacy-student-'):return user['id'].removeprefix('legacy-student-')
    return None


def _question_projection(user,school):
    allowed=subjects_for(user,school)
    if not allowed:return []
    sql='''SELECT id,source,year,discipline,topic,difficulty,context,prompt,
              alternatives_json,correct_letter FROM questions
              WHERE (school_id IS NULL OR school_id=?) AND discipline IN ('''+','.join('?' for _ in allowed)+''') AND status='published'
              AND rights_status IN ('authorized','demo')
              AND (?=1 OR creator_id IS NULL OR creator_id=?) ORDER BY source,id LIMIT 2500'''
    out=[]
    for r in rows(sql,[school]+allowed+[int(user['role']=='coord'),user['id']]):
        try:alts=json.loads(r['alternatives_json'])
        except Exception:alts=[]
        labels=[a.get('text','') for a in alts]
        correct=r['correct_letter']
        if labels and correct in [chr(65+i) for i in range(len(labels))]:answer=str(ord(correct)-65)
        else:answer=''
        typ='multipla' if len(labels)>2 else 'vf' if len(labels)==2 else 'discursiva'
        out.append({'id':'central-'+r['id'],'disciplina':r['discipline'],'tema':r['topic'] or 'Geral',
           'dificuldade':r['difficulty'] or 'média','tipo':typ,'enunciado':(r['context']+'\n'+r['prompt']).strip()[:6000],
           'alternativas':labels,'resposta':answer,'fonte':r['source'],'origem':'central','centralId':r['id'],
           'ano':r['year']})
    return out


def filtered_db(user,school,existing=None):
    db=deepcopy(existing if existing is not None else SOURCE['db'])
    allowed=subjects_for(user,school)
    # Nunca devolver dados de escolas não autorizadas, mesmo que alguém manipule
    # o JSON previamente salvo do Estúdio.
    db['escolas']=[x for x in db.get('escolas',[]) if x.get('id')==school]
    if not db['escolas']:
        db['escolas']=[x for x in SOURCE['db']['escolas'] if x['id']==school]
    db['escola']=db['escolas'][0]['nome'] if db['escolas'] else 'Escola'
    class_rows=rows('''SELECT a.class_id,a.subject FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
                   WHERE a.teacher_id=? AND c.school_id=?''',(user['id'],school)) if user['role']=='prof' else []
    def matches(t):
        if t.get('escolaId')!=school or t.get('disciplina') not in allowed:return False
        if user['role']=='prof':
            group=t.get('grupo','').split('-')[-1]
            known={'escola-x':{'n':'x-9a','u':'x-1b','d':'x-2a','m':'x-3a'},
                   'escola-y':{'u':'y-1b','d':'y-2a','m':'y-3a'},
                   'escola-z':{'d':'z-2a','m':'z-3a'}}
            cls=known.get(school,{}).get(group)
            return any(a['class_id']==cls and a['subject']==t['disciplina'] for a in class_rows)
        if user['role']=='aluno':
            lid=legacy_id(user)
            return bool(lid and any(a['id']==lid for a in t.get('alunos',[])))
        return True
    db['turmas']=[t for t in db.get('turmas',[]) if matches(t)]
    if user['role']=='prof':
        pid=legacy_profile(user)
        for t in db['turmas']:t['prof']=pid
    if user['role']=='aluno':
        lid=legacy_id(user)
        for t in db['turmas']:
            t['alunos']=[a for a in t.get('alunos',[]) if a['id']==lid]
            t['notas']={lid:t.get('notas',{}).get(lid,{})}
            t['temaNotas']={lid:t.get('temaNotas',{}).get(lid,{})}
        for key in ('historico','respostas','perfilAluno','pratica','ultimo','sessoes','metas','cursosFb'):
            db[key]={lid:db.get(key,{}).get(lid,{})} if lid else {}
    allowed_ids={t['id'] for t in db['turmas']}
    db['agenda']=[a for a in db.get('agenda',[]) if a.get('turma') in allowed_ids]
    if user['role']=='prof':
        for a in db['agenda']:a['prof']=legacy_profile(user)
    if user['role']=='coord':
        # Evitar listagem de perfis de outras escolas; a coordenação vê somente
        # pessoas atribuídas a turmas visíveis no HTML.
        used={t['prof'] for t in db['turmas']}
        db['professores']={k:v for k,v in db.get('professores',{}).items() if k in used}
    elif user['role']=='prof':
        pid=legacy_profile(user)
        db['professores']={pid:deepcopy(SOURCE['perfis'].get(pid,{'nome':user['name'],'email':user['email']}))}
        db['professores'][pid]['nome']=user['name']
        db['professores'][pid]['email']=user['email']
    else:db['professores']={}
    db['vinculos']=[v for v in db.get('vinculos',[]) if v.get('escolaId')==school and v.get('disciplina') in allowed]
    # Questões centrais são projeções de leitura; os ajustes feitos no Estúdio
    # são rascunhos locais e não publicam no catálogo do servidor.
    own=[q for q in db.get('questoes',[]) if q.get('disciplina') in allowed and not str(q.get('id','')).startswith('central-') and (user['role']!='coord' or q.get('origem')=='ia')]
    db['questoes']=own+_question_projection(user,school)
    db['provas']=[p for p in db.get('provas',[]) if p.get('turma') in allowed_ids]
    db['config']=deepcopy(db.get('config',SOURCE['db']['config']))
    db['multiEscolaV1']=True
    db['assinaturas']={k:v for k,v in db.get('assinaturas',{}).items() if k==legacy_profile(user)}
    if user['id']=='teacher-demo':
        db['assinaturas']['prof-fis']={'plano':'Professor Individual', 'ciclo':'mensal',
               'status':'simulacao','valor':'29,90','inicio':'2026-11-16','semCobranca':True}
    return db


@router.get('/studio',response_class=HTMLResponse)
def studio(school:str=Query(''),user=Depends(current_user)):
    if user['role']=='aluno':raise HTTPException(403,'A versão antiga não isola respostas do aluno com segurança; utilize o portal atual.')
    schools=allowed_schools(user)
    if not schools:raise HTTPException(403,'Nenhuma escola atribuída à conta.')
    school=school or schools[0]
    assert_school(user,school)
    stored=one('SELECT payload_json FROM studio_states WHERE user_id=? AND school_id=?',(user['id'],school))
    raw=json.loads(stored['payload_json']) if stored else None
    db=filtered_db(user,school,raw)
    pid=legacy_profile(user)
    p=deepcopy(SOURCE['perfis'])
    if user['role']=='coord':p['coord']={'tipo':'coord','nome':user['name'],'papel':'Coordenação exclusiva desta escola'}
    elif user['role']=='prof':
        p[pid]={'tipo':'prof','nome':user['name'],'disc':subjects_for(user,school),
                'papel':'Professor independente · assinatura individual demonstrativa' if user['id']=='teacher-demo' else 'Docente · atribuições nesta escola',
                'email':user['email'],'ativo':True}
    else:p['aluno']={'tipo':'aluno','nome':user['name'],'papel':'Estudante matriculado nesta escola','alunoId':legacy_id(user) or 'm0'}
    html=(ROOT/'frontend/studio_template.html').read_text(encoding='utf8')
    boot={'user':{'id':user['id'],'name':user['name'],'role':user['role']},
          'school_id':school,'db':db,'profiles':p,'profile':pid}
    injected='<script>window.COGNIX_BOOT='+json.dumps(boot,ensure_ascii=False).replace('<','\\u003c')+';</script>\n'
    # O HTML antigo inclui script inline; protegido por sessão e CSP restrita à rota.
    return HTMLResponse(html.replace('<script>',injected+'<script>',1))

class StudioChange(BaseModel):
    school_id:str
    db:dict

@router.put('/api/studio/state')
def save_studio(body:StudioChange,user=Depends(current_user)):
    if user['role']=='aluno':raise HTTPException(403,'Somente educadores podem utilizar o Estúdio legado.')
    assert_school(user,body.school_id)
    # Limite impede JSON excessivo; proíbe gravar mudanças do Estúdio no catálogo central.
    length=len(json.dumps(body.db,ensure_ascii=False))
    if length>6_000_000:raise HTTPException(413,'Demonstração ultrapassa o limite de armazenamento.')
    payload=filtered_db(user,body.school_id,body.db)
    with session() as db:
        db.execute('''INSERT INTO studio_states(user_id,school_id,payload_json)
             VALUES(?,?,?) ON CONFLICT(user_id,school_id) DO UPDATE SET
             payload_json=excluded.payload_json,updated_at=CURRENT_TIMESTAMP''',
             (user['id'],body.school_id,json.dumps(payload,ensure_ascii=False)))
    return {'ok':True,'school':body.school_id,'mode':'rascunho-isolado'}
