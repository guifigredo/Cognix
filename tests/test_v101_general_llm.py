"""v10.1: visão Geral autorizada e geração LLM recuperável por acervo."""
import json
import os
import unittest
from unittest.mock import patch
import httpx

from backend import db
from backend.llm.provider import provider
import test_v100_domains as v100


class GeneralAndLLM(unittest.TestCase):
    setUp=v100.CognixV10.setUp
    tearDown=v100.CognixV10.tearDown
    create_questions=v100.CognixV10.create_questions

    def test_general_shows_allowed_scopes_and_not_others(self):
        _,_,mine=self.create_questions('teach100','personal')
        _,_,school=self.create_questions('teach200','school')
        _,_,other=self.create_questions('teach200','personal')
        with db.session() as con:
            con.execute('''INSERT INTO questions(id,source,source_key,discipline,title,prompt,
                status,rights_status) VALUES(?,?,?,?,?,?,?,?)''',
                ('central-bio','ENEM API','demo-bio','Biologia','Questão pública de biologia',
                 'Qual alternativa representa a composição de uma célula?','published','authorized'))
            con.execute('''INSERT INTO questions(id,source,source_key,discipline,title,prompt,
                status,rights_status,school_id,creator_id) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                ('other-school','Importação docente','other-school','Matemática','Questão escola Y',
                 'Qual expressão representa uma função?', 'published','authorized','escola-y','teach200'))
            con.execute('''INSERT INTO questions(id,source,source_key,discipline,title,prompt,
                status,rights_status) VALUES(?,?,?,?,?,?,?,?)''',
                ('central-draft','ENEM API','hidden-draft','Biologia','Ainda em revisão',
                 'Esse enunciado ainda não foi publicado.','review','pending'))
        result=self.clients['teach100'].get('/api/bank/general')
        self.assertEqual(result.status_code,200,result.text)
        ids={q['id'] for q in result.json()['items']}
        self.assertIn(mine[0]['id'],ids)
        self.assertIn(school[0]['id'],ids)
        self.assertIn('central-bio',ids)  # pode consultar outra matéria sem montar prova
        self.assertNotIn(other[0]['id'],ids)
        self.assertNotIn('other-school',ids)
        self.assertNotIn('central-draft',ids)
        public=next(q for q in result.json()['items'] if q['id']=='central-bio')
        self.assertEqual(public['scope_label'],'Catálogo central')
        self.assertFalse(public['exam_eligible'])
        self.assertEqual(self.clients['teach200'].get('/api/bank/general',params={'topic':'cinemática'}).status_code,200)
        self.assertEqual(self.clients['private100'].get('/api/bank/general').status_code,200)
        self.assertIn(self.clients['coord100'].get('/api/bank/general').status_code,(403,))

    def test_general_revokes_school_items_after_unlink(self):
        _,_,personal=self.create_questions('teach100','personal')
        _,_,school=self.create_questions('teach200','school')
        before=self.clients['teach100'].get('/api/bank/general').json()['items']
        self.assertIn(school[0]['id'],[q['id'] for q in before])
        with db.session() as con:
            con.execute("UPDATE school_memberships SET status='ended' WHERE user_id=? AND school_id=?",
                        ('teach100','escola-x'))
        after=self.clients['teach100'].get('/api/bank/general')
        self.assertEqual(after.status_code,200,after.text)
        ids=[q['id'] for q in after.json()['items']]
        self.assertIn(personal[0]['id'],ids)
        self.assertNotIn(school[0]['id'],ids)

    def test_llm_creates_personal_batch_for_review(self):
        client=self.clients['teach100']
        collection=next(c['id'] for c in client.get('/api/bank/collections').json()['collections'] if c['kind']=='personal')
        fake={'questoes':[{'enunciado':'Um automóvel em movimento uniforme percorre 100 metros em 5 segundos. Qual é a velocidade?',
                           'alternativas':['10 m/s','20 m/s','30 m/s','40 m/s','50 m/s'],
                           'gabarito':'B','justificativa':'A velocidade é espaço dividido pelo tempo.'}]}
        with patch.object(provider,'key','fake-for-tests'),patch.object(provider,'call',return_value=fake):
            created=client.post('/api/ai/questions',json={'collection_id':collection,
                          'subject':'Física','topic':'Cinemática','count':1})
        self.assertEqual(created.status_code,200,created.text)
        item=created.json()['questions'][0]
        batch_id=created.json()['batch_id']
        self.assertTrue(batch_id)
        detail=client.get('/api/bank/batches/'+batch_id)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['items'][0]['id'],item['id'])
        self.assertEqual(detail.json()['items'][0]['review_state'],'draft')
        self.assertEqual(db.one('SELECT collection_id FROM question_records WHERE question_id=?',(item['id'],))['collection_id'],collection)
        self.assertEqual(db.one('SELECT origin_format FROM question_batches WHERE id=?',(batch_id,))['origin_format'],'llm')
        self.assertIn(self.clients['teach200'].get('/api/bank/batches/'+batch_id).status_code,(403,404))
        self.assertIn(self.clients['teach200'].get('/api/questions/'+item['id']).status_code,(403,404))
        search=client.get('/api/bank/general',params={'source':'Cognix LLM'})
        self.assertEqual(search.status_code,200)
        self.assertIn(item['id'],[x['id'] for x in search.json()['items']])
        review=client.post('/api/bank/review',json={'batch_id':batch_id,'items':[
           {'question_id':item['id'],'discipline':'Física','topic':'Cinemática','rights_confirmed':True}]})
        self.assertEqual(review.status_code,200,review.text)
        self.assertEqual(db.one('SELECT status FROM questions WHERE id=?',(item['id'],))['status'],'published')

    def test_llm_school_requires_assigned_subject(self):
        client=self.clients['teach100']
        school=next(c['id'] for c in client.get('/api/bank/collections').json()['collections'] if c['kind']=='school')
        not_assigned=client.post('/api/ai/questions',json={'collection_id':school,
                           'subject':'História','topic':'História do Brasil'})
        self.assertEqual(not_assigned.status_code,403,not_assigned.text)
        self.assertEqual(db.one('SELECT COUNT(*) n FROM question_batches')['n'],0)

    def test_llm_rejects_missing_answer_and_does_not_save_anything(self):
        client=self.clients['teach100']
        collection=next(c['id'] for c in client.get('/api/bank/collections').json()['collections'] if c['kind']=='personal')
        fake={'questoes':[{'enunciado':'Um automóvel com movimento uniforme percorreu 80 metros em 4 segundos.',
                           'alternativas':['10 m/s','20 m/s']}]}
        with patch.object(provider,'key','test'),patch.object(provider,'call',return_value=fake):
            response=client.post('/api/ai/questions',json={'collection_id':collection,
                'subject':'Física','topic':'Cinemática'})
        self.assertEqual(response.status_code,502,response.text)
        self.assertEqual(db.one('SELECT COUNT(*) n FROM question_batches')['n'],0)

    def test_probe_and_status_without_exposing_secret(self):
        client=self.clients['teach100']
        with patch.object(provider,'key','fake-secret-value'),patch.object(provider,'call',return_value={'conexao':'ok'}):
            status=client.get('/api/ai/status')
            probe=client.post('/api/ai/probe',json={})
        self.assertEqual(status.status_code,200)
        self.assertEqual(probe.status_code,200,probe.text)
        self.assertTrue(probe.json()['ok'])
        self.assertNotIn('fake-secret-value',probe.text+status.text)
        with patch.object(provider,'key',''):
            disabled=client.post('/api/ai/probe',json={})
            self.assertEqual(disabled.status_code,503)

    def test_dotenv_works_with_runtime_override(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'runtime-key'},clear=False):
            self.assertEqual(provider.key,'runtime-key')
        with patch.dict(os.environ,{},clear=False):
            env=os.environ.pop('GEMINI_API_KEY',None)
            try:
                with patch('backend.llm.provider.dotenv_values',return_value={'GEMINI_API_KEY':'file-key'}):
                    self.assertEqual(provider.key,'file-key')
            finally:
                if env is not None:os.environ['GEMINI_API_KEY']=env

    def test_gemini_payload_parser_and_fallback(self):
        calls = []
        original_client = httpx.Client

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(503)
            return httpx.Response(200, json={'candidates': [{
                'finishReason': 'STOP', 'content': {'parts': [
                    {'text': 'private reasoning', 'thought': True},
                    {'text': '{"conexao":"ok"}'},
                ]},
            }]})

        with patch.object(provider, 'key', 'only-a-test-key'), patch(
            'backend.llm.provider.httpx.Client',
            side_effect=lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
        ):
            output = provider.call('Retorne JSON com a conexão', 'json')

        self.assertEqual(output, {'conexao': 'ok'})
        self.assertEqual(provider.used_model, 'gemini-3.5-flash-lite')
        self.assertEqual([request.url.path for request in calls], [
            '/v1beta/models/gemini-3.5-flash:generateContent',
            '/v1beta/models/gemini-3.5-flash-lite:generateContent',
        ])
        self.assertEqual(calls[0].headers['x-goog-api-key'], 'only-a-test-key')
        self.assertEqual(json.loads(calls[0].content)['generationConfig']['responseMimeType'],
                         'application/json')
        self.assertNotIn('only-a-test-key', str(calls[0].url))

    def test_gemini_auth_failure_does_not_retry(self):
        from backend.llm.provider import LLMError

        calls = []
        original_client = httpx.Client

        def handler(request):
            calls.append(request)
            return httpx.Response(403)

        with patch.object(provider, 'key', 'only-a-test-key'), patch(
            'backend.llm.provider.httpx.Client',
            side_effect=lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
        ):
            with self.assertRaisesRegex(LLMError, 'HTTP 403'):
                provider.call('Teste de autenticação')

        self.assertEqual(len(calls), 1)
