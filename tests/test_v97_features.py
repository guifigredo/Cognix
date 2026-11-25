"""Regressões para cronogramas persistidos, evidências e acesso por série."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.db import one, rows, session
from backend.llm.provider import provider
from backend.main import app


def login(client, email):
    path=Path(__file__).resolve().parents[1]/'data'/'ACESSOS-DEMO-LOCAL.txt'
    line=next(x for x in path.read_text().splitlines() if x.startswith(email+' | '))
    response=client.post('/api/auth/login',json={'email':email,'password':line.split(' | ',1)[1]})
    assert response.status_code==200,response.text


class V97Features(unittest.TestCase):
    def setUp(self):
        self.cm=TestClient(app)
        self.client=self.cm.__enter__()

    def tearDown(self):
        self.cm.__exit__(None,None,None)

    def test_weekly_lesson_is_saved_and_student_sees_same_content(self):
        login(self.client,'rafael.monteiro@cognix.test')
        classes=self.client.get('/api/classes').json()
        cls=next(x for x in classes if x['id']=='x-3a' and 'Matemática' in x['subjects'])
        payload={'class_id':cls['id'],'subject':'Matemática','weekday':0,'slot':15,
                 'room':'Laboratório','topic':'Revisão de funções e gráficos',
                 'plan':'Comparar estratégias e resolver dois problemas em grupo.',
                 'status':'planejada','notes':'Nota privada para o professor.'}
        created=self.client.post('/api/pedagogy/schedule',json=payload)
        self.assertEqual(created.status_code,200,created.text)
        lesson_id=created.json()['lesson']['id']
        try:
            changed=self.client.patch('/api/pedagogy/schedule/'+lesson_id,
                json={'topic':'Revisão de equações','plan':'Oficina de equações em duplas.',
                      'status':'dada','notes':'Refletir sobre a participação.'})
            self.assertEqual(changed.status_code,200,changed.text)
            self.assertEqual(one('SELECT topic FROM lesson_schedule WHERE id=?',(lesson_id,))['topic'],
                             'Revisão de equações')
            new_session=TestClient(app)
            login(new_session,'alice.fontes@cognix.test')
            schedule=new_session.get('/api/student/schedule',params={'school':cls['school_id']})
            self.assertEqual(schedule.status_code,200,schedule.text)
            same=next(x for x in schedule.json()['lessons']
                      if x['class_id']==cls['id'] and x['slot']==15)
            self.assertEqual(same['topic'],'Revisão de equações')
            self.assertEqual(same['plan'],'Oficina de equações em duplas.')
            self.assertNotIn('notes',same)
        finally:
            with session() as db:
                db.execute('DELETE FROM lesson_schedule WHERE id=?',(lesson_id,))

    def test_time_windows_topic_filters_and_school_scope(self):
        login(self.client,'coordenacao@cognix.test')
        all_data=self.client.get('/api/pedagogy/evidence',params={'school':'escola-x'})
        self.assertEqual(all_data.status_code,200,all_data.text)
        self.assertTrue(all_data.json()['classes'])
        self.assertTrue(all_data.json()['topic_options'])
        first=all_data.json()['topic_options'][0]
        selected=self.client.get('/api/pedagogy/evidence',params={
            'school':'escola-x','topic':first['key'],'period':'mes'})
        self.assertEqual(selected.status_code,200,selected.text)
        self.assertTrue(all(x['key']==first['key'] for x in selected.json()['topics']))
        for grouping in ['avaliacao','semana','quinzena','mes','bimestre','semestre']:
            grouped=self.client.get('/api/pedagogy/evidence',params={
                'school':'escola-x','period':grouping})
            self.assertEqual(grouped.status_code,200,grouped.text)
            self.assertTrue(all(x['count']>0 for x in grouped.json()['timeline']))
        self.assertEqual(self.client.get('/api/pedagogy/evidence',params={
            'school':'escola-y'}).status_code,403)
        self.assertEqual(self.client.post('/api/ai/diagnose-evidence',json={
            'school_id':'escola-y'}).status_code,403)

    def test_qualitative_evidence_and_intervention_are_real_records(self):
        login(self.client,'rafael.monteiro@cognix.test')
        evidence=self.client.get('/api/pedagogy/evidence',params={
            'school':'escola-x','class_id':'x-3a'})
        self.assertEqual(evidence.status_code,200,evidence.text)
        topic=evidence.json()['topic_options'][0]
        student=rows('SELECT user_id FROM enrollments WHERE class_id=? LIMIT 1',('x-3a',))[0]
        common={'school_id':'escola-x','class_id':'x-3a','subject':topic['subject'],
                'topic':topic['topic']}
        qualitative=self.client.post('/api/pedagogy/evidence/observations',json={
            **common,'student_id':student['user_id'],'competency':'autonomia',
            'evidence_level':'com_apoio','observed_on':'2026-11-17',
            'note':'Explicou o procedimento usando um exemplo.'})
        self.assertEqual(qualitative.status_code,200,qualitative.text)
        intervention=self.client.post('/api/pedagogy/evidence/interventions',json={
            **common,'activity':'Oficina de interpretação de gráficos',
            'applied_on':'2026-11-17','notes':'Registro experimental'})
        self.assertEqual(intervention.status_code,200,intervention.text)
        try:
            refreshed=self.client.get('/api/pedagogy/evidence',params={
                'school':'escola-x','class_id':'x-3a','topic':topic['key']})
            self.assertEqual(refreshed.status_code,200,refreshed.text)
            self.assertTrue(any(x['note']=='Explicou o procedimento usando um exemplo.'
                                for x in refreshed.json()['qualitative']))
            self.assertTrue(any(x['activity']=='Oficina de interpretação de gráficos'
                                for x in refreshed.json()['interventions']))
        finally:
            with session() as db:
                db.execute('DELETE FROM competency_observations WHERE id=?',(qualitative.json()['id'],))
                db.execute('DELETE FROM pedagogical_interventions WHERE id=?',(intervention.json()['id'],))

    def test_enem_trail_rejects_non_third_grade(self):
        login(self.client,'rafael.monteiro@cognix.test')
        classes=self.client.get('/api/classes').json()
        other=next(x for x in classes if x['subjects'] and not x['grade'].startswith('3ª'))
        response=self.client.get('/api/pedagogy/trail-overview',params={
            'class_id':other['id'],'subject':other['subjects'][0]})
        self.assertEqual(response.status_code,403,response.text)
        third=next(x for x in classes if x['subjects'] and x['grade'].startswith('3ª'))
        response=self.client.get('/api/pedagogy/trail-overview',params={
            'class_id':third['id'],'subject':third['subjects'][0]})
        self.assertEqual(response.status_code,200,response.text)

    def test_ai_receives_aggregates_and_uses_scheduled_hours(self):
        login(self.client,'rafael.monteiro@cognix.test')
        lessons=[x for x in self.client.get('/api/pedagogy/schedule',params={
            'school':'escola-y'}).json() if x['status']=='planejada']
        self.assertTrue(lessons)
        sample=lessons[0]
        prompts=[]
        def fake_call(prompt,format):
            prompts.append(prompt)
            return {'resumo':'Observações descritivas de padrões, sujeitas a revisão.',
                    'padroes':['Dificuldades a observar nas aulas reais.'],
                    'revisoes':[{'topico':sample['topic'],
                                 'atividade':'Construir analogias e praticar em grupo.',
                                 'minutos':15}]}
        with patch.object(provider,'key','teste-somente-local'),patch.object(provider,'call',side_effect=fake_call):
            response=self.client.post('/api/ai/diagnose-evidence',json={
                'school_id':'escola-y','class_id':sample['class_id']})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertTrue(data['generated'])
        self.assertTrue(data['weekly_plan'])
        self.assertEqual(data['weekly_plan'][0]['weekday'],sample['weekday'])
        self.assertEqual(data['weekly_plan'][0]['slot'],sample['slot'])
        self.assertNotIn('student_name',prompts[0])
        self.assertNotIn('student_id',prompts[0])
        self.assertIn('aulas_semanais_registradas',prompts[0])
        self.assertNotIn('Nota privada para o professor.',prompts[0])


if __name__=='__main__':
    unittest.main()
