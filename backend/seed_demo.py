"""Somente desenvolvimento: contas fictícias, atribuições X/Y/Z e questões autorais de exemplo."""
import json, secrets, hashlib, sys
from pathlib import Path
from .db import init_db, session, ROOT
from .auth import password_hash

ACCOUNTS=[
 ('coord-demo','Marina Almeida','coordenacao@cognix.test','coord'),
 ('teacher-demo','Rafael Monteiro','rafael.monteiro@cognix.test','prof'),
 ('teacher-math','André Valença','andre.valenca@cognix.test','prof'),
 ('student-demo','Alice Fontes','alice.fontes@cognix.test','aluno'),
]

def seed():
    init_db()
    passwords={}
    with session() as db:
        for id,name,email,role in ACCOUNTS:
            if db.execute('SELECT 1 FROM users WHERE id=?',(id,)).fetchone():continue
            password=secrets.token_urlsafe(15)
            db.execute('INSERT INTO users (id,name,email,password_hash,role) VALUES(?,?,?,?,?)',
                (id,name,email,password_hash(password),role))
            passwords[email]=password
        subjects=[('x-1b','Física'),('x-3a','Física'),('y-1b','Física'),('y-1b','Matemática'),
                  ('y-2a','Física'),('y-3a','Matemática'),('z-2a','Matemática'),('z-3a','Matemática')]
        for class_id,subj in subjects:
            db.execute('INSERT OR IGNORE INTO teaching_assignments (id,teacher_id,class_id,subject) VALUES(?,?,?,?)',
                       ('a-'+class_id+'-'+('mat' if subj=='Matemática' else 'fis'),'teacher-demo',class_id,subj))
        db.execute('INSERT OR IGNORE INTO teaching_assignments (id,teacher_id,class_id,subject) VALUES(?,?,?,?)',
                   ('a-x-3a-math','teacher-math','x-3a','Matemática'))
        for cid in ('x-3a',):db.execute('INSERT OR IGNORE INTO enrollments(user_id,class_id) VALUES(?,?)',('student-demo',cid))
        for subject,assessment,score in [('Física','Prova 1',7.8),('Matemática','Simulado 1',8.1)]:
            db.execute('INSERT OR IGNORE INTO grades(id,class_id,subject,student_id,assessment,score) VALUES(?,?,?,?,?,?)',
                (f'g-{subject}-{assessment}','x-3a',subject,'student-demo',assessment,score))
        legacy=json.loads((ROOT/'data/questions_demo.json').read_text())
        for i,q in enumerate(legacy):
            topic=str(q.get('tema') or '')
            area={'Matemática':'Matemática','Física':'Ciências da Natureza','Química':'Ciências da Natureza',
                  'Biologia':'Ciências da Natureza','Geografia':'Ciências Humanas','Linguagens':'Linguagens'}.get(q['disciplina'],'Outra')
            alt=[{'letter':chr(65+j),'text':str(text),'file':''} for j,text in enumerate(q.get('alternativas',[]))]
            answer=q.get('resposta','')
            correct=chr(65+int(answer)) if str(answer).isdigit() and int(answer)<len(alt) else ''
            db.execute('''INSERT OR IGNORE INTO questions(id,source,source_key,area,discipline,title,context,prompt,alternatives_json,media_json,
                 correct_letter,topic,difficulty,status,rights_status,source_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (f'demo-{i+1}','Cognix Demo',str(i+1),area,q['disciplina'],f'{q["disciplina"]} · {topic}',str(q.get('enunciado') or ''),'',
                  json.dumps(alt,ensure_ascii=False),'[]',correct,topic,str(q.get('dificuldade') or ''),'published' if correct else 'review','demo',''))
    path=ROOT/'data/ACESSOS-DEMO-LOCAL.txt'
    if passwords:
        path.write_text('CONTAS FICTÍCIAS DE DEMONSTRAÇÃO — NÃO USE EM PRODUÇÃO\n\n'+''.join(f'{email} | {pw}\n' for email,pw in passwords.items()),encoding='utf-8')
        print('Contas criadas. Credenciais em:',path,'\n'+path.read_text(),flush=True)
    else:print('Contas já existem. Não foram recriadas nem tiveram suas senhas redefinidas.')
    print('Turmas X/Y/Z, vínculos e 57 questões fictícias da versão anterior estão no SQLite (45 de múltipla escolha/VF e 12 discursivas em revisão). Nenhum item de demonstração é ENEM real.')
if __name__=='__main__':seed()
