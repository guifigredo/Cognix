"""Verifica personalização do estudante, projeções e isolamento de perfis na v9.8."""
import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.db import one, session
from backend.main import app


def login(client, email):
    path = Path(__file__).resolve().parents[1] / 'data' / 'ACESSOS-DEMO-LOCAL.txt'
    line = next(row for row in path.read_text().splitlines() if row.startswith(email + ' | '))
    res = client.post('/api/auth/login', json={
        'email': email, 'password': line.split(' | ', 1)[1]})
    assert res.status_code == 200, res.text


class V98Personalization(unittest.TestCase):
    def setUp(self):
        self.cm = TestClient(app)
        self.client = self.cm.__enter__()
        login(self.client, 'alice.fontes@cognix.test')
        self.user_id = one('SELECT id FROM users WHERE email=?',
                           ('alice.fontes@cognix.test',))['id']
        self.school = 'escola-x'
        self.original = one('SELECT * FROM student_preferences WHERE student_id=? AND school_id=?',
                            (self.user_id, self.school))

    def tearDown(self):
        with session() as db:
            db.execute('DELETE FROM student_preferences WHERE student_id=? AND school_id=?',
                       (self.user_id, self.school))
            if self.original:
                db.execute('''INSERT INTO student_preferences
                    (student_id,school_id,values_json,hours,feedback_json) VALUES(?,?,?,?,?)''',
                    (self.user_id, self.school, self.original['values_json'],
                     self.original['hours'], self.original['feedback_json']))
        self.cm.__exit__(None, None, None)

    def test_student_dashboard_explains_priorities_and_areas(self):
        response = self.client.get('/api/student/dashboard', params={'school': self.school})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual({a['area'] for a in payload['areas']},
                         {'Exatas', 'Natureza', 'Humanas', 'Linguagens'})
        self.assertTrue(payload['grades'])
        self.assertTrue(payload['topics'])
        self.assertTrue(all(x['reasons'] and x['area'] for x in payload['topics']))
        self.assertTrue(all('weight' in item and 'score' in item
                            for grade in payload['grades'] for item in grade['assessments']))

    def test_vocation_preferences_feedback_and_partial_update_persist(self):
        response = self.client.post('/api/student/preferences', json={
            'school_id': self.school, 'values': ['Criatividade', 'Pesquisa e descoberta'],
            'activities': ['Fazer experimentos', 'Resolver problemas com cálculos'],
            'environments': ['Laboratório'], 'subjects': ['Matemática'],
            'problem': 'Ajudar a sociedade com soluções sustentáveis.',
            'performance_weight': 10, 'hours': 7, 'objective': 'Engenharias e exatas',
            'focus_topics': ['Funções'], 'study_days': ['Seg', 'Qua', 'Sex'],
            'study_style': 'questoes'})
        self.assertEqual(response.status_code, 200, response.text)
        results = self.client.get('/api/student/vocational', params={'school': self.school})
        self.assertEqual(results.status_code, 200, results.text)
        data = results.json()
        self.assertEqual(data['profile']['problem'],
                         'Ajudar a sociedade com soluções sustentáveis.')
        self.assertEqual(data['profile']['performance_weight'], 10)
        self.assertEqual(data['profile']['objective'], 'Engenharias e exatas')
        self.assertEqual(data['profile']['study_days'], ['Seg', 'Qua', 'Sex'])
        self.assertEqual(data['profile']['study_style'], 'questoes')
        self.assertEqual(data['profile']['focus_topics'], ['Funções'])
        self.assertGreaterEqual(len(data['courses']), 9)
        self.assertTrue(all(item['reasons'] and 'graduation' in item
                            for item in data['courses']))
        selected = self.client.post('/api/student/vocational/feedback', json={
            'school_id': self.school, 'course_id': 'eng', 'choice': 'sim'})
        self.assertEqual(selected.status_code, 200, selected.text)
        saved = self.client.get('/api/student/vocational',
                                params={'school': self.school}).json()
        self.assertEqual(next(c for c in saved['courses'] if c['id'] == 'eng')['feedback'],
                         'sim')
        self.assertEqual(self.client.post('/api/student/preferences', json={
            'school_id': self.school, 'hours': 9}).status_code, 200)
        updated = self.client.get('/api/student/dashboard',
                                  params={'school': self.school}).json()['preferences']
        self.assertEqual(updated['hours'], 9)
        self.assertEqual(updated['objective'], 'Engenharias e exatas')
        self.assertEqual(updated['performance_weight'], 10)
        self.assertEqual(updated['study_days'], ['Seg', 'Qua', 'Sex'])
        self.assertEqual(updated['career_feedback']['eng'], 'sim')

    def test_school_isolation_and_role_isolation(self):
        self.assertEqual(self.client.get('/api/student/dashboard',
                         params={'school': 'escola-y'}).status_code, 403)
        forbidden = self.client.post('/api/student/vocational/feedback', json={
            'school_id': self.school, 'course_id': 'inexistente', 'choice': 'sim'})
        self.assertEqual(forbidden.status_code, 422)
        teacher = TestClient(app)
        login(teacher, 'rafael.monteiro@cognix.test')
        self.assertEqual(teacher.get('/api/student/vocational',
                         params={'school': self.school}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
