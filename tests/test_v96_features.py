"""Regressoes de perfis, alertas, IA e revisao de provas (dados ficticios)."""
import unittest
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.llm.provider import provider


def demo_credentials(email):
    text=(Path(__file__).resolve().parents[1]/'data'/'ACESSOS-DEMO-LOCAL.txt').read_text()
    for line in text.splitlines():
        if line.startswith(email+' | '):
            return {'email':email,'password':line.split(' | ',1)[1]}
    raise AssertionError('Conta de demonstração indisponível')


class V96Features(unittest.TestCase):
    def setUp(self):
        self.cm=TestClient(app)
        self.client=self.cm.__enter__()

    def tearDown(self):
        self.cm.__exit__(None,None,None)

    def login(self,email):
        response=self.client.post('/api/auth/login',json=demo_credentials(email))
        self.assertEqual(response.status_code,200,response.text)

    def test_three_roles_and_student_timetable(self):
        self.login('alice.fontes@cognix.test')
        me=self.client.get('/api/me')
        self.assertEqual(me.status_code,200,me.text)
        self.assertEqual(me.json()['user']['role'],'aluno')
        self.assertNotIn('password_hash',me.json()['user'])
        school=me.json()['schools'][0]['id']
        schedule=self.client.get('/api/student/schedule',params={'school':school})
        self.assertEqual(schedule.status_code,200,schedule.text)
        self.assertTrue(schedule.json()['assessments'])
        self.assertEqual(self.client.get('/api/pedagogy/attention').status_code,403)

    def test_teacher_alerts_and_ai_without_key(self):
        self.login('rafael.monteiro@cognix.test')
        me=self.client.get('/api/me').json()
        classes=self.client.get('/api/classes').json()
        attention=self.client.get('/api/pedagogy/attention')
        self.assertEqual(attention.status_code,200,attention.text)
        self.assertIn('students_to_follow',attention.json())
        self.assertIn('critical_topics',attention.json())
        self.assertTrue(classes)
        selected=next(x for x in classes if x['subjects'] and x['grade'].startswith('3ª'))
        subject=selected['subjects'][0]
        observations=self.client.get('/api/pedagogy/observations',
             params={'class_id':selected['id'],'subject':subject})
        self.assertEqual(observations.status_code,200,observations.text)
        result=self.client.post('/api/ai/diagnose',json={
            'school_id':selected['school_id'],'class_id':selected['id'],'subject':subject})
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn(result.json()['mode'],('regras','llm'))

    def test_llm_diagnosis_uses_anonymized_aggregates(self):
        self.login('rafael.monteiro@cognix.test')
        cls=next(x for x in self.client.get('/api/classes').json() if x['subjects'])
        prompts=[]
        def fake_llm(prompt,mode):
            prompts.append((prompt,mode))
            return {'resumo':'Há padrões que exigem reforço.',
                    'padroes':['Revisar a habilidade priorizada nas aulas seguintes.'],
                    'revisoes':[{'dia':0,'aula':0,'topico':'Revisão','atividade':'Exercícios orientados','minutos':15}]}
        with patch.object(provider,'key','teste-sem-chamada-externa'),patch.object(provider,'call',side_effect=fake_llm):
            r=self.client.post('/api/ai/diagnose',json={
                'school_id':cls['school_id'],'class_id':cls['id'],'subject':cls['subjects'][0]})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['mode'],'llm')
        self.assertTrue(r.json()['generated'])
        self.assertEqual(prompts[0][1],'json')
        aggregates=json.loads(prompts[0][0].split('Dados: ',1)[1])
        self.assertIn('cronograma',aggregates)
        self.assertIn('topicos_criticos',aggregates)
        self.assertIn('erros_por_topico',aggregates)
        self.assertNotIn('alunos',aggregates)
        self.assertNotIn('student_name',prompts[0][0])

    def test_coordination_permissions_and_trail_aggregate(self):
        self.login('coordenacao@cognix.test')
        self.assertEqual(self.client.get('/api/me').json()['user']['role'],'coord')
        self.assertEqual(self.client.get('/api/pedagogy/attention',params={'school':'escola-y'}).status_code,403)
        classes=self.client.get('/api/classes').json()
        selected=next(x for x in classes if x['subjects'] and x['grade'].startswith('3ª'))
        overview=self.client.get('/api/pedagogy/trail-overview',
            params={'class_id':selected['id'],'subject':selected['subjects'][0]})
        self.assertEqual(overview.status_code,200,overview.text)
        self.assertGreater(overview.json()['student_count'],0)

    def test_preview_has_no_autosave_and_saved_exam_can_be_edited(self):
        self.login('rafael.monteiro@cognix.test')
        classes=self.client.get('/api/classes').json()
        combo=None
        for cls in classes:
            for subject in cls['subjects']:
                options=self.client.get('/api/exam-builder/options',
                  params={'class_id':cls['id'],'subject':subject})
                if options.status_code==200 and options.json()['total']>=2:
                    combo=(cls,subject,options.json())
                    break
            if combo:break
        self.assertIsNotNone(combo,'Demo requer duas questões válidas')
        cls,subject,options=combo
        before=len(self.client.get('/api/exams').json())
        payload={'class_id':cls['id'],'subject':subject,'title':'Prévia controlada',
                 'topics':[x['topic'] for x in options['topics']],
                 'types':['multipla','vf','discursiva'],'count':2,
                 'easy_percent':40,'medium_percent':40,'hard_percent':20,
                 'total_points':10,'focus_weak_topics':True}
        preview=self.client.post('/api/exam-builder/preview',json=payload)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertFalse(preview.json()['saved'])
        self.assertEqual(len(self.client.get('/api/exams').json()),before)
        ids=[x['id'] for x in preview.json()['items']]
        edited_prompt='Enunciado personalizado pelo professor para a prova editável.'
        saved=self.client.post('/api/exams',json={
          'class_id':cls['id'],'subject':subject,'title':'Prova confirmada',
          'question_ids':ids,'total_points':12,'instructions':'Leia cada item.',
          'question_edits':{ids[0]:edited_prompt}})
        self.assertEqual(saved.status_code,200,saved.text)
        exam_id=saved.json()['id']
        detail=self.client.get('/api/exams/'+exam_id)
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()['exam']['total_points'],12)
        self.assertEqual(detail.json()['items'][0]['prompt'],edited_prompt)
        docx=self.client.get('/api/exams/'+exam_id+'/docx')
        self.assertEqual(docx.status_code,200,docx.text)
        with zipfile.ZipFile(io.BytesIO(docx.content)) as z:
            self.assertIn(edited_prompt,z.read('word/document.xml').decode('utf8'))
        updated=self.client.patch('/api/exams/'+exam_id,json={
          'class_id':cls['id'],'subject':subject,'title':'Prova editada',
          'question_ids':ids[::-1],'total_points':8,'instructions':'Releia antes de entregar.',
          'question_edits':{ids[0]:edited_prompt}})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(self.client.get('/api/exams/'+exam_id).json()['exam']['title'],'Prova editada')
        assessments=self.client.get('/api/pedagogy/assessments',
            params={'class_id':cls['id'],'subject':subject}).json()
        self.assertTrue(assessments)
        linked=self.client.post('/api/exams/'+exam_id+'/link-assessment',
            json={'assessment':assessments[0]['name']})
        self.assertEqual(linked.status_code,200,linked.text)
        self.assertEqual(self.client.get('/api/exams/'+exam_id).json()['exam']['applied_assessment'],
                         assessments[0]['name'])
        delete=self.client.delete('/api/exams/'+exam_id)
        self.assertEqual(delete.status_code,200,delete.text)
        self.assertEqual(len(self.client.get('/api/exams').json()),before)


if __name__=='__main__':
    unittest.main()
