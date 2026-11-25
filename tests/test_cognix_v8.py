"""Testes de regressão: contas fictícias, separação de escolas e provas por banco."""
from pathlib import Path
import os
import json
import shutil
import tempfile
import zipfile
import io

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
ISOLATED = Path(tempfile.mkdtemp(prefix='cognix-v8-tests-')) / 'test.sqlite3'
shutil.copy2(ROOT / 'data' / 'cognix.sqlite3', ISOLATED)
os.environ['COGNIX_DB'] = str(ISOLATED)
from backend.main import app  # noqa: E402
from backend.db import one, session  # noqa: E402
from backend.import_enem import sync_year  # noqa: E402

CREDENTIALS = {}
for line in (ROOT / 'data' / 'ACESSOS-DEMO-LOCAL.txt').read_text(encoding='utf8').splitlines():
    if ' | ' in line:
        mail, password = line.split(' | ', 1)
        if '@' in mail:
            CREDENTIALS[mail] = password


def sign_in(c, mail):
    response = c.post('/api/auth/login', json={'email': mail, 'password': CREDENTIALS[mail]})
    assert response.status_code == 200, response.text


def test_permissions_by_school():
    with TestClient(app) as teacher, TestClient(app) as coordinator:
        assert teacher.get('/api/me').status_code == 401
        sign_in(teacher, 'rafael.monteiro@cognix.test')
        sign_in(coordinator, 'coordenacao@cognix.test')
        me = teacher.get('/api/me').json()
        assert me['subjects_by_school'] == {'escola-x': ['Matemática'], 'escola-y': ['Física'],
                                             'escola-z': ['Física', 'Matemática']}
        assert len(coordinator.get('/api/me').json()['schools']) == 1
        assert coordinator.get('/api/me').json()['schools'][0]['id'] == 'escola-x'
        assert coordinator.get('/api/classes?school=escola-y').status_code == 403
        assert coordinator.get('/api/exam-builder/options?class_id=y-1b&subject=Física').status_code == 403
        for cls, subject in [('x-1b', 'Física'), ('y-1b', 'Matemática')]:
            assert teacher.get('/api/exam-builder/options', params={'class_id': cls, 'subject': subject}).status_code == 403
            assert teacher.post('/api/exam-builder/random', json={'class_id': cls, 'subject': subject,
                                     'title': 'Tentativa não autorizada'}).status_code == 403


def test_random_generator_and_export():
    with TestClient(app) as c:
        sign_in(c, 'rafael.monteiro@cognix.test')
        for cls, subject in [('x-1b', 'Matemática'), ('y-1b', 'Física'),
                             ('z-3a', 'Matemática'), ('z-3a', 'Física')]:
            options = c.get('/api/exam-builder/options', params={'class_id': cls, 'subject': subject})
            assert options.status_code == 200 and options.json()['total'] >= 6
            data = {'class_id': cls, 'subject': subject, 'title': 'Avaliação demonstrativa',
                    'count': 6, 'easy_percent': 40, 'medium_percent': 40, 'hard_percent': 20,
                    'types': ['multipla', 'vf', 'discursiva'], 'total_points': 10}
            response = c.post('/api/exam-builder/random', json=data)
            assert response.status_code == 200, response.text
            exam_id = response.json()['id']
            details = c.get('/api/exams/' + exam_id).json()
            questions = details['items']
            assert len(questions) == 6
            assert len(set(q['id'] for q in questions)) == len(questions)
            assert all(q['discipline'] == subject for q in questions)
            assert abs(sum(q['points'] for q in questions) - 10) < 0.001
            docx = c.get('/api/exams/' + exam_id + '/docx?answers=1')
            assert docx.status_code == 200 and zipfile.is_zipfile(io.BytesIO(docx.content))
            assert c.get('/api/exams').status_code == 200


def test_small_pool_and_zero_weight_are_explicit():
    with TestClient(app) as c:
        sign_in(c, 'rafael.monteiro@cognix.test')
        response = c.post('/api/exam-builder/random', json={'class_id': 'x-1b', 'subject': 'Matemática',
            'title': 'Mais questões do que existem', 'count': 20, 'total_points': 10})
        assert response.status_code == 200 and response.json()['missing'] > 0
        bad = c.post('/api/exam-builder/random', json={'class_id': 'x-1b', 'subject': 'Matemática',
            'title': 'Percentual zerado', 'easy_percent': 0, 'medium_percent': 0, 'hard_percent': 0})
        assert bad.status_code == 422


def test_import_compatibility():
    item = {'year': 2021, 'index': 39099, 'title': 'Item de importação simulado',
        'context': 'Exemplo sintético usado exclusivamente para validar a API externa.',
        'files': [], 'alternativesIntroduction': 'Escolha a opção', 'correctAlternative': 'B',
        'alternatives': [{'letter': 'A', 'text': '1'}, {'letter': 'B', 'text': '2'}]}
    def handler(request):
        assert request.url.path.endswith('/2021/questions')
        return httpx.Response(200, json={'metadata': {'total': 1, 'hasMore': False}, 'questions': [item]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as external:
        assert sync_year(2021, 'https://simulado.invalid/v1', client=external) == 1
        assert sync_year(2021, 'https://simulado.invalid/v1', client=external) == 1
    assert one("SELECT COUNT(*) n FROM questions WHERE source='ENEM API' AND question_number=39099")['n'] == 1
    # Importação não publica automaticamente conteúdo sem direitos e sem classificação.
    assert one("SELECT status FROM questions WHERE source='ENEM API' AND question_number=39099")['status'] == 'review'


def test_studio_classico_auth():
    with TestClient(app) as c:
        assert c.get('/studio?school=escola-x').status_code == 401
        sign_in(c, 'rafael.monteiro@cognix.test')
        for school in ('escola-x', 'escola-y', 'escola-z'):
            r = c.get('/studio', params={'school': school})
            assert r.status_code == 200 and 'COGNIX_BOOT' in r.text
            assert 'Sorteio rápido sem IA' in r.text
        assert c.get('/studio?school=escola-inexistente').status_code == 403


def test_coordinator_question_bank_admin_scope_and_filters():
    """Coordenação X: acervo ENEM/IA completo para consulta, jamais dados privados de Y."""
    from backend.db import session, one
    from backend.studio import _question_projection
    import json
    unique_id='enem-administrativo-teste'
    with session() as db:
        db.execute('''INSERT OR IGNORE INTO questions
         (id,source,source_key,year,question_number,area,discipline,title,context,prompt,
          alternatives_json,media_json,correct_letter,topic,difficulty,status,rights_status)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (unique_id,'ENEM API','admin-test:2023:7777',2023,7777,'Linguagens','Artes','Questão ENEM fictícia só para teste',
           'Contexto do ENEM inventado','Qual a opção correta?',
           json.dumps([{'letter':'A','text':'Alternativa A'},{'letter':'B','text':'Alternativa B'}]),
           '[]','B','Arte brasileira','média','review','pending'))
    own_x=one("SELECT id,creator_id,discipline FROM questions WHERE school_id='escola-x' AND creator_id IS NOT NULL LIMIT 1")
    own_y=one("SELECT id,creator_id,discipline FROM questions WHERE school_id='escola-y' AND creator_id IS NOT NULL LIMIT 1")
    assert own_x and own_y
    with TestClient(app) as x,TestClient(app) as y,TestClient(app) as teacher:
        sign_in(x,'coordenacao@cognix.test')
        sign_in(y,'coordenacao.y@cognix.test')
        sign_in(teacher,'rafael.monteiro@cognix.test')
        en=x.get('/api/questions/'+unique_id,params={'school':'escola-x'})
        assert en.status_code==200,en.text
        assert en.json()['correct_letter']=='B'
        assert en.json()['prompt']=='Qual a opção correta?'
        assert x.get('/api/questions',params={'school':'escola-x','source':'ENEM API','year':2023,'subject':'Artes'}).json()['total']>=1
        assert x.get('/api/questions/stats',params={'school':'escola-x'}).json()['ai']>0
        local=x.get('/api/questions/'+own_x['id'],params={'school':'escola-x'})
        assert local.status_code==200,local.text
        assert local.json()['correct_letter']
        assert x.get('/api/questions/'+own_y['id'],params={'school':'escola-x'}).status_code==404
        assert x.get('/api/questions/'+own_y['id']).status_code==404
        assert x.get('/api/questions/'+own_y['id']+'/metadata').status_code==404
        assert y.get('/api/questions/'+own_x['id']).status_code==404
        assert x.get('/api/questions',params={'school':'escola-y'}).status_code==403
        assert teacher.get('/api/questions/'+unique_id,params={'school':'escola-x'}).status_code==404
        assert own_y['id'] not in [q['id'] for q in x.get('/api/questions',params={'school':'escola-x','creator_id':own_y['creator_id']}).json()['items']]
        filtered=x.get('/api/questions',params={'school':'escola-x','scope':'escola','source':'Cognix IA · exemplo fictício'})
        assert filtered.status_code==200
        assert all(q['school_id']=='escola-x' for q in filtered.json()['items'])
        assert all(q['prompt'] or q['context'] for q in filtered.json()['items'])
        assert x.patch('/api/questions/'+unique_id,json={'status':'published','rights_status':'authorized','discipline':'Artes'}).status_code==403
        assert x.get('/api/questions',params={'school':'escola-x','scope':'invalid'}).status_code==422
        projected=_question_projection({'role':'coord','id':'coord-demo'},'escola-x')
        assert all(q['disciplina']!='Artes' for q in projected)  # unpublished ENEM not projected
        assert all(q['centralId']!=own_y['id'] for q in projected)


def test_new_plan_registration_and_school_only_account_creation():
    """Autocadastro somente individual; contas escolares pela coordenação vinculada."""
    with TestClient(app) as visitor, TestClient(app) as cx, TestClient(app) as cy:
        assert visitor.get('/api/public/schools').status_code == 200
        base = {'name':'Docente Novo Individual','email':'individual.novo@cognix.test',
                'password':'senhaFortissima123'}
        for forbidden in ({**base,'plan':'school'},
                          {**base,'plan':'individual','role':'aluno'},
                          {**base,'plan':'individual','role':'coord'}):
            answer=visitor.post('/api/auth/register',json=forbidden)
            assert answer.status_code in (403,422),answer.text
        assert one('SELECT 1 FROM users WHERE email=?',(base['email'],)) is None
        created=visitor.post('/api/auth/register',json={**base,'plan':'individual'})
        assert created.status_code == 200,created.text
        me=visitor.get('/api/me').json()
        assert me['user']['role']=='prof'
        assert me['user']['account_plan']=='individual'
        assert me['schools']==[] and me['subjects_by_school']=={}
        assert visitor.post('/api/team/accounts',json={**base,'role':'prof','school_id':'escola-x'}).status_code == 403
        sign_in(cx,'coordenacao@cognix.test')
        sign_in(cy,'coordenacao.y@cognix.test')
        school_prof={'name':'Professora Escolar Nova','email':'docente.escolar@cognix.test',
                     'password':'senhaInstitucional123','role':'prof','school_id':'escola-x'}
        assert cy.post('/api/team/accounts',json=school_prof).status_code==403
        r=cx.post('/api/team/accounts',json=school_prof)
        assert r.status_code==201,r.text
        assert r.json()['account_plan']=='school'
        school_teacher_id=r.json()['id']
        school_stu={'name':'Estudante Nova Escola X','email':'aluno.escolar@cognix.test',
                     'password':'senhaAluno1234','role':'aluno','school_id':'escola-x'}
        r=cx.post('/api/team/accounts',json=school_stu)
        assert r.status_code==201,r.text
        school_student_id=r.json()['id']
        school_coord={'name':'Coordenadora Auxiliar X','email':'coord.auxiliar@cognix.test',
                     'password':'senhaCoord1234','role':'coord','school_id':'escola-x'}
        assert cx.post('/api/team/accounts',json=school_coord).status_code==201
        team_x=cx.get('/api/team').json()
        team_y=cy.get('/api/team').json()
        assert school_teacher_id in [u['id'] for u in team_x['teachers']]
        assert school_teacher_id not in [u['id'] for u in team_y['teachers']]
        assert school_student_id in [u['id'] for u in team_x['students']]
        assert school_student_id not in [u['id'] for u in team_y['students']]
        # Atribuição pode ocorrer depois do cadastro escolar; outra escola é proibida.
        assert cx.post('/api/team/assign',json={'teacher_id':school_teacher_id,
                        'class_id':'x-3a','subject':'Física'}).status_code==200
        assert cy.post('/api/team/assign',json={'teacher_id':school_teacher_id,
                        'class_id':'y-3a','subject':'Física'}).status_code==403
        assert cx.post('/api/team/enroll',json={'student_id':school_student_id,
                        'class_id':'x-3a'}).status_code==200
        assert cy.post('/api/team/enroll',json={'student_id':school_student_id,
                        'class_id':'y-3a'}).status_code==403
        with TestClient(app) as teacher_login,TestClient(app) as student_login:
            assert teacher_login.post('/api/auth/login',json={'email':school_prof['email'],
                'password':school_prof['password']}).status_code==200
            assert teacher_login.get('/api/me').json()['subjects_by_school']['escola-x']==['Física']
            assert teacher_login.get('/api/classes?school=escola-y').status_code==403
            assert student_login.post('/api/auth/login',json={'email':school_stu['email'],
                'password':school_stu['password']}).status_code==200
            assert student_login.get('/api/classes?school=escola-y').status_code==403


def test_individual_affiliation_requires_approval_then_assignment():
    with TestClient(app) as prof,TestClient(app) as cx,TestClient(app) as cy:
        sign_in(prof,'rafael.monteiro@cognix.test')
        assert prof.get('/api/me').json()['user']['account_plan']=='individual'
        sign_in(cx,'coordenacao@cognix.test')
        sign_in(cy,'coordenacao.y@cognix.test')
        newcomer={'name':'Novo Professor de Física','email':'vinculo.novo@cognix.test',
                  'password':'senhaForte98765','plan':'individual'}
        with TestClient(app) as p:
            assert p.post('/api/auth/register',json=newcomer).status_code==200
            req=p.post('/api/affiliations/request',json={'school_id':'escola-y'})
            assert req.status_code==201,req.text
            assert p.get('/api/classes').json()==[]
            assert p.post('/api/affiliations/request',json={'school_id':'escola-y'}).status_code==409
            requests=cy.get('/api/team/join-requests').json()
            rid=next(x['id'] for x in requests if x['teacher_email']==newcomer['email'])
            assert rid not in [x['id'] for x in cx.get('/api/team/join-requests').json()]
            assert cx.post('/api/team/join-requests/'+rid,json={'decision':'approved'}).status_code==403
            assert cy.post('/api/team/join-requests/'+rid,json={'decision':'approved'}).status_code==200
            assert cy.post('/api/team/join-requests/'+rid,json={'decision':'approved'}).status_code==409
            me=p.get('/api/me').json()
            assert [s['id'] for s in me['schools']]==['escola-y']
            assert me['subjects_by_school']['escola-y']==[]
            uid=me['user']['id']
            assert cy.post('/api/team/assign',json={'teacher_id':uid,'class_id':'y-1b',
                         'subject':'Física'}).status_code==200
            assert p.get('/api/me').json()['subjects_by_school']['escola-y']==['Física']
            assert p.get('/api/classes?school=escola-x').status_code==403
            assert p.get('/api/exam-builder/options',params={'class_id':'y-1b',
                         'subject':'Matemática'}).status_code==403


def test_frontend_syntax_and_page_registry_regression():
    """A tela anterior travava por referências JS globais inexistentes."""
    import subprocess
    import shutil
    ui=ROOT/'frontend/js/app.js'
    html=ui.read_text(encoding='utf8')
    pedagogy=(ROOT/'frontend/js/pages/pedagogy.js').read_text(encoding='utf8')
    assert '...pedagogy.pages' in html
    assert 'trilha:trail' in pedagogy
    assert 'praticar:practice' in pedagogy
    assert 'provas,praticar,' not in html
    assert 'plan-individual' in html and 'plan-school' in html
    assert 'school-account-form' in html
    if shutil.which('node'):
        for file in (ui,ROOT/'frontend/js/pages/pedagogy.js'):
            subprocess.run(['node','--check',str(file)],check=True,capture_output=True)
