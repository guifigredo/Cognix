"""Execute: pytest -q tests"""
import json, os, tempfile, pathlib
from fastapi.testclient import TestClient
import httpx

# Definido antes do import do banco.
TEST_DB = pathlib.Path(tempfile.mkdtemp(prefix='cognix-test-'))/'test.sqlite3'
os.environ['COGNIX_DB']=str(TEST_DB)
os.environ['COGNIX_SETUP_CODE']='TESTE-COORDENACAO-SEGREDO-LONGO-123'
from backend.main import app
from backend.db import init_db, rows, one
from backend.import_enem import sync_year, normalize


def register(client,name,email,role='prof',invite=''):
    return client.post('/api/auth/register',json={'name':name,'email':email,'password':'senha-forte-2026','role':role,'invite':invite})


def test_auth_and_permissions():
    with TestClient(app) as a:
        assert a.get('/api/questions').status_code==401
        assert a.get('/api/team').status_code==401
        assert register(a,'Maria Coord','coord@example.org','coord','TESTE-COORDENACAO-SEGREDO-LONGO-123').status_code==200
        assert a.get('/api/team').status_code==200
        assert len(a.get('/api/schools').json())==3
        assert register(a,'Outra Coord','outra@example.org','coord','wrong').status_code==403
        with TestClient(app) as t:
            assert register(t,'Professor Teste','prof@example.org').status_code==200
            assert t.get('/api/team').status_code==403
            assert t.get('/api/classes').json()==[]
            tid=t.get('/api/me').json()['user']['id']
            with TestClient(app) as s:
                assert register(s,'Aluno Teste','aluno@example.org','aluno').status_code==200
                sid=s.get('/api/me').json()['user']['id']
                assert s.get('/api/classes').json()==[]
                assign=a.post('/api/team/assign',json={'teacher_id':tid,'class_id':'y-1b','subject':'Física'})
                assert assign.status_code==200, assign.text
                a.post('/api/team/assign',json={'teacher_id':tid,'class_id':'y-1b','subject':'Matemática'})
                assert t.get('/api/classes').json()[0]['subjects']==['Física','Matemática']
                a.post('/api/team/enroll',json={'student_id':sid,'class_id':'y-1b'})
                assert s.get('/api/classes').json()[0]['id']=='y-1b'
                assert s.get('/api/class/y-1b/students').status_code==403
                assert t.get('/api/class/y-1b/students').status_code==200
                assert t.post('/api/grades',json={'class_id':'y-1b','subject':'Geografia','student_id':sid,'assessment':'Prova 1','score':7.5}).status_code==403
                assert t.post('/api/grades',json={'class_id':'y-1b','subject':'Física','student_id':sid,'assessment':'Prova 1','score':7.5}).status_code==200
                assert s.get('/api/grades?class_id=y-1b').json()[0]['score']==7.5
                assert s.get('/api/grades?class_id=x-1b').status_code==403
                assert a.get('/api/classes').status_code==200
        assert a.post('/api/auth/logout').status_code==200
        assert a.get('/api/team').status_code==401
        assert a.post('/api/auth/login',json={'email':'coord@example.org','password':'wrong-password'}).status_code==401
        assert a.post('/api/auth/login',json={'email':'coord@example.org','password':'senha-forte-2026'}).status_code==200


def test_import_and_curate():
    item={'year':2023,'index':1,'title':'Teste de importação','discipline':'matematica','language':None,
          'context':'Texto originário de resposta simulada em teste, NÃO é questão real do ENEM.',
          'files':[],'alternativesIntroduction':'Qual opção?','correctAlternative':'B',
          'alternatives':[{'letter':'A','text':'1','isCorrect':False},{'letter':'B','text':'2','isCorrect':True}]}
    def handler(req):
        assert req.url.path.endswith('/2023/questions')
        return httpx.Response(200,json={'metadata':{'total':1,'hasMore':False},'questions':[item]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as cli:
        assert sync_year(2023,'https://test.local/v1',client=cli)==1
        assert sync_year(2023,'https://test.local/v1',client=cli)==1
    assert one("SELECT COUNT(*) n FROM questions WHERE source='ENEM API'")['n']==1
    assert normalize(item)['discipline']==''
    with TestClient(app) as coord:
        coord.post('/api/auth/login',json={'email':'coord@example.org','password':'senha-forte-2026'})
        qs=coord.get('/api/questions?source=ENEM%20API').json()
        assert qs['total']==1
        q=qs['items'][0]
        assert q['correct_letter']=='B' and q['status']=='review'
        assert coord.patch('/api/questions/enem-2023-1-geral',json={'status':'published','rights_status':'pending'}).status_code==422
        assert coord.patch('/api/questions/enem-2023-1-geral',json={'status':'published','rights_status':'authorized',
           'discipline':'Matemática','topic':'Funções','difficulty':'média'}).status_code==200
        assert coord.get('/api/questions/enem-2023-1-geral').json()['topic']=='Funções'
        with TestClient(app) as student:
            student.post('/api/auth/login',json={'email':'aluno@example.org','password':'senha-forte-2026'})
            q=student.get('/api/questions?source=ENEM%20API').json()['items'][0]
            assert 'correct_letter' not in q
            assert student.get('/api/questions/enem-2023-1-geral').status_code==403
            result=student.post('/api/practice/answer',json={'question_id':q['id'],'letter':'B'})
            assert result.json()['correct'] is True
            assert student.get('/api/practice/progress').json()['n']==1
        with TestClient(app) as teacher:
            teacher.post('/api/auth/login',json={'email':'prof@example.org','password':'senha-forte-2026'})
            assert teacher.post('/api/exams',json={'class_id':'y-1b','subject':'Física','title':'Exame teste',
                'question_ids':['enem-2023-1-geral']}).status_code==200
            assert teacher.post('/api/exams',json={'class_id':'x-1b','subject':'Física','title':'Exame indevido',
                'question_ids':['enem-2023-1-geral']}).status_code==403
            assert len(teacher.get('/api/exams').json())==1
