"""Persistência SQLite com migrations idempotentes para o protótipo Cognix."""
import os
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent.parent
DB_FILE = Path(os.getenv('COGNIX_DB', str(ROOT / 'data' / 'cognix.sqlite3')))
if not DB_FILE.is_absolute():
    DB_FILE = ROOT / DB_FILE

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('coord','prof','aluno')),
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS coordinator_schools (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
 PRIMARY KEY(user_id,school_id)
);
CREATE TABLE IF NOT EXISTS studio_states (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 school_id TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id,school_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS invitations (
  code_hash TEXT PRIMARY KEY, role TEXT NOT NULL, email TEXT, created_by TEXT REFERENCES users(id),
  used_by TEXT REFERENCES users(id), expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schools (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, subtitle TEXT NOT NULL DEFAULT '', city TEXT DEFAULT '',
  initials TEXT, color TEXT
);
CREATE TABLE IF NOT EXISTS school_memberships (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  PRIMARY KEY(user_id,school_id)
);
CREATE TABLE IF NOT EXISTS school_join_requests (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_by TEXT REFERENCES users(id),
  reviewed_at TEXT,
  UNIQUE(user_id,school_id)
);
CREATE INDEX IF NOT EXISTS idx_school_join_requests_school ON school_join_requests(school_id,status);
CREATE TABLE IF NOT EXISTS classes (
  id TEXT PRIMARY KEY, school_id TEXT NOT NULL REFERENCES schools(id), name TEXT NOT NULL, grade TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teaching_assignments (
  id TEXT PRIMARY KEY, teacher_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  class_id TEXT NOT NULL REFERENCES classes(id) ON DELETE CASCADE, subject TEXT NOT NULL,
  UNIQUE(teacher_id,class_id,subject)
);
CREATE TABLE IF NOT EXISTS enrollments (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  class_id TEXT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  PRIMARY KEY(user_id,class_id)
);
CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, source_key TEXT NOT NULL,
  year INTEGER, question_number INTEGER, area TEXT NOT NULL DEFAULT '',
  discipline TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '', context TEXT NOT NULL DEFAULT '',
  prompt TEXT NOT NULL DEFAULT '', alternatives_json TEXT NOT NULL DEFAULT '[]',
  media_json TEXT NOT NULL DEFAULT '[]', correct_letter TEXT NOT NULL DEFAULT '',
  topic TEXT NOT NULL DEFAULT '', difficulty TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'review' CHECK (status IN ('review','published','archived')),
  rights_status TEXT NOT NULL DEFAULT 'pending', source_url TEXT NOT NULL DEFAULT '',
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source,source_key)
);
CREATE TABLE IF NOT EXISTS question_school_classifications (
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  discipline TEXT NOT NULL,
  topic TEXT NOT NULL DEFAULT '',
  difficulty TEXT NOT NULL DEFAULT '',
  classified_by TEXT NOT NULL REFERENCES users(id),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(school_id,question_id)
);
CREATE INDEX IF NOT EXISTS idx_question_school_discipline
  ON question_school_classifications(school_id,discipline);
CREATE INDEX IF NOT EXISTS idx_questions_filter ON questions(source,year,area,status);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(discipline,topic);
CREATE TABLE IF NOT EXISTS exam_sets (
  id TEXT PRIMARY KEY, creator_id TEXT NOT NULL REFERENCES users(id),
  class_id TEXT NOT NULL REFERENCES classes(id), subject TEXT NOT NULL,
  title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS exam_items (
  exam_id TEXT NOT NULL REFERENCES exam_sets(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL REFERENCES questions(id), position INTEGER NOT NULL,
  PRIMARY KEY (exam_id,question_id)
);
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), question_id TEXT NOT NULL REFERENCES questions(id),
  chosen_letter TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS question_error_tags (
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  letter TEXT NOT NULL CHECK(letter IN ('A','B','C','D','E')),
  description TEXT NOT NULL,
  author_id TEXT NOT NULL REFERENCES users(id),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(school_id,question_id,letter)
);
CREATE TABLE IF NOT EXISTS grades (
  id TEXT PRIMARY KEY, class_id TEXT NOT NULL REFERENCES classes(id),
  subject TEXT NOT NULL, student_id TEXT NOT NULL REFERENCES users(id),
  assessment TEXT NOT NULL, score REAL NOT NULL CHECK(score>=0 AND score<=10),
  UNIQUE(class_id,subject,student_id,assessment)
);
CREATE TABLE IF NOT EXISTS assessments (
  id TEXT PRIMARY KEY, class_id TEXT NOT NULL REFERENCES classes(id),
  subject TEXT NOT NULL, name TEXT NOT NULL, weight REAL NOT NULL DEFAULT 1,
  scheduled_on TEXT NOT NULL DEFAULT '', topics_json TEXT NOT NULL DEFAULT '[]',
  origin TEXT NOT NULL DEFAULT '', UNIQUE(class_id,subject,name)
);
CREATE TABLE IF NOT EXISTS grade_topics (
  class_id TEXT NOT NULL REFERENCES classes(id), subject TEXT NOT NULL,
  student_id TEXT NOT NULL REFERENCES users(id), assessment TEXT NOT NULL,
  topic TEXT NOT NULL, score REAL NOT NULL CHECK(score>=0 AND score<=10),
  PRIMARY KEY(class_id,subject,student_id,assessment,topic)
);
CREATE TABLE IF NOT EXISTS lesson_schedule (
  id TEXT PRIMARY KEY, class_id TEXT NOT NULL REFERENCES classes(id), subject TEXT NOT NULL,
  teacher_id TEXT NOT NULL REFERENCES users(id), weekday INTEGER NOT NULL, slot INTEGER NOT NULL,
  room TEXT NOT NULL, topic TEXT NOT NULL, plan TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'planejada', notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS competency_observations (
  id TEXT PRIMARY KEY, school_id TEXT NOT NULL REFERENCES schools(id),
  class_id TEXT NOT NULL REFERENCES classes(id), subject TEXT NOT NULL,
  student_id TEXT NOT NULL REFERENCES users(id), observer_id TEXT NOT NULL REFERENCES users(id),
  topic TEXT NOT NULL, competency TEXT NOT NULL, evidence_level TEXT NOT NULL,
  observed_on TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_competency_scope ON competency_observations(class_id,subject,topic,observed_on);
CREATE TABLE IF NOT EXISTS pedagogical_interventions (
  id TEXT PRIMARY KEY, school_id TEXT NOT NULL REFERENCES schools(id),
  class_id TEXT NOT NULL REFERENCES classes(id), subject TEXT NOT NULL,
  topic TEXT NOT NULL, creator_id TEXT NOT NULL REFERENCES users(id),
  activity TEXT NOT NULL, applied_on TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_interventions_scope ON pedagogical_interventions(class_id,subject,topic,applied_on);
CREATE TABLE IF NOT EXISTS student_topic_history (
  student_id TEXT NOT NULL REFERENCES users(id), grade_label TEXT NOT NULL,
  topic TEXT NOT NULL, score REAL NOT NULL,
  PRIMARY KEY(student_id,grade_label,topic)
);
CREATE TABLE IF NOT EXISTS school_configuration (
  school_id TEXT PRIMARY KEY REFERENCES schools(id), settings_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_teacher ON lesson_schedule(teacher_id,weekday,slot);
CREATE INDEX IF NOT EXISTS idx_assessments_subject ON assessments(class_id,subject);
CREATE TABLE IF NOT EXISTS student_goals (
  student_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  topic TEXT NOT NULL, target INTEGER NOT NULL DEFAULT 5, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(student_id,school_id,topic)
);
CREATE TABLE IF NOT EXISTS student_preferences (
  student_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  values_json TEXT NOT NULL DEFAULT '[]', hours INTEGER NOT NULL DEFAULT 4,
  feedback_json TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(student_id,school_id)
);
CREATE TABLE IF NOT EXISTS topic_history_scoped (
  student_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  school_id TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  grade_label TEXT NOT NULL, topic TEXT NOT NULL, score REAL NOT NULL,
  origin TEXT NOT NULL DEFAULT 'demo',
  PRIMARY KEY(student_id,school_id,grade_label,topic)
);
CREATE TABLE IF NOT EXISTS grade_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  coordinator_id TEXT NOT NULL REFERENCES users(id), school_id TEXT NOT NULL,
  class_id TEXT NOT NULL, student_id TEXT NOT NULL, subject TEXT NOT NULL,
  assessment TEXT NOT NULL, previous_score REAL, new_score REAL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS import_jobs (
  id TEXT PRIMARY KEY, year TEXT NOT NULL, state TEXT NOT NULL, imported INTEGER NOT NULL DEFAULT 0,
  processed INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT REFERENCES users(id), action TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''

def connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=30000')
    return con

@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_db():
    with session() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript(SCHEMA)
        # Migrações compatíveis com o SQLite da versão anterior.
        # Conta individual: autocadastro docente. Conta institucional: criada exclusivamente pela escola.
        user_columns = {r[1] for r in con.execute('PRAGMA table_info(users)')}
        if 'account_plan' not in user_columns:
            con.execute("ALTER TABLE users ADD COLUMN account_plan TEXT NOT NULL DEFAULT 'school'")
            # O professor fictício multiescolas é o único assinante individual da demonstração.
            con.execute("UPDATE users SET account_plan='individual' WHERE id='teacher-demo' AND role='prof'")
            # Autocadastros antigos sem turmas passam a ser individuais, sem perder o login.
            con.execute("""UPDATE users SET account_plan='individual'
                WHERE role='prof' AND id NOT IN
                    (SELECT teacher_id FROM teaching_assignments)""")
        # Os vínculos históricos passam a aparecer no cadastro da própria escola, sem perder notas.
        con.execute('''INSERT OR IGNORE INTO school_memberships(user_id,school_id)
          SELECT DISTINCT a.teacher_id,c.school_id FROM teaching_assignments a
          JOIN classes c ON c.id=a.class_id JOIN users u ON u.id=a.teacher_id WHERE u.role='prof' ''')
        con.execute('''INSERT OR IGNORE INTO school_memberships(user_id,school_id)
          SELECT DISTINCT e.user_id,c.school_id FROM enrollments e
          JOIN classes c ON c.id=e.class_id JOIN users u ON u.id=e.user_id WHERE u.role='aluno' ''')
        columns = {r[1] for r in con.execute('PRAGMA table_info(invitations)')}
        if 'school_id' not in columns:
            con.execute('ALTER TABLE invitations ADD COLUMN school_id TEXT')
        columns = {r[1] for r in con.execute('PRAGMA table_info(questions)')}
        if 'creator_id' not in columns:
            con.execute('ALTER TABLE questions ADD COLUMN creator_id TEXT')
        if 'school_id' not in columns:
            con.execute('ALTER TABLE questions ADD COLUMN school_id TEXT')
        con.execute('CREATE INDEX IF NOT EXISTS idx_questions_owner_school ON questions(creator_id,school_id,discipline)')
        # v10: vínculo revogável, identidade distinta de credencial e acervos explícitos.
        membership_cols = {r[1] for r in con.execute('PRAGMA table_info(school_memberships)')}
        if 'status' not in membership_cols:
            con.execute("ALTER TABLE school_memberships ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        con.executescript(V10_SCHEMA)
        link_cols={r[1] for r in con.execute('PRAGMA table_info(account_link_challenges)')}
        if 'preferences_transferred' not in link_cols:
            con.execute('ALTER TABLE account_link_challenges ADD COLUMN preferences_transferred INTEGER NOT NULL DEFAULT 0')
        if 'selection_json' not in link_cols:
            con.execute("ALTER TABLE account_link_challenges ADD COLUMN selection_json TEXT NOT NULL DEFAULT '[]'")
        # Correção aditiva de uma versão inicial v10: o mesmo blob físico (SHA)
        # pode pertencer a *mais de uma* questão, mas cada associação é privada.
        for ix in con.execute('PRAGMA index_list(question_attachments)').fetchall():
            ix_columns=[x[2] for x in con.execute('PRAGMA index_info("'+ix[1]+'")').fetchall()]
            if ix[2] and ix_columns==['storage_key']:
                con.execute('''CREATE TABLE question_attachments_rebuild (
                   id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES questions(id),
                   storage_key TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL,
                   size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL)''')
                con.execute('INSERT INTO question_attachments_rebuild SELECT * FROM question_attachments')
                con.execute('DROP TABLE question_attachments')
                con.execute('ALTER TABLE question_attachments_rebuild RENAME TO question_attachments')
                con.execute('CREATE INDEX IF NOT EXISTS idx_attachment_storage_key ON question_attachments(storage_key)')
                break
        # Congela o estado atual dos exames anteriores à migração. Não é possível
        # reconstruir revisões antigas já perdidas; são rotuladas como baseline.
        previous=con.execute('''SELECT i.exam_id,i.question_id,q.title,q.context,q.prompt,
                   q.alternatives_json,q.media_json,q.correct_letter,q.discipline,q.topic,
                   q.difficulty,q.source FROM exam_items i JOIN questions q ON q.id=i.question_id
                   LEFT JOIN exam_item_snapshots snap ON snap.exam_id=i.exam_id AND snap.question_id=i.question_id
                   WHERE snap.exam_id IS NULL''').fetchall()
        for old in previous:
            frozen=dict(old)
            exam_id=frozen.pop('exam_id');question_id=frozen.pop('question_id')
            con.execute('''INSERT INTO exam_item_snapshots(exam_id,question_id,snapshot_json,question_version)
                           VALUES(?,?,?,0)''',(exam_id,question_id,json.dumps(frozen,ensure_ascii=False)))
        # Área Matemática do ENEM corresponde integralmente à disciplina; Natureza exige curadoria local.
        con.execute("UPDATE questions SET discipline='Matemática' WHERE source='ENEM API' AND discipline='' AND area='Matemática'")
        # Campos para erros de aprendizagem e origem da demonstração.
        present = {r[1] for r in con.execute('PRAGMA table_info(attempts)')}
        for col, definition in [('reason', "TEXT NOT NULL DEFAULT ''"),
                                ('origin', "TEXT NOT NULL DEFAULT 'app'"),
                                ('school_id', "TEXT NOT NULL DEFAULT ''")]:
            if col not in present:
                con.execute(f'ALTER TABLE attempts ADD COLUMN {col} {definition}')
        # Metadados das provas sorteadas: migração aditiva sem destruir provas anteriores.
        for table, fields in {
            'exam_sets': [('total_points', 'REAL NOT NULL DEFAULT 10'),
                          ('generation_mode', "TEXT NOT NULL DEFAULT 'manual'"),
                          ('configuration_json', "TEXT NOT NULL DEFAULT '{}'"),
                          ('applied_assessment', "TEXT NOT NULL DEFAULT ''")],
            'exam_items': [('points', 'REAL NOT NULL DEFAULT 0')],
        }.items():
            present = {r[1] for r in con.execute(f'PRAGMA table_info({table})')}
            for field, definition in fields:
                if field not in present:
                    con.execute(f'ALTER TABLE {table} ADD COLUMN {field} {definition}')
        # Histórico da demonstração delimitado pela matrícula em cada instituição.
        con.execute("""INSERT OR IGNORE INTO topic_history_scoped(student_id,school_id,grade_label,topic,score)
          SELECT h.student_id,c.school_id,h.grade_label,h.topic,h.score
          FROM student_topic_history h JOIN enrollments en ON en.user_id=h.student_id
          JOIN classes c ON c.id=en.class_id""")
        for id,name,subtitle,city,initials,color in [
            ('escola-x','Escola X','Colégio Horizonte','Salvador, BA','X','#5366bd'),
            ('escola-y','Escola Y','Instituto Aurora','Salvador, BA','Y','#be8353'),
            ('escola-z','Escola Z','Escola Vale Verde','Lauro de Freitas, BA','Z','#487a75')
        ]:
            con.execute('INSERT OR IGNORE INTO schools VALUES(?,?,?,?,?,?)', (id,name,subtitle,city,initials,color))
        rows=[
            ('x-1b','escola-x','1ª Série B','1ª série EM'),('x-3a','escola-x','3ª Série A','3ª série EM'),
            ('y-1b','escola-y','1ª Série B','1ª série EM'),('y-2a','escola-y','2ª Série A','2ª série EM'),
            ('y-3a','escola-y','3ª Série A','3ª série EM'),('z-2a','escola-z','2ª Série A','2ª série EM'),
            ('z-3a','escola-z','3ª Série A','3ª série EM')
        ]
        con.executemany('INSERT OR IGNORE INTO classes VALUES(?,?,?,?)',rows)

def rows(sql, args=()):
    with session() as con:
        return [dict(x) for x in con.execute(sql,args).fetchall()]

def one(sql,args=()):
    with session() as con:
        r=con.execute(sql,args).fetchone()
        return dict(r) if r else None


V10_SCHEMA = '''
CREATE TABLE IF NOT EXISTS teacher_identities (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS account_identities (
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 identity_id TEXT NOT NULL REFERENCES teacher_identities(id)
);
CREATE INDEX IF NOT EXISTS idx_account_identity ON account_identities(identity_id);
CREATE TABLE IF NOT EXISTS verified_emails (
 user_id TEXT NOT NULL REFERENCES users(id), email TEXT NOT NULL,
 verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id,email), UNIQUE(email)
);
CREATE TABLE IF NOT EXISTS verification_challenges (
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), email TEXT NOT NULL,
 purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
 expires_at TEXT NOT NULL, consumed_at TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_challenge_user ON verification_challenges(user_id,purpose);
CREATE TABLE IF NOT EXISTS school_teacher_invites (
 id TEXT PRIMARY KEY, school_id TEXT NOT NULL REFERENCES schools(id),
 email TEXT NOT NULL, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
 invited_by TEXT NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL,
 accepted_by TEXT REFERENCES users(id), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS school_policy (
 school_id TEXT PRIMARY KEY REFERENCES schools(id),
 allow_personal_email INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS question_collections (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('personal','school')),
 owner_id TEXT REFERENCES users(id), school_id TEXT REFERENCES schools(id),
 name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK ((kind='personal' AND owner_id IS NOT NULL AND school_id IS NULL)
 OR (kind='school' AND school_id IS NOT NULL AND owner_id IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_personal ON question_collections(owner_id) WHERE kind='personal';
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_school ON question_collections(school_id) WHERE kind='school';
CREATE TABLE IF NOT EXISTS question_categories (
 id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES question_collections(id),
 discipline TEXT NOT NULL, topic TEXT NOT NULL, normalized TEXT NOT NULL,
 confirmed_by TEXT REFERENCES users(id),
 UNIQUE(collection_id,discipline,normalized)
);
CREATE TABLE IF NOT EXISTS question_batches (
 id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES question_collections(id),
 uploader_id TEXT NOT NULL REFERENCES users(id), origin_format TEXT NOT NULL,
 filename TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'imported', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(collection_id,uploader_id,content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_batches_collection ON question_batches(collection_id,created_at);
CREATE TABLE IF NOT EXISTS question_import_items (
 batch_id TEXT NOT NULL REFERENCES question_batches(id), position INTEGER NOT NULL,
 question_id TEXT NOT NULL UNIQUE REFERENCES questions(id),
 missing_json TEXT NOT NULL DEFAULT '[]', suggestion_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(batch_id,position)
);
CREATE TABLE IF NOT EXISTS question_records (
 question_id TEXT PRIMARY KEY REFERENCES questions(id),
 collection_id TEXT NOT NULL REFERENCES question_collections(id),
 registered_by TEXT NOT NULL REFERENCES users(id),
 provenance TEXT NOT NULL, content_sha256 TEXT NOT NULL,
 review_state TEXT NOT NULL DEFAULT 'draft' CHECK(review_state IN ('draft','reviewed','published')),
 category_id TEXT REFERENCES question_categories(id), version INTEGER NOT NULL DEFAULT 1,
 confirmed_at TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_records_collection_state ON question_records(collection_id,review_state);
CREATE INDEX IF NOT EXISTS idx_records_category ON question_records(category_id,review_state);
CREATE TABLE IF NOT EXISTS question_attachments (
 id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES questions(id),
 storage_key TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachment_storage_key ON question_attachments(storage_key);
CREATE TABLE IF NOT EXISTS question_batch_files (
 batch_id TEXT PRIMARY KEY REFERENCES question_batches(id),
 storage_key TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exam_item_snapshots (
 exam_id TEXT NOT NULL, question_id TEXT NOT NULL, snapshot_json TEXT NOT NULL,
 question_version INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(exam_id,question_id),
 FOREIGN KEY(exam_id,question_id) REFERENCES exam_items(exam_id,question_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS question_authorizations (
 school_id TEXT NOT NULL REFERENCES schools(id), question_id TEXT NOT NULL REFERENCES questions(id),
 recipient_id TEXT NOT NULL REFERENCES users(id), authorized_by TEXT NOT NULL REFERENCES users(id),
 question_version INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
 PRIMARY KEY(school_id,question_id,recipient_id)
);
CREATE TABLE IF NOT EXISTS personal_transfers (
 source_id TEXT NOT NULL REFERENCES users(id), target_id TEXT NOT NULL REFERENCES users(id),
 question_id TEXT NOT NULL REFERENCES questions(id), confirmed_by TEXT NOT NULL REFERENCES users(id),
 confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_id,target_id,question_id)
);
CREATE TABLE IF NOT EXISTS teacher_personal_preferences (
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 preferences_json TEXT NOT NULL DEFAULT '{}',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS account_link_challenges (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES users(id),
 target_id TEXT NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL,
 confirmed_at TEXT, preferences_transferred INTEGER NOT NULL DEFAULT 0,
 selection_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS account_events (
 id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
 subject_id TEXT REFERENCES users(id), school_id TEXT REFERENCES schools(id),
 event TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_account_events ON account_events(subject_id,school_id,created_at);
'''
