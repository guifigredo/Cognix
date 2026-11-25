"""API Cognix: autenticação real de demonstração, permissões no servidor e dados persistentes."""
import hashlib, json, os, secrets, datetime, math
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from .db import init_db, session, one, rows, ROOT
from .auth import COOKIE, current_user, require, register_user, create_school_account, password_verify, password_hash, new_session
from .import_enem import run_job
from .access import allowed_schools,assert_school,assert_class,subjects_for,assert_subject,scoped_question_sql
from .permissions import for_user, is_ai_generated

def initialize():
    init_db()
    if os.getenv('COGNIX_EXEMPLOS_DOCENTES','1')=='1':
        from .seed_teacher_items import seed_examples
        seed_examples()


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app=FastAPI(title='Cognix API',version='10.0',lifespan=lifespan,docs_url='/developer/api-docs')
UI = ROOT/'frontend'
app.mount('/assets',StaticFiles(directory=str(UI)),name='assets')

@app.middleware('http')
async def safety_headers(request,call_next):
    if request.method in ('POST','PUT','PATCH','DELETE') and request.url.path.startswith('/api/'):
        origin=request.headers.get('origin')
        if origin and origin.rstrip('/') != f'{request.url.scheme}://{request.headers.get("host","")}'.rstrip('/'):
            return JSONResponse({'detail':'Origem não permitida'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
    response.headers['Content-Security-Policy']=("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; " if request.url.path.startswith('/studio') else "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
         "img-src 'self' https: data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    return response

@app.get('/')
def home(): return FileResponse(UI/'index.html')

@app.get('/api/health')
def health():return {'ok':True,'version':'10.0'}

class Credentials(BaseModel):
    email:str
    password:str
class Register(Credentials):
    name:str
    plan:Literal['individual']
    role:str|None=None   # Rejeita tentativas antigas de autocadastrar aluno/coordenação.
class SchoolAccount(Credentials):
    name:str
    role:Literal['prof','aluno','coord']
    school_id:str
class SchoolRequest(BaseModel):
    school_id:str
class SchoolDecision(BaseModel):
    decision:Literal['approved','rejected']
class ResetPassword(BaseModel):
    current:str
    new:str
class Profile(BaseModel):
    name:str=Field(min_length=3,max_length=100)
class Assignment(BaseModel):
    teacher_id:str
    class_id:str
    subject:str=Field(min_length=2,max_length=60)
class Enroll(BaseModel):
    student_id:str
    class_id:str
class ExamInput(BaseModel):
    class_id:str
    subject:str
    title:str=Field(min_length=3,max_length=120)
    question_ids:list[str]=Field(min_length=1,max_length=100)
    total_points:float=Field(10,gt=0,le=100)
    instructions:str=Field('Leia com atenção.',max_length=1200)
    question_edits:dict[str,str]=Field(default_factory=dict)
class ExamApplication(BaseModel):
    assessment:str=Field(min_length=2,max_length=80)
class AttemptInput(BaseModel):
    question_id:str
    letter:str
    school_id:str=''
class GradeInput(BaseModel):
    class_id:str
    subject:str
    student_id:str
    assessment:str=Field(min_length=2,max_length=80)
    score:float=Field(ge=0,le=10)
    topic_scores:dict[str,float]|None=None
class ReviewInput(BaseModel):
    status:str
    rights_status:str='pending'
    discipline:str=''
    topic:str=''
    difficulty:str=''

LOGIN_ATTEMPTS={}
@app.get('/api/auth/status')
def auth_status():
    return {'coordinator_exists':bool(one("SELECT id FROM users WHERE role='coord' LIMIT 1")), 'setup_required':True}

@app.post('/api/auth/register')
def signup(body:Register,response:Response):
    # Nunca permitir autocadastro de contas escolares, alunos ou coordenação.
    if body.role and body.role!='prof':
        raise HTTPException(403,'Contas escolares são criadas exclusivamente pela coordenação.')
    id=register_user(body.name,body.email,body.password,'prof')
    new_session(response,id)
    return {'ok':True,'user':one('SELECT id,name,email,role,account_plan FROM users WHERE id=?',(id,))}

@app.post('/api/auth/login')
def login(body:Credentials,response:Response,request:Request):
    email=body.email.strip().lower()
    client_ip=request.client.host if request.client else 'unknown'
    rate_id=hashlib.sha256((client_ip+':'+email).encode()).hexdigest()
    now=datetime.datetime.now(datetime.timezone.utc).timestamp()
    a=[t for t in LOGIN_ATTEMPTS.get(rate_id,[]) if now-t<300]
    if len(a)>=8: raise HTTPException(429,'Muitas tentativas. Tente novamente em cinco minutos.')
    user=one('SELECT * FROM users WHERE email=?',(email,))
    if not user:
        user=one('''SELECT u.* FROM verified_emails v JOIN users u ON u.id=v.user_id
                   WHERE v.email=?''',(email,))
    if not user or not user['active'] or not password_verify(body.password,user['password_hash']):
        a.append(now);LOGIN_ATTEMPTS[rate_id]=a
        raise HTTPException(401,'E-mail ou senha inválidos.')
    LOGIN_ATTEMPTS.pop(rate_id,None)
    new_session(response,user['id'])
    return {'ok':True,'user':{k:user[k] for k in ('id','name','email','role')}}

@app.post('/api/auth/logout')
def logout(response:Response,request:Request):
    token=request.cookies.get(COOKIE)
    if token:
        with session() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie(COOKIE,path='/')
    return {'ok':True}

@app.get('/api/me')
def me(user=Depends(current_user)):
    if user['role']=='coord':
        schools=rows('''SELECT s.* FROM schools s JOIN coordinator_schools cs ON cs.school_id=s.id
                        WHERE cs.user_id=? ORDER BY s.id''',(user['id'],))
    elif user['role']=='prof':
        schools=rows('''SELECT s.* FROM schools s JOIN school_memberships m ON m.school_id=s.id
             WHERE m.user_id=? AND m.status='active' ORDER BY s.id''',(user['id'],))
    else:
        schools=rows('''SELECT s.* FROM schools s WHERE s.id IN (
            SELECT c.school_id FROM classes c JOIN enrollments e ON e.class_id=c.id WHERE e.user_id=?
            UNION SELECT m.school_id FROM school_memberships m WHERE m.user_id=?) ORDER BY s.id''',(user['id'],user['id']))
    safe_user={key:user.get(key) for key in ('id','name','email','role','account_plan','active')}
    return {'user':safe_user,'schools':schools,
        'has_third_year':any(c['grade'].startswith('3ª') for c in visible_classes(user)),
        'subscription': ('Plano Individual · demonstração' if user.get('account_plan')=='individual' else 'Plano da Escola · demonstração'),
        'subjects_by_school':{sc['id']:subjects_for(user,sc['id']) for sc in schools},
        'permissions':for_user(user['role'])['capabilities']}

@app.get('/api/permissions')
def permissions(user=Depends(current_user)):
    return for_user(user['role'])

@app.patch('/api/me')
def edit_profile(data:Profile,user=Depends(current_user)):
    with session() as db:db.execute('UPDATE users SET name=? WHERE id=?',(data.name.strip(),user['id']))
    return {'ok':True}

@app.post('/api/me/password')
def edit_password(data:ResetPassword,user=Depends(current_user)):
    with session() as db:
        saved=db.execute('SELECT password_hash FROM users WHERE id=?',(user['id'],)).fetchone()
        if not password_verify(data.current,saved['password_hash']): raise HTTPException(403,'Senha atual incorreta.')
        db.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(data.new),user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
    return {'ok':True,'message':'Senha alterada; faça login novamente.'}

@app.get('/api/schools')
def schools(user=Depends(current_user)):
    if user['role']=='coord':return me(user)['schools']
    return me(user)['schools']

def visible_classes(user,school=None):
    if user['role']=='coord':
        sql='''SELECT c.*,s.name school_name FROM classes c JOIN schools s ON s.id=c.school_id
        JOIN coordinator_schools cs ON cs.school_id=c.school_id WHERE cs.user_id=? AND (? IS NULL OR c.school_id=?)'''
        if school:assert_school(user,school)
        return rows(sql,(user['id'],school,school))
    if user['role']=='prof':
        if school:assert_school(user,school)
        return rows('''SELECT DISTINCT c.*,s.name school_name FROM classes c JOIN schools s ON s.id=c.school_id
        JOIN teaching_assignments a ON a.class_id=c.id
        JOIN school_memberships m ON m.user_id=a.teacher_id AND m.school_id=c.school_id AND m.status='active'
        WHERE a.teacher_id=? AND (? IS NULL OR c.school_id=?) ORDER BY s.id,c.name''',
        (user['id'],school,school))
    if school:assert_school(user,school)
    return rows('''SELECT c.*,s.name school_name FROM classes c JOIN schools s ON s.id=c.school_id
         JOIN enrollments e ON e.class_id=c.id WHERE e.user_id=? AND (? IS NULL OR c.school_id=?) ORDER BY s.id,c.name''',
         (user['id'],school,school))

@app.get('/api/classes')
def classes(school:str|None=None,user=Depends(current_user)):
    classes=visible_classes(user,school)
    for c in classes:
        if user['role']=='prof':
            c['subjects']=[r['subject'] for r in rows('SELECT subject FROM teaching_assignments WHERE class_id=? AND teacher_id=?',(c['id'],user['id']))]
        elif user['role']=='coord':
            c['subjects']=[r['subject'] for r in rows('SELECT DISTINCT subject FROM teaching_assignments WHERE class_id=?',(c['id'],))]
        else:c['subjects']=[]
    return classes

@app.get('/api/public/schools')
def public_schools():
    # O nome da escola é público; matrículas e pessoas não são.
    return rows('SELECT id,name,subtitle FROM schools ORDER BY name')

@app.post('/api/team/accounts',status_code=201)
def provision_school_account(body:SchoolAccount,user=Depends(require('coord'))):
    assert_school(user,body.school_id)
    return create_school_account(creator_id=user['id'],school_id=body.school_id,
        name=body.name,email=body.email,password=body.password,role=body.role)

@app.get('/api/affiliations')
def own_affiliations(user=Depends(require('prof'))):
    if user.get('account_plan')!='individual':
        return {'plan':'school','requests':[]}
    return {'plan':'individual','requests':rows('''SELECT r.id,r.school_id,s.name school_name,
             r.status,r.created_at FROM school_join_requests r JOIN schools s ON s.id=r.school_id
             WHERE r.user_id=? ORDER BY r.created_at DESC''',(user['id'],))}

@app.post('/api/affiliations/request',status_code=201)
def request_affiliation(body:SchoolRequest,user=Depends(require('prof'))):
    if user.get('account_plan')!='individual':
        raise HTTPException(403,'Somente professores do plano individual solicitam vínculos.')
    with session() as db:
        if not db.execute('SELECT 1 FROM schools WHERE id=?',(body.school_id,)).fetchone():
            raise HTTPException(404,'Escola não encontrada.')
        if db.execute("SELECT 1 FROM school_memberships WHERE user_id=? AND school_id=? AND status='active'",(user['id'],body.school_id)).fetchone():
            raise HTTPException(409,'Você já está vinculado a essa escola.')
        old=db.execute('SELECT id,status FROM school_join_requests WHERE user_id=? AND school_id=?',(user['id'],body.school_id)).fetchone()
        if old:
            if old['status']=='pending':raise HTTPException(409,'O pedido já está aguardando análise.')
            db.execute('''UPDATE school_join_requests SET status='pending',created_at=CURRENT_TIMESTAMP,
                      reviewed_by=NULL,reviewed_at=NULL WHERE id=?''',(old['id'],))
        else:
            db.execute('INSERT INTO school_join_requests(id,user_id,school_id) VALUES(?,?,?)',
                    (secrets.token_hex(12),user['id'],body.school_id))
    return {'ok':True,'message':'Pedido enviado à coordenação. Você ainda não tem acesso às turmas dessa escola.'}

@app.get('/api/team/join-requests')
def school_affiliation_requests(user=Depends(require('coord'))):
    ids=allowed_schools(user)
    if not ids:return []
    ph=','.join('?' for _ in ids)
    return rows(f'''SELECT r.id,r.school_id,s.name school_name,u.id teacher_id,
                    u.name teacher_name,u.email teacher_email,r.status,r.created_at
                    FROM school_join_requests r JOIN schools s ON s.id=r.school_id
                    JOIN users u ON u.id=r.user_id
                    WHERE r.school_id IN ({ph}) AND r.status='pending'
                    ORDER BY r.created_at DESC''',ids)

@app.post('/api/team/join-requests/{request_id}')
def decide_affiliation(request_id:str,body:SchoolDecision,user=Depends(require('coord'))):
    with session() as db:
        req=db.execute('''SELECT r.*,u.role,u.account_plan FROM school_join_requests r
                 JOIN users u ON u.id=r.user_id WHERE r.id=?''',(request_id,)).fetchone()
        if not req:raise HTTPException(404,'Pedido não encontrado.')
        if not db.execute('SELECT 1 FROM coordinator_schools WHERE user_id=? AND school_id=?',
                          (user['id'],req['school_id'])).fetchone():
            raise HTTPException(403,'Você só pode analisar solicitações da sua escola.')
        if req['status']!='pending':raise HTTPException(409,'Esse pedido já foi analisado.')
        if req['role']!='prof' or req['account_plan']!='individual':
            raise HTTPException(422,'Solicitação de plano inválida.')
        db.execute('''UPDATE school_join_requests SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP
                      WHERE id=?''',(body.decision,user['id'],request_id))
        if body.decision=='approved':
            db.execute('INSERT OR IGNORE INTO school_memberships(user_id,school_id) VALUES(?,?)',
                    (req['user_id'],req['school_id']))
            db.execute("UPDATE school_memberships SET status='active' WHERE user_id=? AND school_id=?",
                       (req['user_id'],req['school_id']))
    return {'ok':True,'message':('Professor vinculado à escola. Atribua turmas e disciplinas para liberar acesso.' if body.decision=='approved' else 'Pedido recusado.')}

@app.get('/api/team')
def team(user=Depends(require('coord'))):
    ids=allowed_schools(user)
    if not ids:return {'teachers':[],'students':[],'coordinators':[],'assignments':[],'enrollments':[]}
    ph=','.join('?' for _ in ids)
    # Nunca liste contas de outras escolas nem contas sem vínculo institucional.
    teachers=rows(f'''SELECT u.id,u.name,u.email,u.active,u.account_plan,
            GROUP_CONCAT(m.school_id) school_ids FROM users u
            JOIN school_memberships m ON m.user_id=u.id AND m.status='active'
            WHERE u.role='prof' AND m.school_id IN ({ph})
            GROUP BY u.id ORDER BY u.name''',ids)
    students=rows(f'''SELECT u.id,u.name,u.email,u.active,u.account_plan FROM users u
        WHERE u.role='aluno' AND EXISTS (SELECT 1 FROM school_memberships m
                  WHERE m.user_id=u.id AND m.school_id IN ({ph})) ORDER BY u.name''',ids)
    coordinators=rows(f'''SELECT DISTINCT u.id,u.name,u.email,u.active FROM users u
      JOIN coordinator_schools z ON z.user_id=u.id WHERE z.school_id IN ({ph}) ORDER BY u.name''',ids)
    assignments=rows(f'''SELECT a.id,a.teacher_id,a.class_id,a.subject,u.name teacher_name,
          c.name class_name,s.name school_name,s.id school_id FROM teaching_assignments a
          JOIN users u ON u.id=a.teacher_id JOIN classes c ON c.id=a.class_id
          JOIN schools s ON s.id=c.school_id JOIN school_memberships m ON m.user_id=a.teacher_id
          AND m.school_id=s.id AND m.status='active' WHERE s.id IN ({ph})
          ORDER BY school_name,class_name,subject''',ids)
    enrollments=rows(f'''SELECT e.user_id,e.class_id,u.name student_name,c.name class_name,s.name school_name
        FROM enrollments e JOIN users u ON u.id=e.user_id JOIN classes c ON c.id=e.class_id
        JOIN schools s ON s.id=c.school_id WHERE s.id IN ({ph})''',ids)
    return dict(teachers=teachers,students=students,coordinators=coordinators,assignments=assignments,enrollments=enrollments)

@app.get('/api/audit/grades')
def grade_audit(school:str,user=Depends(require('coord'))):
    assert_school(user,school)
    return rows('''SELECT a.created_at,cu.name coordinator_name,stu.name student_name,
          c.name class_name,a.subject,a.assessment,a.previous_score,a.new_score
       FROM grade_audit a JOIN users cu ON cu.id=a.coordinator_id
       JOIN users stu ON stu.id=a.student_id JOIN classes c ON c.id=a.class_id
       WHERE a.school_id=? ORDER BY a.id DESC LIMIT 150''',(school,))

@app.post('/api/team/assign')
def assign(body:Assignment,user=Depends(require('coord'))):
    with session() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='prof'",(body.teacher_id,)).fetchone():
            raise HTTPException(422,'Professor inválido.')
        cls=assert_class(user,body.class_id)
        if not db.execute("SELECT 1 FROM school_memberships WHERE user_id=? AND school_id=? AND status='active'",
                          (body.teacher_id,cls['school_id'])).fetchone():
            raise HTTPException(403,'Professor não vinculado à sua escola. Aprove o pedido ou crie conta escolar.')
        db.execute('INSERT OR IGNORE INTO teaching_assignments(id,teacher_id,class_id,subject) VALUES(?,?,?,?)',
                  (secrets.token_hex(12),body.teacher_id,body.class_id,body.subject.strip()))
    return {'ok':True}

@app.delete('/api/team/assign/{assignment_id}')
def unassign(assignment_id:str,user=Depends(require('coord'))):
    x=one('SELECT class_id FROM teaching_assignments WHERE id=?',(assignment_id,))
    if not x:raise HTTPException(404,'Vínculo não encontrado.')
    assert_class(user,x['class_id'])
    with session() as db:db.execute('DELETE FROM teaching_assignments WHERE id=?',(assignment_id,))
    return {'ok':True}

@app.post('/api/team/enroll')
def enroll(body:Enroll,user=Depends(require('coord'))):
    with session() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='aluno'",(body.student_id,)).fetchone():
            raise HTTPException(422,'Aluno inválido.')
        cls=assert_class(user,body.class_id)
        if not db.execute('SELECT 1 FROM school_memberships WHERE user_id=? AND school_id=?',
                          (body.student_id,cls['school_id'])).fetchone():
            raise HTTPException(403,'Aluno não pertence à sua escola. Cadastre-o no plano da escola.')
        db.execute('INSERT OR IGNORE INTO enrollments(user_id,class_id) VALUES(?,?)',(body.student_id,body.class_id))
    return {'ok':True}

def question_visibility(user, school=''):
    '''Filtro *no servidor*: acervo central + itens da instituição, por disciplina atribuída.

    Itens ENEM de Ciências da Natureza não têm Física, Química ou Biologia explícitas.
    Só aparecem ao docente após classificação curricular da SUA escola; o original
    central não é alterado por uma coordenação local.
    '''
    permitted=allowed_schools(user)
    if school:
        assert_school(user,school)
        permitted=[school]
    subjects=subjects_for(user,school or None) if user['role']=='prof' else []
    placeholders=','.join('?' for _ in permitted)
    legacy='1=0';legacy_args=[]
    if permitted:
        legacy=f'(q.school_id IS NULL OR q.school_id IN ({placeholders}))'
        legacy_args=list(permitted)
        if user['role']=='prof':
            if subjects:
                legacy+=f''' AND (q.discipline IN ({','.join('?' for _ in subjects)}) OR EXISTS
                  (SELECT 1 FROM question_school_classifications qc
                  JOIN teaching_assignments ta ON ta.subject=qc.discipline
                  JOIN classes c ON c.id=ta.class_id AND c.school_id=qc.school_id
                  JOIN school_memberships m ON m.user_id=ta.teacher_id AND m.school_id=c.school_id AND m.status='active'
                  WHERE qc.question_id=q.id AND ta.teacher_id=? AND qc.school_id IN ({placeholders})))'''
                legacy_args+=subjects+[user['id']]+permitted
            else:legacy+=' AND 1=0'
            legacy+=' AND (q.creator_id IS NULL OR q.creator_id=?)'
            legacy_args.append(user['id'])
        elif user['role']=='aluno':legacy+=' AND q.creator_id IS NULL'
    # Itens v10 requerem propriedade de coleção; o legado sem classificação
    # permanece no acesso antigo, mas é deliberadamente intransferível.
    clauses=[f'(NOT EXISTS (SELECT 1 FROM question_records r WHERE r.question_id=q.id) AND {legacy})']
    args=legacy_args
    if user['role']=='prof':
        clauses.append('''EXISTS (SELECT 1 FROM question_records r JOIN question_collections c ON c.id=r.collection_id
            WHERE r.question_id=q.id AND c.kind='personal' AND c.owner_id=?)''')
        args.append(user['id'])
    if permitted:
        collection=f'''EXISTS (SELECT 1 FROM question_records r JOIN question_collections c ON c.id=r.collection_id
                   WHERE r.question_id=q.id AND c.kind='school' AND c.school_id IN ({placeholders})'''
        collection_args=list(permitted)
        if user['role']=='prof':
            if subjects:
                collection+=f" AND q.discipline IN ({','.join('?' for _ in subjects)})"
                collection_args+=subjects
            else:collection+=' AND 1=0'
        collection+=')'
        clauses.append(collection);args+=collection_args
    return '('+' OR '.join(clauses)+')',args


def question_school_details(item,user,school=''):
    '''Sinaliza em que escola uma questão central recebeu classificação curricular.'''
    ids=[school] if school else allowed_schools(user)
    tags=[]
    if ids:
        tags=rows('''SELECT school_id,discipline,topic,difficulty FROM question_school_classifications
              WHERE question_id=? AND school_id IN ('''+','.join('?' for _ in ids)+''')''',[item['id']]+ids)
    item['school_classifications']=tags
    item['display_discipline']=item['discipline'] or ', '.join(sorted({x['discipline'] for x in tags}))
    return item


class QuestionSchoolClassification(BaseModel):
    school_id: str
    discipline: str
    topic: str = ''
    difficulty: str = ''


@app.post('/api/questions/{qid}/school-classification')
def classify_enem_for_school(qid:str,body:QuestionSchoolClassification,user=Depends(require('coord'))):
    '''Apenas metadados locais: nunca altera conteúdo, gabarito, direitos ou publicação global.'''
    assert_school(user,body.school_id)
    q=one('SELECT id,source,area,school_id,discipline FROM questions WHERE id=?',(qid,))
    if not q or q['source']!='ENEM API' or q['school_id'] is not None:
        raise HTTPException(422,'Somente questões ENEM do catálogo central podem receber essa classificação.')
    eligible={'Ciências da Natureza':['Física','Química','Biologia'],
              'Matemática':['Matemática'],
              'Linguagens':['Linguagens','Português'],
              'Ciências Humanas':['Geografia','História']}.get(q['area'],[])
    discipline=body.discipline.strip()
    if discipline not in eligible or discipline not in subjects_for(user,body.school_id):
        raise HTTPException(422,'Disciplina incompatível com a área do ENEM ou não oferecida nesta escola.')
    difficulty=body.difficulty.strip()
    if difficulty not in ('','fácil','média','difícil'):
        raise HTTPException(422,'Dificuldade inválida.')
    with session() as db:
        db.execute('''INSERT INTO question_school_classifications
             (school_id,question_id,discipline,topic,difficulty,classified_by)
             VALUES (?,?,?,?,?,?) ON CONFLICT(school_id,question_id) DO UPDATE SET
             discipline=excluded.discipline,topic=excluded.topic,difficulty=excluded.difficulty,
             classified_by=excluded.classified_by,updated_at=CURRENT_TIMESTAMP''',
             (body.school_id,qid,discipline,body.topic.strip()[:200],difficulty,user['id']))
        db.execute('INSERT INTO activity_log(user_id,action) VALUES(?,?)',
                   (user['id'],f'Classificou questão ENEM {qid} para {body.school_id} como {discipline}'))
    return {'ok':True,'school_id':body.school_id,'discipline':discipline,
            'message':'Classificação escolar salva. Professores vinculados à disciplina poderão consultar esta questão.'}


@app.get('/api/questions/mine')
def my_questions(school: str='', subject: str='', page:int=Query(1,ge=1),
                 limit:int=Query(20,ge=1,le=100), user=Depends(require('prof'))):
    if school: assert_school(user,school)
    allowed=subjects_for(user,school or None)
    conditions=['creator_id=?']; args=[user['id']]
    if allowed:
        conditions.append('discipline IN ('+','.join('?' for _ in allowed)+')')
        args+=allowed
    else:
        return {'total':0,'items':[],'subjects':[],'page':page}
    if school:conditions.append('school_id=?');args.append(school)
    else:
        sites=allowed_schools(user)
        conditions.append('school_id IN ('+','.join('?' for _ in sites)+')');args+=sites
    if subject:
        if subject not in allowed:raise HTTPException(403,'Esta disciplina não está atribuída a você na escola.')
        conditions.append('discipline=?');args.append(subject)
    where=' AND '.join(conditions)
    total=one('SELECT COUNT(*) n FROM questions WHERE '+where,args)['n']
    items=rows('''SELECT id,source,school_id,year,question_number,area,discipline,title,context,prompt,
                    alternatives_json,media_json,correct_letter,topic,difficulty,status,rights_status,imported_at
                 FROM questions WHERE '''+where+' ORDER BY imported_at DESC,id LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])
    for item in items:
        item['alternatives']=json.loads(item.pop('alternatives_json'))
        item['media']=json.loads(item.pop('media_json'))
    return {'total':total,'items':items,'subjects':allowed,'page':page}

@app.get('/api/questions')
def questions(q:str='',year:int|None=None,area:str='',subject:str='',topic:str='',difficulty:str='',
              source:str='',status:str='',rights_status:str='',creator_id:str='',scope:str='',
              school:str='',page:int=Query(1,ge=1,le=50000),limit:int=Query(20,ge=1,le=100),
              user=Depends(current_user)):
    # A visualização administrativa é completa, mas sempre delimitada pela escola.
    if user['role']=='aluno':
        raise HTTPException(403,'O acervo completo é exclusivo dos educadores. Use Praticar.')
    condition,args=question_visibility(user,school)
    conditions=[condition]
    if status:conditions.append('q.status=?');args.append(status)
    if q:
        conditions.append('(q.title LIKE ? OR q.context LIKE ? OR q.prompt LIKE ? OR q.topic LIKE ?)')
        args += [f'%{q[:80]}%']*4
    if year:conditions.append('q.year=?');args.append(year)
    if area:
        sites=[school] if school else allowed_schools(user)
        conditions.append('(q.area=? OR q.discipline=? OR EXISTS (SELECT 1 FROM question_school_classifications sc '
                          'WHERE sc.question_id=q.id AND sc.discipline=? AND sc.school_id IN ('+
                          ','.join('?' for _ in sites)+')))')
        args.extend([area,area,area]+sites)
    if subject:
        sites=[school] if school else allowed_schools(user)
        conditions.append('(q.discipline=? OR EXISTS (SELECT 1 FROM question_school_classifications sc '
                          'WHERE sc.question_id=q.id AND sc.discipline=? AND sc.school_id IN ('+
                          ','.join('?' for _ in sites)+')) )')
        args.extend([subject,subject]+sites)
    if topic:
        sites=[school] if school else allowed_schools(user)
        conditions.append('(q.topic LIKE ? OR EXISTS (SELECT 1 FROM question_school_classifications sc '
                          'WHERE sc.question_id=q.id AND sc.topic LIKE ? AND sc.school_id IN ('+
                          ','.join('?' for _ in sites)+')))')
        args.extend(['%'+topic[:100]+'%']*2+sites)
    if difficulty:
        sites=[school] if school else allowed_schools(user)
        conditions.append('(q.difficulty=? OR EXISTS (SELECT 1 FROM question_school_classifications sc '
                          'WHERE sc.question_id=q.id AND sc.difficulty=? AND sc.school_id IN ('+
                          ','.join('?' for _ in sites)+')))')
        args.extend([difficulty,difficulty]+sites)
    if source:conditions.append('q.source=?');args.append(source)
    if rights_status:conditions.append('q.rights_status=?');args.append(rights_status)
    if creator_id:
        if user['role']!='coord':raise HTTPException(403,'Filtro por autor exclusivo da coordenação.')
        conditions.append('q.creator_id=?');args.append(creator_id)
    if scope:
        if scope not in ('central','escola'):raise HTTPException(422,'Escopo inválido.')
        conditions.append('q.school_id IS NULL' if scope=='central' else 'q.school_id IS NOT NULL')
    where=' WHERE '+' AND '.join(conditions)
    joins=' LEFT JOIN users author ON author.id=q.creator_id'
    total=one('SELECT COUNT(*) AS n FROM questions q'+where,args)['n']
    results=rows("""SELECT q.id,q.source,q.year,q.question_number,q.area,q.discipline,q.language,
            q.title,q.context,q.prompt,q.alternatives_json,q.media_json,q.topic,q.difficulty,
            q.status,q.rights_status,q.source_url,q.correct_letter,q.school_id,q.creator_id,
            author.name creator_name
            FROM questions q"""+joins+where+
            ' ORDER BY q.year DESC,q.question_number ASC,q.imported_at DESC,q.id LIMIT ? OFFSET ?',
            args+[limit,(page-1)*limit])
    for item in results:
        item['alternatives']=json.loads(item.pop('alternatives_json'))
        item['media']=json.loads(item.pop('media_json'))
        question_school_details(item,user,school)
    return {'total':total,'page':page,'limit':limit,'items':results}

@app.get('/api/questions/stats')
def question_stats(school:str='',user=Depends(require('coord','prof'))):
    where,args=question_visibility(user,school)
    where=' WHERE '+where
    return {'total':one('SELECT COUNT(*) n FROM questions q'+where,args)['n'],
            'enem':one('SELECT COUNT(*) n FROM questions q'+where+" AND q.source='ENEM API'",args)['n'],
            'ai':one('SELECT COUNT(*) n FROM questions q'+where+" AND (q.source='Cognix LLM' OR q.source LIKE 'Cognix IA%')",args)['n'],
            'review':one('SELECT COUNT(*) n FROM questions q'+where+" AND q.status='review'",args)['n'],
            'published':one('SELECT COUNT(*) n FROM questions q'+where+" AND q.status='published'",args)['n'],
            'by_source':rows('SELECT q.source source,COUNT(*) n FROM questions q'+where+' GROUP BY q.source ORDER BY n DESC',args),
            'by_status':rows('SELECT q.status status,COUNT(*) n FROM questions q'+where+' GROUP BY q.status ORDER BY n DESC',args),
            'by_subject':rows('SELECT q.discipline discipline,COUNT(*) n FROM questions q'+where+' GROUP BY q.discipline ORDER BY n DESC',args),
            'by_difficulty':rows('SELECT q.difficulty difficulty,COUNT(*) n FROM questions q'+where+' GROUP BY q.difficulty ORDER BY n DESC',args)}

@app.get('/api/questions/{qid}')
def question_detail(qid:str,school:str='',user=Depends(require('coord','prof'))):
    visibility,args=question_visibility(user,school)
    q=one('SELECT q.* FROM questions q WHERE q.id=? AND '+visibility,[qid]+args)
    if not q:raise HTTPException(404,'Questão indisponível neste perfil ou escola.')
    q['alternatives']=json.loads(q.pop('alternatives_json'))
    q['media']=json.loads(q.pop('media_json'))
    return question_school_details(q,user,school)

@app.get('/api/questions/{qid}/metadata')
def question_metadata(qid:str,school:str='',user=Depends(require('coord'))):
    visibility,args=question_visibility(user,school)
    q=one("""SELECT id,source,source_key,school_id,discipline,area,topic,difficulty,status,
            rights_status,year,question_number,creator_id FROM questions q WHERE q.id=? AND """+visibility,
          [qid]+args)
    if not q:raise HTTPException(404,'Questão indisponível nesta escola.')
    return question_school_details(q,user,school)

@app.patch('/api/questions/{qid}')
def review_question(qid:str,data:ReviewInput,user=Depends(require('coord'))):
    if data.status not in ('review','published','archived'):raise HTTPException(422,'Status inválido.')
    if data.status=='published' and data.rights_status not in ('authorized','demo'):
        raise HTTPException(422,'Para publicar, valide os direitos de reprodução e marque autorizado.')
    visibility,args=question_visibility(user,'')
    current=one('SELECT q.discipline,q.school_id FROM questions q WHERE q.id=? AND '+visibility,[qid]+args)
    if not current:raise HTTPException(404,'Questão não encontrada nesta escola.')
    # Não autorizar alteração de catálogo global por uma coordenação local.
    # A revisão global precisa de uma etapa de curadoria central independente.
    if current['school_id'] is None:
        raise HTTPException(403,'Acervo central somente para consulta. Revisões globais são de responsabilidade da curadoria central.')
    with session() as db:
        result=db.execute("""UPDATE questions SET status=?,rights_status=?,discipline=?,topic=?,difficulty=? WHERE id=?""",
                          (data.status,data.rights_status,data.discipline.strip(),data.topic.strip(),data.difficulty.strip(),qid))
        if not result.rowcount:raise HTTPException(404,'Questão não encontrada.')
        db.execute('INSERT INTO activity_log(user_id,action) VALUES(?,?)',(user['id'],f'Revisou questão {qid} → {data.status}'))
    return {'ok':True}

@app.post('/api/imports/enem')
def start_import(request:Request, tasks:BackgroundTasks,year:str='2023',user=Depends(require('coord'))):
    if year!='todos' and (not year.isdigit() or not 2009<=int(year)<=2023):
        raise HTTPException(422,'Ano inválido (2009–2023).')
    if one("SELECT id FROM import_jobs WHERE state IN ('pending','running') LIMIT 1"):
        raise HTTPException(409,'Uma importação já está em andamento.')
    job=secrets.token_hex(12)
    with session() as db:db.execute('INSERT INTO import_jobs(id,year,state) VALUES (?,?,?)',(job,year,'pending'))
    tasks.add_task(run_job,job,year)
    return {'job_id':job,'state':'pending'}

@app.get('/api/imports')
def imports(user=Depends(require('coord'))):
    return rows('SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT 10')

def allowed_subject(user,class_id,subject):
    try:
        assert_class(user,class_id)
        if user['role']=='coord':return True
        return bool(one('SELECT id FROM teaching_assignments WHERE class_id=? AND teacher_id=? AND subject=?',
                        (class_id,user['id'],subject)))
    except HTTPException:return False

def validate_exam_questions(db,user,class_id,subject,ids):
    if not allowed_subject(user,class_id,subject):
        raise HTTPException(403,'Disciplina não atribuída nesta turma.')
    if not ids or len(ids)>100 or len(ids)!=len(set(ids)):
        raise HTTPException(422,'Escolha entre 1 e 100 questões distintas.')
    cls=db.execute('SELECT school_id FROM classes WHERE id=?',(class_id,)).fetchone()
    if cls is None:raise HTTPException(404,'Turma não encontrada.')
    for qid in ids:
        q=db.execute('SELECT status,rights_status,discipline,creator_id,school_id FROM questions WHERE id=?',(qid,)).fetchone()
        school_tag=db.execute('''SELECT discipline FROM question_school_classifications
             WHERE school_id=? AND question_id=?''',(cls['school_id'],qid)).fetchone()
        classified=q and (q['discipline']==subject or (school_tag and school_tag['discipline']==subject))
        if not q or not classified or q['status']!='published' or q['rights_status'] not in ('authorized','demo'):
            raise HTTPException(422,f'Questão {qid} ainda não foi liberada para provas.')
        rec=db.execute('''SELECT c.kind,c.owner_id,c.school_id FROM question_records r
                 JOIN question_collections c ON c.id=r.collection_id WHERE r.question_id=?''',(qid,)).fetchone()
        if rec:
            if rec['kind']=='personal' and rec['owner_id']!=user['id']:
                raise HTTPException(403,'Questão particular de outro professor.')
            if rec['kind']=='school' and rec['school_id']!=cls['school_id']:
                raise HTTPException(403,'Questão institucional de outra escola.')
        elif (q['school_id'] and q['school_id']!=cls['school_id']) or (q['creator_id'] and user['role']=='prof' and q['creator_id']!=user['id']):
            raise HTTPException(403,'Questão legada de outra escola ou outro professor.')
    return cls['school_id']

def freeze_exam_item(db,exam_id,qid):
    q=db.execute('''SELECT title,context,prompt,alternatives_json,media_json,correct_letter,
                        discipline,topic,difficulty,source FROM questions WHERE id=?''',(qid,)).fetchone()
    rev=db.execute('SELECT version FROM question_records WHERE question_id=?',(qid,)).fetchone()
    db.execute('''INSERT INTO exam_item_snapshots(exam_id,question_id,snapshot_json,question_version)
                  VALUES(?,?,?,?)''',(exam_id,qid,json.dumps(dict(q),ensure_ascii=False),rev['version'] if rev else 1))

def exam_question_edits(body):
    if any(qid not in body.question_ids or not isinstance(prompt,str)
           or len(prompt.strip())<15 or len(prompt)>5000
           for qid,prompt in body.question_edits.items()):
        raise HTTPException(422,'Edição de enunciado inválida. Mantenha pelo menos 15 caracteres.')
    return {key:value.strip() for key,value in body.question_edits.items()}

@app.post('/api/exams')
def create_exam(body:ExamInput,user=Depends(require('coord','prof'))):
    selected=body.question_ids
    edits=exam_question_edits(body)
    with session() as db:
        school=validate_exam_questions(db,user,body.class_id,body.subject,selected)
        id=secrets.token_hex(12)
        db.execute('''INSERT INTO exam_sets(id,creator_id,class_id,subject,title,total_points,
            generation_mode,configuration_json) VALUES(?,?,?,?,?,?,?,?)''',
                   (id,user['id'],body.class_id,body.subject,body.title,body.total_points,'reviewed-bank',
                    json.dumps({'school_id':school,'requested_count':len(selected),
                                'instructions':body.instructions,'question_edits':edits},ensure_ascii=False)))
        base,extra=divmod(round(body.total_points*100),len(selected))
        for pos,qid in enumerate(selected):
            db.execute('INSERT INTO exam_items(exam_id,question_id,position,points) VALUES(?,?,?,?)',
                (id,qid,pos,(base+(1 if pos<extra else 0))/100))
            freeze_exam_item(db,id,qid)
    return {'ok':True,'id':id}

@app.patch('/api/exams/{exam_id}')
def update_exam(exam_id:str,body:ExamInput,user=Depends(require('coord','prof'))):
    edits=exam_question_edits(body)
    with session() as db:
        exam=db.execute('SELECT * FROM exam_sets WHERE id=?',(exam_id,)).fetchone()
        if not exam or exam['creator_id']!=user['id']:
            raise HTTPException(404,'Prova não encontrada ou não pertence à sua conta.')
        if exam['class_id']!=body.class_id or exam['subject']!=body.subject:
            raise HTTPException(422,'Para mudar turma ou disciplina, crie outra prova.')
        school=validate_exam_questions(db,user,body.class_id,body.subject,body.question_ids)
        db.execute('''UPDATE exam_sets SET title=?,total_points=?,configuration_json=? WHERE id=?''',
           (body.title,body.total_points,json.dumps({'school_id':school,
            'requested_count':len(body.question_ids),'instructions':body.instructions,
            'question_edits':edits},
            ensure_ascii=False),exam_id))
        db.execute('DELETE FROM exam_items WHERE exam_id=?',(exam_id,))
        base,extra=divmod(round(body.total_points*100),len(body.question_ids))
        for pos,qid in enumerate(body.question_ids):
            db.execute('INSERT INTO exam_items(exam_id,question_id,position,points) VALUES(?,?,?,?)',
                       (exam_id,qid,pos,(base+(1 if pos<extra else 0))/100))
            freeze_exam_item(db,exam_id,qid)
    return {'ok':True,'id':exam_id}

@app.delete('/api/exams/{exam_id}')
def delete_exam(exam_id:str,user=Depends(require('coord','prof'))):
    with session() as db:
        exam=db.execute('SELECT creator_id,class_id,subject FROM exam_sets WHERE id=?',(exam_id,)).fetchone()
        if not exam or exam['creator_id']!=user['id'] or not allowed_subject(user,exam['class_id'],exam['subject']):
            raise HTTPException(404,'Prova não encontrada ou sem permissão.')
        db.execute('DELETE FROM exam_sets WHERE id=?',(exam_id,))
    return {'ok':True}

@app.post('/api/exams/{exam_id}/link-assessment')
def link_exam_assessment(exam_id:str,body:ExamApplication,user=Depends(require('coord','prof'))):
    """Vincula a prova a uma avaliação registrada, sem alterar notas."""
    with session() as db:
        exam=db.execute('SELECT * FROM exam_sets WHERE id=?',(exam_id,)).fetchone()
        if not exam or exam['creator_id']!=user['id'] or not allowed_subject(user,exam['class_id'],exam['subject']):
            raise HTTPException(404,'Prova não encontrada ou sem permissão.')
        existing=db.execute('''SELECT 1 FROM assessments
            WHERE class_id=? AND subject=? AND name=?''',
            (exam['class_id'],exam['subject'],body.assessment)).fetchone()
        if not existing:
            raise HTTPException(422,'A avaliação precisa estar cadastrada pela coordenação antes do vínculo.')
        db.execute('UPDATE exam_sets SET applied_assessment=? WHERE id=?',(body.assessment,exam_id))
    return {'ok':True,'assessment':body.assessment}

@app.get('/api/exams')
def list_exams(school:str='',user=Depends(require('prof','coord'))):
    if school:assert_school(user,school)
    if user['role']=='coord':
        join_filter='''JOIN coordinator_schools cs ON cs.school_id=c.school_id
          WHERE cs.user_id=? AND (?='' OR c.school_id=?)'''
    else:
        join_filter='''JOIN teaching_assignments ta ON ta.class_id=c.id AND ta.subject=e.subject
          JOIN school_memberships m ON m.user_id=ta.teacher_id AND m.school_id=c.school_id AND m.status='active'
          WHERE e.creator_id=? AND ta.teacher_id=? AND (?='' OR c.school_id=?)'''
    params=[user['id'],school,school] if user['role']=='coord' else [user['id'],user['id'],school,school]
    return rows('''SELECT DISTINCT e.*,c.name class_name,s.name school_name,
          (SELECT COUNT(*) FROM exam_items i WHERE i.exam_id=e.id) total
       FROM exam_sets e JOIN classes c ON c.id=e.class_id JOIN schools s ON s.id=c.school_id '''+
       join_filter+''' ORDER BY e.created_at DESC''',params)

@app.get('/api/exams/{exam_id}')
def exam_detail(exam_id:str,user=Depends(require('coord','prof'))):
    exam=one('SELECT * FROM exam_sets WHERE id=?',(exam_id,))
    if not exam:raise HTTPException(404,'Prova não encontrada.')
    if user['role']=='coord':assert_class(user,exam['class_id'])
    elif exam['creator_id']!=user['id'] or not allowed_subject(user,exam['class_id'],exam['subject']):
        raise HTTPException(404,'Prova não encontrada.')
    items=rows('''SELECT q.id,q.title,q.context,q.prompt,q.alternatives_json,q.media_json,q.correct_letter,
          q.discipline,q.topic,q.difficulty,q.source,i.points,s.snapshot_json
       FROM exam_items i JOIN questions q ON q.id=i.question_id
       LEFT JOIN exam_item_snapshots s ON s.exam_id=i.exam_id AND s.question_id=i.question_id
       WHERE i.exam_id=? ORDER BY i.position''',(exam_id,))
    try:cfg=json.loads(exam.get('configuration_json') or '{}')
    except (ValueError,TypeError):cfg={}
    edits=cfg.get('question_edits') or {}
    for i in items:
        frozen=json.loads(i.pop('snapshot_json') or '{}')
        i.update(frozen)
        i['alternatives']=json.loads(i.pop('alternatives_json'));i['media']=json.loads(i.pop('media_json'))
        if i['id'] in edits:i['prompt']=edits[i['id']]
    return {'exam':exam,'items':items}

@app.post('/api/practice/answer')
def practice_answer(body:AttemptInput,user=Depends(require('aluno'))):
    q=one("SELECT id,correct_letter,discipline,rights_status,school_id,creator_id FROM questions WHERE id=? AND status='published'",(body.question_id,))
    if not q or q['rights_status'] not in ('authorized','demo'):raise HTTPException(404,'Questão indisponível.')
    if not body.school_id:raise HTTPException(422,'Escola obrigatória para responder.')
    assert_school(user,body.school_id)
    if q['creator_id'] or (q['school_id'] and q['school_id']!=body.school_id):
        raise HTTPException(404,'Questão não disponível para prática.')
    assert_subject(user,q['discipline'],body.school_id)
    chosen=body.letter.strip().upper()
    if chosen not in ('A','B','C','D','E'):raise HTTPException(422,'Alternativa inválida.')
    ok=int(chosen==q['correct_letter'])
    with session() as db: db.execute('INSERT INTO attempts(id,user_id,question_id,chosen_letter,correct,school_id) VALUES(?,?,?,?,?,?)',
                          (secrets.token_hex(12),user['id'],q['id'],chosen,ok,body.school_id))
    return {'correct':bool(ok),'correct_letter':q['correct_letter']}

@app.get('/api/practice/progress')
def practice_progress(user=Depends(require('aluno'))):
    n=one('SELECT COUNT(*) n, COALESCE(SUM(correct),0) hits FROM attempts WHERE user_id=?',(user['id'],))
    n['accuracy']=round(100*n['hits']/n['n'],1) if n['n'] else 0
    return n

@app.get('/api/grades')
def read_grades(class_id:str,subject:str='',user=Depends(current_user)):
    if user['role']=='aluno':
        if not one('SELECT 1 FROM enrollments WHERE user_id=? AND class_id=?',(user['id'],class_id)):
            raise HTTPException(403,'Turma não vinculada.')
        return rows('SELECT assessment,score,subject FROM grades WHERE class_id=? AND student_id=?',
                    (class_id,user['id']))
    if user['role']=='prof' and not (subject and allowed_subject(user,class_id,subject)):
        raise HTTPException(403,'Selecione uma disciplina que você leciona.')
    if user['role']=='coord':assert_class(user,class_id)
    filt=' AND subject=?' if subject else ''
    return rows('''SELECT g.id,g.subject,g.assessment,g.score,u.name student_name,g.student_id FROM grades g
      JOIN users u ON u.id=g.student_id WHERE g.class_id=?'''+filt+' ORDER BY student_name,assessment',
      [class_id]+([subject] if subject else []))

@app.post('/api/grades')
def save_grade(body:GradeInput,user=Depends(require('coord'))):
    if not math.isfinite(body.score):raise HTTPException(422,'A nota deve ser um número finito.')
    if not allowed_subject(user,body.class_id,body.subject): raise HTTPException(403,'Sem vínculo com esta disciplina.')
    if not one('SELECT 1 FROM enrollments WHERE class_id=? AND user_id=?',(body.class_id,body.student_id)):
        raise HTTPException(422,'Aluno não matriculado na turma.')
    with session() as db:
        previous=db.execute('SELECT score FROM grades WHERE class_id=? AND subject=? AND student_id=? AND assessment=?',
            (body.class_id,body.subject,body.student_id,body.assessment.strip())).fetchone()
        registered=db.execute('SELECT topics_json FROM assessments WHERE class_id=? AND subject=? AND name=?',
            (body.class_id,body.subject,body.assessment.strip())).fetchone()
        if not registered:
            raise HTTPException(422,'Avaliação não cadastrada. Use Cronogramas para cadastrar.')
        try: allowed_topics=json.loads(registered['topics_json'])
        except (ValueError,TypeError): allowed_topics=[]
        if body.topic_scores is not None:
            unknown=set(body.topic_scores)-set(allowed_topics)
            if unknown:raise HTTPException(422,'Tópicos não cadastrados nesta avaliação: '+', '.join(sorted(unknown)))
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>10
                   for v in body.topic_scores.values()):
                raise HTTPException(422,'Notas por tópico devem estar entre 0 e 10.')
        db.execute('''INSERT INTO grades(id,class_id,subject,student_id,assessment,score) VALUES (?,?,?,?,?,?)
          ON CONFLICT(class_id,subject,student_id,assessment) DO UPDATE SET score=excluded.score''',
          (secrets.token_hex(12),body.class_id,body.subject,body.student_id,body.assessment.strip(),body.score))
        # Só atribuir nota de tópico quando houver evidência explícita, ou quando a
        # própria avaliação tratar de exatamente um tópico. Nunca dividir uma
        # nota composta entre tópicos por suposição.
        topic_values=body.topic_scores if body.topic_scores is not None else (
            {allowed_topics[0]:body.score} if len(allowed_topics)==1 else {})
        for topic,score in topic_values.items():
            db.execute('''INSERT INTO grade_topics(class_id,subject,student_id,assessment,topic,score)
              VALUES(?,?,?,?,?,?) ON CONFLICT(class_id,subject,student_id,assessment,topic)
              DO UPDATE SET score=excluded.score''',
              (body.class_id,body.subject,body.student_id,body.assessment.strip(),topic,score))
        school=db.execute('SELECT school_id FROM classes WHERE id=?',(body.class_id,)).fetchone()['school_id']
        db.execute('INSERT INTO grade_audit(coordinator_id,school_id,class_id,student_id,subject,assessment,previous_score,new_score) VALUES(?,?,?,?,?,?,?,?)',
          (user['id'],school,body.class_id,body.student_id,body.subject,body.assessment.strip(),previous['score'] if previous else None,body.score))
    return {'ok':True,'topics_updated':list(topic_values),
            'note':'Notas por tópico só são atualizadas com evidência específica.' if not topic_values and len(allowed_topics)>1 else 'Nota e evidências gravadas.'}

@app.get('/api/class/{class_id}/students')
def class_students(class_id:str,user=Depends(require('coord','prof'))):
    assert_class(user,class_id)
    return rows('''SELECT u.id,u.name,u.email FROM users u JOIN enrollments e ON u.id=e.user_id
           WHERE e.class_id=? ORDER BY u.name''',(class_id,))

@app.get('/api/overview')
def overview(school:str|None=None,user=Depends(current_user)):
    classes=visible_classes(user,school)
    class_ids=[x['id'] for x in classes]
    q_where,q_args=scoped_question_sql(user,school)
    questions=one('SELECT COUNT(*) n FROM questions WHERE '+q_where,q_args)['n']
    exams=one('SELECT COUNT(*) n FROM exam_sets WHERE creator_id=?',(user['id'],))['n']
    if user['role']=='prof':
        assignments=rows('''SELECT a.subject,c.name class_name,c.id class_id,s.name school_name,s.id school_id
          FROM teaching_assignments a JOIN classes c ON c.id=a.class_id JOIN schools s ON s.id=c.school_id
          JOIN school_memberships m ON m.user_id=a.teacher_id AND m.school_id=c.school_id AND m.status='active'
          WHERE a.teacher_id=? AND (? IS NULL OR c.school_id=?) ORDER BY s.id,a.subject,c.name''',(user['id'],school,school))
    elif user['role']=='coord':
        assignments=rows('''SELECT a.subject,c.name class_name,c.id class_id,s.name school_name,u.name teacher_name
          FROM teaching_assignments a JOIN users u ON u.id=a.teacher_id
          JOIN classes c ON c.id=a.class_id JOIN schools s ON s.id=c.school_id
          JOIN coordinator_schools z ON z.school_id=s.id WHERE z.user_id=?
          AND (? IS NULL OR s.id=?) ORDER BY s.id,a.subject,c.name''',(user['id'],school,school))
    else:assignments=[]
    return {'classes':len(class_ids),'schools':len({x['school_id'] for x in classes}),
       'questions':questions,'exams':exams,'assignments':assignments}

from .studio import router as studio_router
from .ai import router as ai_router
app.include_router(studio_router)
app.include_router(ai_router)

from .random_exam import router as random_exam_router
app.include_router(random_exam_router)
from .exam_export import router as export_router
app.include_router(export_router)
from .pedagogy import router as pedagogy_router
from .learning import router as learning_router
from .evidence import router as evidence_router
app.include_router(pedagogy_router)
app.include_router(learning_router)
app.include_router(evidence_router)
from .teacher_tools import router as teacher_tools_router
app.include_router(teacher_tools_router)
from .error_notebook import router as error_notebook_router
app.include_router(error_notebook_router)
from .question_bank import router as question_bank_router
app.include_router(question_bank_router)
from .accounts_v10 import router as accounts_v10_router
app.include_router(accounts_v10_router)

