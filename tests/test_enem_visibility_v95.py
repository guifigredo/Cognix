"""Isolamento de questões ENEM: importação, classificação escolar, matéria e direitos."""
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import one
from backend.import_enem import store_questions
from test_cognix_v8 import sign_in


def _fake(index,discipline,title):
    return dict(year=2023,index=index,discipline=discipline,title=title,
      context='Texto fictício exclusivamente para teste automatizado.',
      alternativesIntroduction='Qual alternativa está correta?',files=[],
      correctAlternative='A',alternatives=[{'letter':'A','text':'Uma opção'},{'letter':'B','text':'Outra opção'}])


def test_enem_import_and_school_scoped_classification():
    store_questions([
        _fake(99124,'matematica','QUESTÃO_TESTE_MATEMATICA'),
        _fake(99125,'ciencias-natureza','QUESTÃO_TESTE_NATUREZA'),
    ])
    with (TestClient(app) as rafael, TestClient(app) as caio,
          TestClient(app) as coord_x, TestClient(app) as coord_y):
        sign_in(rafael,'rafael.monteiro@cognix.test')
        sign_in(caio,'caio.neri@cognix.test')
        sign_in(coord_x,'coordenacao@cognix.test')
        sign_in(coord_y,'coordenacao.y@cognix.test')

        math=one("SELECT * FROM questions WHERE title='QUESTÃO_TESTE_MATEMATICA'")
        nature=one("SELECT * FROM questions WHERE title='QUESTÃO_TESTE_NATUREZA'")
        assert math['discipline']=='Matemática'
        assert nature['discipline']==''
        assert math['status']=='review' and math['rights_status']=='pending'
        assert nature['status']=='review' and nature['rights_status']=='pending'
        mid,nid=math['id'],nature['id']

        # Ao professor X, Matemática é exibida, independentemente de revisão.
        q=rafael.get('/api/questions',params={'school':'escola-x','source':'ENEM API'})
        assert q.status_code==200, q.text
        assert mid in [x['id'] for x in q.json()['items']]
        assert nid not in [x['id'] for x in q.json()['items']]
        assert rafael.get('/api/questions/stats',params={'school':'escola-x'}).status_code==200
        assert rafael.get('/api/questions/'+nid,params={'school':'escola-x'}).status_code==404

        # Natureza exige classificação local. A coordenação Y não interfere em X.
        payload={'school_id':'escola-x','discipline':'Física','topic':'Óptica','difficulty':'média'}
        forbidden=coord_y.post(f'/api/questions/{nid}/school-classification',json=payload)
        assert forbidden.status_code==403
        classified=coord_x.post(f'/api/questions/{nid}/school-classification',json=payload)
        assert classified.status_code==200,classified.text
        assert one('SELECT discipline FROM questions WHERE id=?',(nid,))['discipline']==''

        # Caio leciona Física em X; Rafael leciona Matemática em X e Física em Y.
        r=caio.get('/api/questions',params={'school':'escola-x','subject':'Física','source':'ENEM API'})
        assert r.status_code==200,r.text
        assert nid in [x['id'] for x in r.json()['items']]
        assert nid not in [x['id'] for x in rafael.get('/api/questions',params={'school':'escola-x'}).json()['items']]
        assert rafael.get('/api/questions/'+nid,params={'school':'escola-y'}).status_code==404

        # A coordenação de Y classifica para Y, sem afetar as demais escolas.
        payload={'school_id':'escola-y','discipline':'Física','topic':'Eletromagnetismo'}
        assert coord_y.post(f'/api/questions/{nid}/school-classification',json=payload).status_code==200
        q=rafael.get('/api/questions',params={'school':'escola-y','subject':'Física','source':'ENEM API'})
        assert nid in [x['id'] for x in q.json()['items']]
        detail=rafael.get('/api/questions/'+nid,params={'school':'escola-y'})
        assert detail.status_code==200
        assert detail.json()['display_discipline']=='Física'
        assert detail.json()['school_classifications'][0]['school_id']=='escola-y'

        # Direitos continuam pendentes: não pode montar prova usando a questão.
        bad=rafael.post('/api/exams',json={'class_id':'y-1b','subject':'Física',
          'title':'Prova com questão pendente','question_ids':[nid]})
        assert bad.status_code==422
        assert all(x['id']!=nid for x in
          rafael.get('/api/exam-builder/options',params={'class_id':'y-1b','subject':'Física'}).json().get('items',[]))
        # Uma hipotética liberação global, feita fora da conta da escola, permite
        # utilizar a questão somente na disciplina classificda e atribuída.
        from backend.db import session
        with session() as db:
            db.execute("UPDATE questions SET status='published',rights_status='authorized' WHERE id=?",(nid,))
        manual=rafael.post('/api/exams',json={'class_id':'y-1b','subject':'Física',
           'title':'Prova autorizada da escola Y','question_ids':[nid]})
        assert manual.status_code==200,manual.text
        assert rafael.post('/api/exams',json={'class_id':'x-1b','subject':'Matemática',
           'title':'Matemática não vinculada','question_ids':[nid]}).status_code==422
        assert rafael.get('/api/exam-builder/options',params={'class_id':'y-1b','subject':'Física'}).json()['total']>=7


def test_cannot_fake_discipline_in_enem_area():
    nature=one("SELECT id FROM questions WHERE title='QUESTÃO_TESTE_NATUREZA'")
    assert nature
    with TestClient(app) as c:
        sign_in(c,'coordenacao@cognix.test')
        bad=c.post('/api/questions/'+nature['id']+'/school-classification',json={
          'school_id':'escola-x','discipline':'Matemática'})
        assert bad.status_code==422


def test_importer_handles_missing_year_and_pagination_without_metadata():
    """A resposta enxuta da API pode omitir year, discipline e metadata."""
    import httpx
    from backend.import_enem import sync_year
    calls=[]
    def route(request):
        offset=int(request.url.params.get('offset','0'))
        calls.append(offset)
        if offset==0:
            data=[{'index':136+i,'title':f'TEST_PAGE_{i}', 'context':'Exemplo fictício',
                  'alternatives':[{'letter':'A','text':'X'},{'letter':'B','text':'Y'}]}
                  for i in range(45)]
        else:
            data=[]
        return httpx.Response(200,json={'questions':data})
    with httpx.Client(transport=httpx.MockTransport(route)) as client:
        n=sync_year(2022,'https://example.invalid/v1',client=client)
    assert n==45
    # Página parcial encerra sem depender do campo metadata.
    assert calls==[0]
    item=one("SELECT discipline,area,year FROM questions WHERE title='TEST_PAGE_0'")
    assert item=={'discipline':'Matemática','area':'Matemática','year':2022}


def test_enem_import_preserves_draft_rights_on_reimport():
    from backend.import_enem import store_questions
    item=_fake(99177,'matematica','TEST_ENEM_IDEMPOTENT')
    assert store_questions([item])==1
    with __import__('backend.db',fromlist=['session']).session() as db:
        db.execute("UPDATE questions SET status='published',rights_status='authorized' WHERE title='TEST_ENEM_IDEMPOTENT'")
    assert store_questions([item])==1
    q=one("SELECT status,rights_status FROM questions WHERE title='TEST_ENEM_IDEMPOTENT'")
    assert q=={'status':'published','rights_status':'authorized'}
