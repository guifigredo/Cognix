"""Aceites v10: retomada, isolamento, versão de prova, vínculo e restauração."""
import io
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ['COGNIX_EXEMPLOS_DOCENTES']='0'
os.environ['COGNIX_DEV_INVITES']='1'

from fastapi.testclient import TestClient
from docx import Document
from backend import db
from backend.auth import password_hash
from backend.main import app
from backend import question_bank


TEXT='''1. Um carro tem velocidade constante em movimento retilíneo. Qual o valor da velocidade?
A) 10 m/s
B) 20 m/s
Gabarito: B
2. Uma aceleração constante altera a velocidade de um móvel. Qual lei descreve isso?
A) Primeira lei
B) Segunda lei
Gabarito: B'''


class CognixV10(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=db.DB_FILE;self.old_store=question_bank.STORE
        db.DB_FILE=Path(self.temp.name)/'test.sqlite3'
        question_bank.STORE=Path(self.temp.name)/'attachments'
        os.environ['COGNIX_DB']=str(db.DB_FILE)
        os.environ['COGNIX_UPLOAD_STORE']=str(question_bank.STORE)
        db.init_db()
        with db.session() as con:
            for uid,email,role,plan in [('coord100','coord100@example.org','coord','school'),
                                        ('teach100','teach100@example.org','prof','school'),
                                        ('teach200','teach200@example.org','prof','school'),
                                        ('private100','private100@example.org','prof','individual')]:
                con.execute('''INSERT INTO users(id,name,email,password_hash,role,account_plan)
                 VALUES(?,?,?,?,?,?)''',(uid,uid,email,password_hash('valid-password-100'),role,plan))
            con.execute('INSERT INTO coordinator_schools(user_id,school_id) VALUES(?,?)',('coord100','escola-x'))
            for uid in ('teach100','teach200'):
                con.execute('INSERT INTO school_memberships(user_id,school_id) VALUES(?,?)',(uid,'escola-x'))
                con.execute('INSERT INTO teaching_assignments(id,teacher_id,class_id,subject) VALUES(?,?,?,?)',
                            ('assign-'+uid,uid,'x-1b','Física'))
            con.execute('INSERT INTO verified_emails(user_id,email) VALUES(?,?)',
                        ('private100','private100@example.org'))
        self.clients={}
        for email in ('coord100','teach100','teach200','private100'):
            c=TestClient(app)
            assert c.post('/api/auth/login',json={'email':email+'@example.org','password':'valid-password-100'}).status_code==200
            self.clients[email]=c

    def tearDown(self):
        for c in self.clients.values():c.close()
        db.DB_FILE=self.old_db;question_bank.STORE=self.old_store
        self.temp.cleanup()

    def create_questions(self,owner='teach100',kind='personal',payload=TEXT):
        c=self.clients[owner]
        collections=c.get('/api/bank/collections').json()['collections']
        coll=next(x['id'] for x in collections if x['kind']==kind)
        out=c.post('/api/bank/import/text',json={'collection_id':coll,'text':payload})
        self.assertEqual(out.status_code,200,out.text)
        batch=out.json()['batch_id']
        details=c.get('/api/bank/batches/'+batch).json()
        return coll,batch,details['items']

    def test_p0_resume_review_search_isolation(self):
        collection,batch,items=self.create_questions()
        again=self.clients['teach100'].post('/api/bank/import/text',json={'collection_id':collection,'text':TEXT}).json()
        self.assertTrue(again['resumed']);self.assertEqual(again['batch_id'],batch)
        self.assertEqual(again['total'],2)
        out=self.clients['teach100'].post('/api/bank/batches/'+batch+'/categorize')
        self.assertEqual(out.status_code,200)
        self.assertEqual(out.json()['suggested'],2)
        reviewed=self.clients['teach100'].post('/api/bank/review',json={'batch_id':batch,'items':[
            {'question_id':x['id'],'discipline':'Física','topic':'Cinemática','rights_confirmed':True} for x in items]})
        self.assertEqual(reviewed.status_code,200,reviewed.text)
        again=self.clients['teach100'].post('/api/bank/batches/'+batch+'/categorize').json()
        self.assertEqual(again['suggested'],0)
        search=self.clients['teach100'].get('/api/bank/search',params={'topic':'Cinemática','collection_id':collection})
        self.assertEqual(search.json()['total'],2)
        self.assertEqual(db.one('SELECT COUNT(*) n FROM question_categories')['n'],1)
        deny=self.clients['teach200'].get('/api/questions/'+items[0]['id'])
        self.assertIn(deny.status_code,(403,404))
        self.assertEqual(self.clients['coord100'].get('/api/bank/search').json()['total'],0)

    def test_concurrent_import_same_lot_is_idempotent(self):
        first=self.clients['teach100']
        collection=next(x['id'] for x in first.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        second=TestClient(app)
        self.assertEqual(second.post('/api/auth/login',json={'email':'teach100@example.org',
                         'password':'valid-password-100'}).status_code,200)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs=[pool.submit(client.post,'/api/bank/import/text',json={
                   'collection_id':collection,'text':TEXT}) for client in (first,second)]
                responses=[job.result() for job in jobs]
            self.assertTrue(all(r.status_code==200 for r in responses),[r.text for r in responses])
            self.assertEqual(responses[0].json()['batch_id'],responses[1].json()['batch_id'])
            self.assertEqual(db.one('SELECT COUNT(*) n FROM question_import_items')['n'],2)
        finally:second.close()

    def test_exam_version_survives_question_revision(self):
        _,batch,items=self.create_questions()
        c=self.clients['teach100']
        review={'batch_id':batch,'items':[{'question_id':x['id'],'discipline':'Física',
                 'topic':'Cinemática','rights_confirmed':True} for x in items]}
        self.assertEqual(c.post('/api/bank/review',json=review).status_code,200)
        qid=items[0]['id']
        created=c.post('/api/exams',json={'class_id':'x-1b','subject':'Física','title':'Avaliação de revisão',
          'question_ids':[qid],'total_points':10})
        self.assertEqual(created.status_code,200,created.text)
        exam_id=created.json()['id']
        original=c.get('/api/exams/'+exam_id).json()['items'][0]['prompt']
        review['items'][0]['prompt']='Enunciado corrigido posteriormente sobre velocidade média e aceleração.'
        self.assertEqual(c.post('/api/bank/review',json=review).status_code,200)
        self.assertNotEqual(db.one('SELECT prompt FROM questions WHERE id=?',(qid,))['prompt'],original)
        after=c.get('/api/exams/'+exam_id).json()
        self.assertEqual(after['items'][0]['prompt'],original)
        self.assertEqual(c.get('/api/exams/'+exam_id+'/docx').status_code,200)

    def test_docx_attachment_backup_restore(self):
        doc=Document();doc.add_paragraph(TEXT)
        buff=io.BytesIO();doc.save(buff)
        c=self.clients['teach100'];coll=next(x['id'] for x in c.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        response=c.post('/api/bank/import/file?collection_id='+coll+'&filename=avaliacao.docx',
                        content=buff.getvalue(),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(response.status_code,200,response.text)
        batch=c.get('/api/bank/batches/'+response.json()['batch_id']).json()
        qid=batch['items'][0]['id']
        attachments=c.get('/api/bank/attachments',params={'question_id':qid}).json()
        self.assertEqual(len(attachments),0)  # original é do lote, não da primeira questão
        self.assertEqual(c.get('/api/bank/batches/'+response.json()['batch_id']+'/original').status_code,200)
        self.assertIn(self.clients['teach200'].get('/api/bank/batches/'+response.json()['batch_id']+'/original').status_code,(403,404))
        from scripts.backup_restore_v10 import snapshot,restore
        archive=Path(self.temp.name)/'backup.zip'
        snapshot(archive)
        restored=restore(archive,Path(self.temp.name)/'isolated-restore')
        self.assertTrue(restored['verified'])
        self.assertEqual(restored['attachments'],1)
        self.assertEqual(restored['counts']['question_records'],2)

    def test_pdf_text_layer_and_scanned_failure(self):
        from reportlab.pdfgen import canvas
        buffer=io.BytesIO()
        doc=canvas.Canvas(buffer)
        y=800
        for line in TEXT.splitlines():
            doc.drawString(50,y,line);y-=20
        doc.save()
        c=self.clients['teach100']
        collection=next(x['id'] for x in c.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        response=c.post('/api/bank/import/file',params={'collection_id':collection,'filename':'prova.pdf'},
            content=buffer.getvalue(),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['total'],2)
        invalid=c.post('/api/bank/import/file',params={'collection_id':collection,'filename':'digitalizado.pdf'},
            content=b'%PDF-1.4\n%%EOF',headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(invalid.status_code,422)

    def test_docx_embedded_image_is_private(self):
        from PIL import Image
        from docx.shared import Cm
        picture=io.BytesIO();Image.new('RGB',(24,24),color='blue').save(picture,'PNG');picture.seek(0)
        doc=Document();doc.add_paragraph('1. Qual é a velocidade do corpo em movimento retilíneo?')
        doc.add_paragraph().add_run().add_picture(picture,width=Cm(1))
        doc.add_paragraph('A) 10 m/s');doc.add_paragraph('B) 20 m/s');doc.add_paragraph('Gabarito: B')
        buff=io.BytesIO();doc.save(buff)
        c=self.clients['teach100'];coll=next(x['id'] for x in c.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        response=c.post('/api/bank/import/file',params={'collection_id':coll,'filename':'imagem.docx'},
                        content=buff.getvalue(),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(response.status_code,200,response.text)
        qid=c.get('/api/bank/batches/'+response.json()['batch_id']).json()['items'][0]['id']
        attachments=c.get('/api/bank/attachments',params={'question_id':qid}).json()
        self.assertEqual(len(attachments),1)  # só imagem extraída; original é do lote
        self.assertTrue(any(x['media_type']=='image/png' for x in attachments))
        image=next(x for x in attachments if x['media_type']=='image/png')
        self.assertEqual(c.get('/api/bank/attachments/'+image['id']).status_code,200)
        self.assertIn(self.clients['teach200'].get('/api/bank/attachments/'+image['id']).status_code,(403,404))

    def test_same_picture_can_belong_to_multiple_questions(self):
        from PIL import Image
        from docx.shared import Cm
        picture=io.BytesIO();Image.new('RGB',(16,16),color='red').save(picture,'PNG')
        doc=Document()
        for n in (1,2):
            doc.add_paragraph(f'{n}. Um corpo em movimento retilíneo possui velocidade constante?')
            doc.add_paragraph().add_run().add_picture(io.BytesIO(picture.getvalue()),width=Cm(1))
            doc.add_paragraph('A) Sim');doc.add_paragraph('B) Não');doc.add_paragraph('Gabarito: A')
        blob=io.BytesIO();doc.save(blob)
        c=self.clients['teach100']
        coll=next(x['id'] for x in c.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        uploaded=c.post('/api/bank/import/file',params={'collection_id':coll,'filename':'imagem-repetida.docx'},
                        content=blob.getvalue(),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        questions=c.get('/api/bank/batches/'+uploaded.json()['batch_id']).json()['items']
        self.assertEqual(len(questions),2)
        pics=[c.get('/api/bank/attachments',params={'question_id':q['id']}).json()[0] for q in questions]
        self.assertNotEqual(pics[0]['id'],pics[1]['id'])
        self.assertEqual(pics[0]['sha256'],pics[1]['sha256'])
        for p in pics:self.assertEqual(c.get('/api/bank/attachments/'+p['id']).status_code,200)

    def test_upgrade_early_v10_attachment_constraint(self):
        # Uma versão inicial v10 poderia ter UNIQUE(storage_key); a migração
        # deve removê-lo sem apagar linhas ou exigir intervenção manual.
        with db.session() as con:
            con.execute('ALTER TABLE question_attachments RENAME TO question_attachments_previous')
            con.execute('''CREATE TABLE question_attachments (
                id TEXT PRIMARY KEY,question_id TEXT NOT NULL REFERENCES questions(id),
                storage_key TEXT NOT NULL UNIQUE,filename TEXT NOT NULL,media_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL)''')
            con.execute('DROP TABLE question_attachments_previous')
        db.init_db()
        indexes=db.rows('PRAGMA index_list(question_attachments)')
        for idx in indexes:
            columns=[x['name'] for x in db.rows('PRAGMA index_info("'+idx['name']+'")')]
            self.assertFalse(idx['unique'] and columns==['storage_key'])

    def test_original_file_never_transfers_with_single_item(self):
        source=self.clients['teach100'];target=self.clients['private100']
        coll=next(x['id'] for x in source.get('/api/bank/collections').json()['collections'] if x['kind']=='personal')
        doc=Document();doc.add_paragraph(TEXT)
        buff=io.BytesIO();doc.save(buff)
        uploaded=source.post('/api/bank/import/file',params={'collection_id':coll,'filename':'duas-questoes.docx'},
                             content=buff.getvalue(),headers={'Content-Type':'application/octet-stream'})
        self.assertEqual(uploaded.status_code,200)
        batch=uploaded.json()['batch_id']
        items=source.get('/api/bank/batches/'+batch).json()['items']
        self.assertEqual(len(items),2)
        preview=source.post('/api/accounts/link/preview',json={'target_email':'private100@example.org',
                'target_password':'valid-password-100'}).json()
        self.assertEqual(source.post('/api/accounts/link/confirm',json={
            'challenge':preview['challenge'],'question_ids':[items[0]['id']],'confirm':True}).status_code,200)
        self.assertEqual(target.get('/api/bank/search').json()['total'],1)
        self.assertEqual(source.get('/api/bank/search',params={'collection_id':coll}).json()['total'],1)
        self.assertIn(target.get('/api/bank/batches/'+batch+'/original').status_code,(403,404))
        self.assertEqual(source.get('/api/bank/batches/'+batch+'/original').status_code,200)

    def test_link_specific_professor_and_revoke_open_session(self):
        c1=self.clients['teach100'];c2=self.clients['teach200'];coord=self.clients['coord100']
        personal,batch,items=self.create_questions('teach100')
        other,_,items_other=self.create_questions('teach200')
        school,batch_school,inst_items=self.create_questions('teach100','school')
        with db.session() as con:
            con.execute('''INSERT INTO questions(id,source,source_key,discipline,topic,prompt,
                  creator_id,school_id,status,rights_status) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                  ('ambiguous-legacy-1','Legado','ambiguous-legacy-1','Física','Cinemática',
                   'Questão antiga com origem institucional ambígua','teach100','escola-x','published','demo'))
        before=coord.get('/api/bank/search',params={'collection_id':school}).json()
        self.assertEqual(before['total'],1 if not inst_items else 2)
        # Conta de destino existente, credencial comprovada e e-mail verificado.
        preview=c1.post('/api/accounts/link/preview',json={'target_email':'private100@example.org',
                  'target_password':'valid-password-100'})
        self.assertEqual(preview.status_code,200,preview.text)
        info=preview.json();self.assertEqual({x['id'] for x in info['eligible']},{x['id'] for x in items})
        self.assertEqual(info['ambiguous_legacy_count'],1)
        self.assertNotIn(items_other[0]['id'],{x['id'] for x in info['eligible']})
        out=c1.post('/api/accounts/link/confirm',json={'challenge':info['challenge'],
                  'question_ids':[x['id'] for x in items],'confirm':True})
        self.assertEqual(out.status_code,200,out.text)
        self.assertEqual(out.json()['transferred'],2)
        self.assertEqual(db.one('SELECT registered_by FROM question_records WHERE question_id=?',(items[0]['id'],))['registered_by'],'teach100')
        retry=c1.post('/api/accounts/link/confirm',json={'challenge':info['challenge'],
                  'question_ids':[x['id'] for x in items],'confirm':True})
        self.assertTrue(retry.json()['already_confirmed'])
        self.assertEqual(c1.get('/api/bank/search',params={'collection_id':personal}).json()['total'],0)
        target=self.clients['private100'].get('/api/bank/search').json()
        self.assertEqual(target['total'],2)
        self.assertIn(c2.get('/api/questions/'+items[0]['id']).status_code,(403,404))
        impact=coord.get('/api/accounts/school/escola-x/members/teach100/impact')
        self.assertEqual(impact.status_code,200)
        self.assertEqual(coord.post('/api/accounts/school/escola-x/members/teach100/end',json={'confirm':True}).status_code,200)
        db.init_db()  # uma inicialização posterior não pode reativar o professor
        self.assertNotIn('escola-x',[x['id'] for x in c1.get('/api/me').json()['schools']])
        self.assertEqual(c1.get('/api/classes').json(),[])
        self.assertEqual(c1.get('/api/bank/search').json()['total'],0)
        self.assertEqual(c1.get('/api/pedagogy/my-classes-summary').json(),[])
        self.assertEqual(c1.get('/api/pedagogy/attention').json()['critical_topics'],[])
        self.assertEqual(c1.get('/api/pedagogy/schedule').json(),[])
        self.assertEqual(c1.get('/api/exams').json(),[])
        self.assertEqual(coord.get('/api/bank/search',params={'collection_id':school}).json()['total'],2)
        self.assertEqual(self.clients['private100'].get('/api/bank/search').json()['total'],2)

    def test_transfer_confirmed_private_preferences_and_retry_guard(self):
        source=self.clients['teach100'];target=self.clients['private100']
        coll,batch,items=self.create_questions('teach100')
        saved=source.put('/api/accounts/personal/preferences',json={
            'preferred_subject':'Física','review_layout':'compact'})
        self.assertEqual(saved.status_code,200,saved.text)
        preview=source.post('/api/accounts/link/preview',json={
            'target_email':'private100@example.org','target_password':'valid-password-100'}).json()
        self.assertEqual(preview['personal_preferences']['preferred_subject'],'Física')
        payload={'challenge':preview['challenge'],'question_ids':[items[0]['id']],
                 'include_personal_preferences':True,'confirm':True}
        result=source.post('/api/accounts/link/confirm',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertTrue(result.json()['preferences_transferred'])
        self.assertEqual(target.get('/api/accounts/personal/preferences').json(),{
            'preferred_subject':'Física','review_layout':'compact'})
        again=source.post('/api/accounts/link/confirm',json=payload)
        self.assertEqual(again.status_code,200,again.text)
        self.assertTrue(again.json()['already_confirmed'])
        changed=dict(payload,question_ids=[items[1]['id']])
        self.assertEqual(source.post('/api/accounts/link/confirm',json=changed).status_code,409)

    def test_coordinator_closes_dedicated_access(self):
        coord=self.clients['coord100'];teacher=self.clients['teach200']
        preview=coord.get('/api/accounts/school/escola-x/members/teach200/impact')
        self.assertTrue(preview.json()['may_close_dedicated_account'])
        closed=coord.post('/api/accounts/school/escola-x/members/teach200/close-institutional-access',
                          json={'confirm':True})
        self.assertEqual(closed.status_code,200,closed.text)
        self.assertEqual(teacher.get('/api/me').status_code,401)
        self.assertEqual(db.one('SELECT active FROM users WHERE id=?',('teach200',))['active'],0)
        self.assertEqual(db.one('SELECT status FROM school_memberships WHERE user_id=?',('teach200',))['status'],'revoked')

    def test_institutional_close_requires_exclusive_credential(self):
        teacher=self.clients['teach100'];coord=self.clients['coord100']
        with db.session() as con:
            con.execute('INSERT INTO school_memberships(user_id,school_id) VALUES(?,?)',('teach100','escola-y'))
        denied=teacher.post('/api/accounts/institutional/close',params={
            'password':'valid-password-100','confirm':'true'})
        self.assertEqual(denied.status_code,409,denied.text)
        with db.session() as con:
            con.execute("UPDATE school_memberships SET status='revoked' WHERE user_id=? AND school_id=?",
                        ('teach100','escola-y'))
            con.execute('INSERT INTO verified_emails(user_id,email) VALUES(?,?)',
                        ('teach100','pessoal100@example.org'))
        impact=coord.get('/api/accounts/school/escola-x/members/teach100/impact').json()
        self.assertFalse(impact['may_close_dedicated_account'])
        self.assertFalse(impact['verified_personal_access'])  # o alias é da mesma credencial
        self.assertTrue(impact['personal_alias_on_this_credential'])
        denied=teacher.post('/api/accounts/institutional/close',params={
            'password':'valid-password-100','confirm':'true'})
        self.assertEqual(denied.status_code,409,denied.text)
        self.assertTrue(db.one('SELECT active FROM users WHERE id=?',('teach100',))['active'])

    def test_invite_existing_identity_and_personal_email_policy(self):
        coord=self.clients['coord100']
        created=coord.post('/api/accounts/school/invite',json={
            'school_id':'escola-x','name':'Docente já cadastrado','email':'teach200@example.org'})
        self.assertEqual(created.status_code,200,created.text)
        invitation=created.json()['development_token']
        accepted=coord.post('/api/accounts/school/accept',json={
            'token':invitation,'password':'valid-password-100'})
        self.assertEqual(accepted.status_code,200,accepted.text)
        self.assertTrue(accepted.json()['existing_account'])
        self.assertEqual(accepted.json()['user_id'],'teach200')
        denied=self.clients['teach200'].post('/api/accounts/personal-email/challenge',json={
            'email':'teacher.private@example.net'})
        self.assertEqual(denied.status_code,403)
        allowed=coord.post('/api/accounts/school/policy',json={
            'school_id':'escola-x','allow_personal_email':True})
        self.assertEqual(allowed.status_code,200)
        challenge=self.clients['teach200'].post('/api/accounts/personal-email/challenge',json={
            'email':'teacher.private@example.net'})
        self.assertEqual(challenge.status_code,200,challenge.text)
        code=challenge.json()['development_code']
        verified=self.clients['teach200'].post('/api/accounts/personal-email/verify',json={'code':code})
        self.assertEqual(verified.status_code,200)
        activation=self.clients['teach200'].post('/api/accounts/personal/activate')
        self.assertEqual(activation.status_code,200,activation.text)
        alias=TestClient(app)
        self.assertEqual(alias.post('/api/auth/login',json={
            'email':'teacher.private@example.net','password':'valid-password-100'}).status_code,200)
        alias.close()


if __name__=='__main__':unittest.main()
