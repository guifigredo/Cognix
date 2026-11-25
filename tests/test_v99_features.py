"""Regressões para a experiência docente, evidências e isolamento institucional."""
import json
import secrets
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.db import one, rows, session
from backend.main import app


def login(client,email):
    credentials=Path(__file__).resolve().parents[1]/'data'/'ACESSOS-DEMO-LOCAL.txt'
    password=next(line.split(' | ',1)[1] for line in credentials.read_text().splitlines()
                  if line.startswith(email+' | '))
    res=client.post('/api/auth/login',json={'email':email,'password':password})
    assert res.status_code==200,res.text


class TeacherTools(unittest.TestCase):
    def setUp(self):
        self.cm=TestClient(app)
        self.client=self.cm.__enter__()

    def tearDown(self):
        self.cm.__exit__(None,None,None)

    def test_planned_lesson_can_be_reviewed_and_saved_without_groups(self):
        login(self.client,'rafael.monteiro@cognix.test')
        teacher=one('SELECT id FROM users WHERE email=?',('rafael.monteiro@cognix.test',))['id']
        lesson=one('''SELECT l.id,l.plan FROM lesson_schedule l JOIN teaching_assignments t
          ON t.class_id=l.class_id AND t.subject=l.subject AND t.teacher_id=l.teacher_id
          WHERE l.teacher_id=? LIMIT 1''',(teacher,))
        self.assertIsNotNone(lesson)
        lesson_id=lesson['id']
        try:
            response=self.client.get('/api/teacher-tools/lesson/'+lesson_id)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(response.json()['steps']),4)
            self.assertTrue(all('grupo' not in x['activity'].lower()
                       for x in response.json()['steps']))
            plan='Diagnóstico individual revisado pelo professor para a próxima aula.'
            saved=self.client.post('/api/teacher-tools/lesson/'+lesson_id+'/apply',json={'plan':plan})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(one('SELECT plan FROM lesson_schedule WHERE id=?',(lesson_id,))['plan'],plan)
        finally:
            with session() as db:
                db.execute('UPDATE lesson_schedule SET plan=? WHERE id=?',(lesson['plan'],lesson_id))
        login(self.client,'alice.fontes@cognix.test')
        self.assertEqual(self.client.get('/api/teacher-tools/lesson/'+lesson_id).status_code,403)

    def test_grade_topic_evidence_is_not_inferred_from_combined_score(self):
        login(self.client,'coordenacao@cognix.test')
        student=one('SELECT user_id FROM enrollments WHERE class_id=? LIMIT 1',('x-3a',))['user_id']
        name='Teste99-'+secrets.token_hex(4)
        with session() as db:
            db.execute('''INSERT INTO assessments(id,class_id,subject,name,weight,topics_json)
              VALUES(?,?,?,?,?,?)''',(secrets.token_hex(12),'x-3a','Matemática',name,1,
                                      json.dumps(['Tópico A','Tópico B'])))
        try:
            base={'class_id':'x-3a','subject':'Matemática','student_id':student,
                  'assessment':name,'score':7}
            self.assertEqual(self.client.post('/api/grades',json=base).status_code,200)
            self.assertEqual(rows('SELECT topic FROM grade_topics WHERE assessment=?',(name,)),[])
            invalid=self.client.post('/api/grades',json={**base,'topic_scores':{'Inexistente':8}})
            self.assertEqual(invalid.status_code,422)
            saved=self.client.post('/api/grades',json={**base,
                          'topic_scores':{'Tópico A':9,'Tópico B':5}})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual([(r['topic'],r['score']) for r in rows('''SELECT topic,score
              FROM grade_topics WHERE assessment=? ORDER BY topic''',(name,))],
              [('Tópico A',9),('Tópico B',5)])
            self.assertEqual(self.client.get('/api/teacher-tools/report.csv',params={
                'class_id':'x-3a','subject':'Matemática'}).status_code,200)
        finally:
            with session() as db:
                db.execute('DELETE FROM grade_topics WHERE assessment=?',(name,))
                db.execute('DELETE FROM grades WHERE assessment=?',(name,))
                db.execute('DELETE FROM grade_audit WHERE assessment=?',(name,))
                db.execute('DELETE FROM assessments WHERE name=?',(name,))

    def test_error_notebook_is_based_only_on_scoped_real_answers(self):
        login(self.client,'rafael.monteiro@cognix.test')
        response=self.client.get('/api/teacher-tools/error-notebook',params={
                      'class_id':'x-3a','subject':'Matemática'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('attempts',response.json())
        self.assertEqual(self.client.get('/api/teacher-tools/error-notebook',params={
                      'class_id':'y-3a','subject':'Matemática'}).status_code,403)
        login(self.client,'alice.fontes@cognix.test')
        self.assertEqual(self.client.get('/api/teacher-tools/error-notebook',params={
                      'class_id':'x-3a','subject':'Matemática'}).status_code,403)

    def test_teacher_feedback_is_private_editable_draft(self):
        login(self.client,'rafael.monteiro@cognix.test')
        student=one('SELECT user_id FROM enrollments WHERE class_id=? LIMIT 1',('x-3a',))['user_id']
        response=self.client.get('/api/teacher-tools/feedback',params={
          'class_id':'x-3a','subject':'Matemática','student_id':student})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'rascunho')
        self.assertIn('nenhuma mensagem',response.json()['note'].lower())

    def test_institutional_criteria_apply_consistently_to_topic_evidence(self):
        login(self.client,'coordenacao@cognix.test')
        school=one('SELECT school_id FROM classes WHERE id=?',('x-3a',))['school_id']
        old=one('SELECT settings_json FROM school_configuration WHERE school_id=?',(school,))
        self.assertIsNotNone(old)
        settings=json.loads(old['settings_json'])
        try:
            with session() as db:
                db.execute('UPDATE school_configuration SET settings_json=? WHERE school_id=?',
                           (json.dumps({**settings,'mediaAprov':8.0,'mediaRec':5.0}),school))
            matrix=self.client.get('/api/pedagogy/matrix',params={
                    'class_id':'x-3a','subject':'Matemática'})
            self.assertEqual(matrix.status_code,200,matrix.text)
            self.assertEqual(matrix.json()['school_threshold'],8.0)
            evidence=self.client.get('/api/pedagogy/evidence',params={
                    'school':school,'class_id':'x-3a'})
            self.assertEqual(evidence.status_code,200,evidence.text)
            self.assertEqual(evidence.json()['school_threshold'],8.0)
        finally:
            with session() as db:
                db.execute('UPDATE school_configuration SET settings_json=? WHERE school_id=?',
                           (old['settings_json'],school))

    def test_question_error_notebook_filters_exact_topic(self):
        login(self.client,'rafael.monteiro@cognix.test')
        base={'class_id':'x-3a','subject':'Matemática'}
        all_questions=self.client.get('/api/teacher-tools/error-notebook',params=base)
        self.assertEqual(all_questions.status_code,200,all_questions.text)
        chosen='Tópico não encontrado no banco de prática — teste'
        filtered=self.client.get('/api/teacher-tools/error-notebook',params={**base,'topic':chosen})
        self.assertEqual(filtered.status_code,200,filtered.text)
        self.assertEqual(filtered.json()['questions'],[])
        self.assertEqual(filtered.json()['attempts'],0)


if __name__=='__main__':
    unittest.main()
