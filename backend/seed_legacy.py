"""Importação idempotente dos DADOS FICTÍCIOS do HTML Cognix Multiescolas.

Executar: python -m backend.seed_legacy
Não substitui notas, senhas nem vínculos já editados. O JSON foi extraído da função
seed() + migrarMultiEscola() do HTML original, sem inventar novos valores.
"""
import csv
import io
import json
import secrets
from collections import Counter
from pathlib import Path

from .db import ROOT, init_db, session
from .auth import password_hash

DATA_FILE = ROOT / 'data' / 'legacy_full_demo.json'
CREDS_FILE = ROOT / 'data' / 'ACESSOS-DEMO-LOCAL.txt'
TEACHER_CREDS_FILE = ROOT / 'data' / 'ACESSOS-PROFESSORES-DEMO.txt'
STUDENT_CREDS_FILE = ROOT / 'data' / 'ACESSOS-ALUNOS-DEMO.csv'

TEACHERS = {
    'prof-mat': ('teacher-math', 'andre.valenca@cognix.test'),
    'prof-fis': ('teacher-demo', 'rafael.monteiro@cognix.test'),
    'prof-qui': ('legacy-teacher-qui', 'jorge.costa@cognix.test'),
    'prof-bio': ('legacy-teacher-bio', 'victor.leal@cognix.test'),
    'prof-lin': ('legacy-teacher-lin', 'mila@cognix.test'),
    'prof-geo': ('legacy-teacher-geo', 'leonan.lopes@cognix.test'),
}
SCHOOL_CLASS = {
    'escola-x': {'n': 'x-9a', 'u': 'x-1b', 'd': 'x-2a', 'm': 'x-3a'},
    'escola-y': {'u': 'y-1b', 'd': 'y-2a', 'm': 'y-3a'},
    'escola-z': {'d': 'z-2a', 'm': 'z-3a'},
}


def sid(legacy_id):
    return 'student-demo' if legacy_id == 'm0' else 'legacy-student-' + legacy_id


def password_for_demo():
    return secrets.token_urlsafe(16)


def read_known_credentials():
    # Preservar as senhas originais já distribuídas. Nunca tentar recuperá-las do hash.
    existing = {}
    if CREDS_FILE.is_file():
        for line in CREDS_FILE.read_text(encoding='utf8').splitlines():
            if ' | ' in line:
                mail, pw = line.split(' | ', 1)
                if '@' in mail and pw.strip():
                    existing[mail.strip()] = pw.strip()
    return existing


def write_credentials(creds):
    header = ('ACESSOS FICTÍCIOS PARA TESTE LOCAL — NÃO PUBLICAR / NÃO USAR EM PRODUÇÃO\n'
              'Cada conta exige seu próprio e-mail e senha. Senhas da demonstração\n'
              'não substituem um provisionamento seguro em produção.\n'
              'As senhas existentes são preservadas ao executar novamente a importação.\n\n')
    CREDS_FILE.write_text(header + ''.join(f'{mail} | {pw}\n' for mail, pw in sorted(creds.items())), encoding='utf8')
    lines = ['CONTAS FICTÍCIAS DOS PROFESSORES DO HTML ORIGINAL',
             'Senha individual por docente; uso somente local.','']
    for _, (user_id, mail) in TEACHERS.items():
        lines.append(f'{mail} | {creds.get(mail, "(senha anterior não disponível; redefina na conta)")}')
    TEACHER_CREDS_FILE.write_text('\n'.join(lines)+'\n', encoding='utf8')


def import_legacy():
    init_db()
    payload = json.loads(DATA_FILE.read_text(encoding='utf8'))
    source, profiles = payload['db'], payload['perfis']
    credentials = read_known_credentials()
    new_students = []
    counters = Counter()
    with session() as db:
        for legacy_key, (user_id, email) in TEACHERS.items():
            name = profiles[legacy_key]['nome']
            found = db.execute('SELECT id FROM users WHERE id=?', (user_id,)).fetchone()
            if not found:
                pwd = password_for_demo()
                db.execute('INSERT INTO users(id,name,email,password_hash,role) VALUES(?,?,?,?,?)',
                           (user_id, name, email, password_hash(pwd), 'prof'))
                credentials[email] = pwd
                counters['professores_novos'] += 1
            elif legacy_key == 'prof-mat':
                # Conta existente do professor André; identidade visual original do protótipo.
                db.execute("UPDATE users SET name='Prof. André' WHERE id=? AND name='André Valença'",(user_id,))
            elif legacy_key == 'prof-fis':
                db.execute("UPDATE users SET name='Prof. Rafael Monteiro' WHERE id=? AND name='Rafael Monteiro'",(user_id,))
        # Reaproveitar a escola X/Y/Z já existente, incluindo seus IDs.
        for e in source['escolas']:
            db.execute('''INSERT OR IGNORE INTO schools(id,name,subtitle,city,initials,color)
                          VALUES(?,?,?,?,?,?)''', (e['id'],e['nome'],e['fantasia'],e['cidade'],e['sigla'],e['cor']))
        for school_id, groups in SCHOOL_CLASS.items():
            for group, class_id in groups.items():
                ts=next((t for t in source['turmas'] if t['escolaId']==school_id and t['grupo'].split('-')[-1]==group),None)
                if not ts: continue
                db.execute('INSERT OR IGNORE INTO classes(id,school_id,name,grade) VALUES(?,?,?,?)',
                           (class_id,school_id,ts['nome'],ts['serie']))
        # Alunos do HTML: IDs por grupo, compartilhados entre as disciplinas da mesma turma.
        unique_students = {}
        for t in source['turmas']:
            for student in t['alunos']:
                unique_students.setdefault(student['id'], student['nome'])
        for legacy_id, name in sorted(unique_students.items()):
            user_id = sid(legacy_id)
            email = 'alice.fontes@cognix.test' if legacy_id=='m0' else f'aluno.{legacy_id}@cognix.test'
            if not db.execute('SELECT id FROM users WHERE id=?',(user_id,)).fetchone():
                pwd = password_for_demo()
                db.execute('INSERT INTO users(id,name,email,password_hash,role) VALUES(?,?,?,?,?)',
                           (user_id,name,email,password_hash(pwd),'aluno'))
                new_students.append((name,email,pwd))
                if legacy_id == 'm0':credentials[email] = pwd
                counters['alunos_novos'] += 1
        for t in source['turmas']:
            school_id = t['escolaId']
            group = t['grupo'].split('-')[-1]
            class_id = SCHOOL_CLASS[school_id][group]
            subject = t['disciplina']
            teacher_id = TEACHERS[t['prof']][0]
            assignment_id = f'legacy-assign-{school_id}-{group}-{t["prof"]}-{subject}'
            db.execute('''INSERT OR IGNORE INTO teaching_assignments(id,teacher_id,class_id,subject)
                       VALUES(?,?,?,?)''', (assignment_id,teacher_id,class_id,subject))
            counters['turmas_disciplina'] += 1
            for student in t['alunos']:
                db.execute('INSERT OR IGNORE INTO enrollments(user_id,class_id) VALUES(?,?)',
                           (sid(student['id']),class_id))
            for v in t['avaliacoes']:
                asses_id = f'legacy-av-{class_id}-{subject}-{v["id"]}'
                db.execute('''INSERT OR IGNORE INTO assessments
                   (id,class_id,subject,name,weight,scheduled_on,topics_json,origin)
                   VALUES(?,?,?,?,?,?,?,?)''',
                   (asses_id,class_id,subject,v['nome'],float(v['peso']),v.get('data',''),
                    json.dumps(v['temas'],ensure_ascii=False),'HTML multiescolas'))
                counters['avaliacoes'] += 1
            for legacy_student, score_map in t['notas'].items():
                for av_id, score in score_map.items():
                    if score is None: continue
                    assessment = next((v for v in t['avaliacoes'] if v['id']==av_id),None)
                    if not assessment:continue
                    grade_id = f'legacy-grade-{class_id}-{subject}-{legacy_student}-{av_id}'
                    db.execute('''INSERT OR IGNORE INTO grades(id,class_id,subject,student_id,assessment,score)
                                  VALUES(?,?,?,?,?,?)''',
                               (grade_id,class_id,subject,sid(legacy_student),assessment['nome'],float(score)))
                    counters['notas_html'] += 1
                    for topic, topic_score in t.get('temaNotas',{}).get(legacy_student,{}).get(av_id,{}).items():
                        db.execute('''INSERT OR IGNORE INTO grade_topics
                          (class_id,subject,student_id,assessment,topic,score)
                          VALUES(?,?,?,?,?,?)''',
                          (class_id,subject,sid(legacy_student),assessment['nome'],topic,float(topic_score)))
                        counters['notas_topicos'] += 1
        for a in source['agenda']:
            t = next((t for t in source['turmas'] if t['id']==a['turma']), None)
            if not t: continue
            sc, group = t['escolaId'], t['grupo'].split('-')[-1]
            cl = SCHOOL_CLASS[sc][group]
            db.execute('''INSERT OR IGNORE INTO lesson_schedule
                (id,class_id,subject,teacher_id,weekday,slot,room,topic,plan,status,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                ('legacy-'+a['id'],cl,t['disciplina'],TEACHERS[t['prof']][0],
                 int(a['dia']),int(a['slot']),a['sala'],a['topico'],a['plano'],a['status'],a['obs']))
            counters['aulas'] += 1
        for legacy_id, years in source.get('historico',{}).items():
            for grade_label, topics in years.items():
                for topic, score in topics.items():
                    db.execute('''INSERT OR IGNORE INTO student_topic_history
                         (student_id,grade_label,topic,score) VALUES(?,?,?,?)''',
                         (sid(legacy_id),grade_label,topic,float(score)))
                    counters['historico_topicos'] += 1
        for e in source['escolas']:
            db.execute('INSERT OR IGNORE INTO school_configuration(school_id,settings_json) VALUES(?,?)',
                (e['id'],json.dumps({'mediaAprov':source.get('mediaAprov',6),
                          'mediaRec':source.get('mediaRec',4),
                          'avaliacoes':source.get('config',{})},ensure_ascii=False)))
    # Não recriar senhas se importação for repetida. Credenciais antigas já distribuídas são mantidas.
    write_credentials(credentials)
    if new_students:
        already=[]
        if STUDENT_CREDS_FILE.is_file():
            with STUDENT_CREDS_FILE.open(encoding='utf-8',newline='') as fp:
                already=list(csv.DictReader(fp))
        seen={r['email'] for r in already}
        with STUDENT_CREDS_FILE.open('w',encoding='utf-8',newline='') as fp:
            writer=csv.DictWriter(fp,fieldnames=['nome','email','senha'])
            writer.writeheader()
            writer.writerows(already)
            writer.writerows({'nome':n,'email':e,'senha':p} for n,e,p in new_students if e not in seen)
    print('Dados fictícios do HTML importados (sem sobrescrever dados existentes):',dict(counters))
    print('Acessos dos professores:', TEACHER_CREDS_FILE)
    return counters

if __name__=='__main__':
    import_legacy()
