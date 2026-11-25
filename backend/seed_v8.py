"""Migração idempotente da demonstração v8, mantendo a versão histórica intacta."""
import json
import secrets
from copy import deepcopy
from pathlib import Path
from .db import init_db, session, ROOT
from .auth import password_hash
from .seed_legacy import sid, SCHOOL_CLASS


def migrate():
    init_db()
    src=json.loads((ROOT/'data/legacy_full_demo.json').read_text('utf8'))['db']
    with session() as c:
        # A coordenação da escola X não administra Y/Z.
        c.execute('INSERT OR IGNORE INTO coordinator_schools(user_id,school_id) VALUES(?,?)',('coord-demo','escola-x'))
        # Coordenações fictícias independentes, uma por instituição.
        # Apenas o professor Rafael simula assinatura individual.
        for cid, sid_, name, email in [
            ('coord-y-demo', 'escola-y', 'Coordenação Escola Y', 'coordenacao.y@cognix.test'),
            ('coord-z-demo', 'escola-z', 'Coordenação Escola Z', 'coordenacao.z@cognix.test'),
        ]:
            if not c.execute('SELECT 1 FROM users WHERE id=?',(cid,)).fetchone():
                password=secrets.token_urlsafe(17)
                c.execute('INSERT INTO users(id,name,email,password_hash,role) VALUES(?,?,?,?,?)',
                          (cid,name,email,password_hash(password),'coord'))
                with (ROOT/'data/ACESSOS-DEMO-LOCAL.txt').open('a',encoding='utf8') as out:
                    out.write(f'{email} | {password}\n')
            c.execute('INSERT OR IGNORE INTO coordinator_schools(user_id,school_id) VALUES(?,?)',(cid,sid_))
        # Adiciona um professor fictício de Física na escola X para preservar as turmas da fonte.
        if not c.execute("SELECT 1 FROM users WHERE id='teacher-physics-x'").fetchone():
            pw=secrets.token_urlsafe(16)
            c.execute("INSERT INTO users(id,name,email,password_hash,role) VALUES(?,?,?,?,?)",('teacher-physics-x','Prof. Caio Neri','caio.neri@cognix.test',password_hash(pw),'prof'))
            # credencial independente da assinatura individual
            f=ROOT/'data/ACESSOS-DEMO-LOCAL.txt'
            with f.open('a',encoding='utf8') as fo:fo.write(f'caio.neri@cognix.test | {pw}\n')
        # Atribuições solicitadas para assinatura: X Matemática / Y Física / Z Matemática e Física.
        c.execute("DELETE FROM teaching_assignments WHERE teacher_id='teacher-demo'")
        c.execute("DELETE FROM teaching_assignments WHERE teacher_id='teacher-math' AND class_id IN ('x-1b','x-2a','x-9a','x-3a') AND subject='Física'")
        # Matemática X mantém André (professor original) e pode ter Rafael como docente vinculado.
        for cid in ['x-9a','x-1b','x-2a','x-3a']:
            if c.execute('SELECT 1 FROM classes WHERE id=?',(cid,)).fetchone():
                c.execute('INSERT OR IGNORE INTO teaching_assignments VALUES(?,?,?,?)',(f'demo-v8-x-{cid}-mat','teacher-demo',cid,'Matemática'))
        for cid in ['y-1b','y-3a']:
            c.execute('INSERT OR IGNORE INTO teaching_assignments VALUES(?,?,?,?)',(f'demo-v8-y-{cid}-fis','teacher-demo',cid,'Física'))
        for cid in ['z-2a','z-3a']:
            for sub in ['Matemática','Física']:
                c.execute('INSERT OR IGNORE INTO teaching_assignments VALUES(?,?,?,?)',(f'demo-v8-z-{cid}-{sub}','teacher-demo',cid,sub))
        # Reatribui Física X a outro docente de demonstração e Matemática Y a André.
        c.execute("DELETE FROM teaching_assignments WHERE teacher_id='teacher-math' AND class_id LIKE 'y-%' AND subject='Física'")
        for cid in ['x-1b','x-2a','x-3a']:
            c.execute('INSERT OR IGNORE INTO teaching_assignments VALUES(?,?,?,?)',(f'demo-v8-fisx-{cid}','teacher-physics-x',cid,'Física'))
        for cid in ['y-1b','y-3a']:
            c.execute('INSERT OR IGNORE INTO teaching_assignments VALUES(?,?,?,?)',(f'demo-v8-maty-{cid}','teacher-math',cid,'Matemática'))
        # Completa Física para escola Z sem remover as avaliações fictícias originais.
        for cid,group in [('z-2a','d'),('z-3a','m')]:
            orig=next((t for t in src['turmas'] if t['escolaId']=='escola-x' and t['grupo'].split('-')[-1]==group and t['disciplina']=='Física'),None)
            if not orig:continue
            for v in orig['avaliacoes']:
                a_id=f'demo-v8-fis-z-{cid}-{v["id"]}'
                c.execute('INSERT OR IGNORE INTO assessments(id,class_id,subject,name,weight,scheduled_on,topics_json,origin) VALUES(?,?,?,?,?,?,?,?)',
                    (a_id,cid,'Física',v['nome'],v['peso'],v.get('data',''),json.dumps(v['temas'],ensure_ascii=False),'Demo adicional v8'))
            for a in orig['alunos']:
                for v in orig['avaliacoes']:
                    score=orig['notas'].get(a['id'],{}).get(v['id'])
                    if score is None:continue
                    student=sid('z_'+a['id'])
                    if not c.execute('SELECT 1 FROM users WHERE id=?',(student,)).fetchone():continue
                    g_id=f'demo-v8-zfis-{cid}-{student}-{v["id"]}'
                    c.execute('INSERT OR IGNORE INTO grades(id,class_id,subject,student_id,assessment,score) VALUES(?,?,?,?,?,?)',
                        (g_id,cid,'Física',student,v['nome'],score))
                    for topic,val in orig['temaNotas'].get(a['id'],{}).get(v['id'],{}).items():
                        c.execute('INSERT OR IGNORE INTO grade_topics(class_id,subject,student_id,assessment,topic,score) VALUES(?,?,?,?,?,?)',
                          (cid,'Física',student,v['nome'],topic,val))
    print('Migração v8: escolas isoladas, assinatura individual X Matemática / Y Física / Z Matemática+Física.')

if __name__=='__main__':migrate()
