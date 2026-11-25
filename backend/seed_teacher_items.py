"""Itens autorais de demonstração, privados por professor e escola.

Os itens são CÓPIAS fictícias do banco inicial, não conteúdo criado por LLM.
A chave de origem é determinística; múltiplas execuções não duplicam dados.
"""
import json
import hashlib
from .db import rows, session

SOURCE='Cognix IA · exemplo fictício'

def seed_examples():
    links=rows('''SELECT DISTINCT a.teacher_id,u.name,c.school_id,a.subject
      FROM teaching_assignments a
      JOIN users u ON u.id=a.teacher_id
      JOIN classes c ON c.id=a.class_id
      WHERE u.role='prof' AND u.active=1
      ORDER BY a.teacher_id,c.school_id,a.subject''')
    with session() as con:
        count=0
        for a in links:
            examples=con.execute('''SELECT title,context,prompt,alternatives_json,media_json,
                    correct_letter,topic,difficulty
                  FROM questions WHERE creator_id IS NULL AND source='Cognix Demo' AND discipline=?
                   AND status='published' AND rights_status='demo' ORDER BY id LIMIT 2''',
                 (a['subject'],)).fetchall()
            for ix,example in enumerate(examples):
                key=f"{a['teacher_id']}:{a['school_id']}:{a['subject']}:{ix}"
                qid='own-demo-'+hashlib.sha256(key.encode()).hexdigest()[:22]
                text=(example['context'] or example['prompt']).strip()
                if not text:continue
                pre=f"[EXEMPLO FICTÍCIO DO ACERVO DOCENTE] Questão demonstrativa: {text}"
                cur=con.execute('''INSERT OR IGNORE INTO questions
                  (id,source,source_key,area,discipline,title,context,prompt,alternatives_json,
                   media_json,correct_letter,topic,difficulty,status,rights_status,source_url,creator_id,school_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    qid,SOURCE,key,a['subject'],a['subject'],
                    f"Exemplo pessoal — {example['topic']}",pre,example['prompt'],example['alternatives_json'],
                    example['media_json'],example['correct_letter'],example['topic'],example['difficulty'],
                    'review','demo','',a['teacher_id'],a['school_id']))
                count+=cur.rowcount
    return count

if __name__=='__main__':
    from .db import init_db
    init_db()
    print('Exemplos particulares criados:',seed_examples())
