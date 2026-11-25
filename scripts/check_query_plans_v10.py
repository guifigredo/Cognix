"""EXPLAIN QUERY PLAN com massa sintética isolada; nunca altera o banco real."""
import json
import argparse
import sqlite3
import statistics
import time

from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.db import DB_FILE


def main(count=5000,source_path=DB_FILE):
    source_path=Path(source_path)
    if not source_path.is_file():
        raise SystemExit('Banco de origem inexistente. Informe --db com um banco já inicializado na v10.')
    source=sqlite3.connect(f'file:{source_path.resolve()}?mode=ro',uri=True)
    test=sqlite3.connect(':memory:')
    source.backup(test);source.close()
    test.execute('PRAGMA foreign_keys=ON')
    if not test.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='question_records'").fetchone():
        raise SystemExit('Banco ainda não migrado para v10. Inicialize uma cópia de QA com o Cognix antes do benchmark.')
    collection='benchmark-collection'
    owner=test.execute("SELECT id FROM users WHERE role='prof' LIMIT 1").fetchone()
    if not owner:raise RuntimeError('Banco de testes deve conter ao menos um professor.')
    owner=owner[0]
    test.execute('''INSERT INTO question_collections(id,kind,owner_id,name)
                    VALUES(?,'personal',?,'Benchmark temporário')''',(collection,owner))
    collections=[collection]
    for group in range(1,10):
        uid='benchmark-user-'+str(group)
        test.execute('''INSERT INTO users(id,name,email,password_hash,role,account_plan)
           VALUES(?,?,?,'unused','prof','individual')''',
           (uid,uid,uid+'@invalid.example'))
        cid='benchmark-collection-'+str(group)
        test.execute("INSERT INTO question_collections(id,kind,owner_id,name) VALUES(?,'personal',?,'Benchmark')",(cid,uid))
        collections.append(cid)
    for i in range(count):
        qid='benchmark-'+str(i)
        subject='Física' if i%2 else 'Matemática'
        topic='Cinemática' if i%5 else 'Dinâmica'
        test.execute('''INSERT INTO questions(id,source,source_key,discipline,topic,prompt,status,rights_status)
                        VALUES(?,'Benchmark v10',?,?,?,?, 'review','pending')''',
                     (qid,qid,subject,topic,f'Questão sintética {i} para medir consulta'))
        selected_collection=collections[i%len(collections)]
        selected_owner=owner if i%len(collections)==0 else 'benchmark-user-'+str(i%len(collections))
        test.execute('''INSERT INTO question_records(question_id,collection_id,registered_by,provenance,content_sha256)
                        VALUES(?,?,?,'benchmark','')''',(qid,selected_collection,selected_owner))
    test.commit();test.execute('ANALYZE')
    cases={
      'listar_acervo':('''SELECT question_id FROM question_records WHERE collection_id=? AND review_state=? LIMIT 40''',(collection,'draft')),
      'buscar_disciplina_topico':('''SELECT q.id FROM questions q JOIN question_records r ON r.question_id=q.id
              WHERE r.collection_id=? AND q.discipline=? AND q.topic=? LIMIT 30''',(collection,'Física','Cinemática')),
      'localizar_lote':('''SELECT position,question_id FROM question_import_items WHERE batch_id=? ORDER BY position''',('lote-ficticio',))
    }
    results={}
    for label,(sql,args) in cases.items():
        plan=[r[3] for r in test.execute('EXPLAIN QUERY PLAN '+sql,args).fetchall()]
        times=[]
        for _ in range(40):
            start=time.perf_counter();test.execute(sql,args).fetchall();times.append((time.perf_counter()-start)*1000)
        results[label]={'plan':plan,'median_ms':round(statistics.median(times),3)}
    print(json.dumps({'synthetic_questions':count,'source_database_unmodified':True,'cases':results},indent=2,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Planos de execução com massa sintética, sem alterar a origem.')
    parser.add_argument('--db',type=Path,default=DB_FILE,help='Banco SQLite v10 inicializado')
    parser.add_argument('--count',type=int,default=5000,help='Quantidade sintética de questões')
    options=parser.parse_args()
    if not 10<=options.count<=500000:parser.error('--count deve estar entre 10 e 500000')
    main(options.count,options.db)
