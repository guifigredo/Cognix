"""Banco v10: ingestão recuperável, acervos explícitos e permissões por item."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import unicodedata
import zipfile
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import current_user, require
from .db import ROOT, one, rows, session
from .access import allowed_schools, assert_school
from .llm.provider import provider, LLMError

router = APIRouter(prefix='/api/bank', tags=['Banco de questões'])
STORE = Path(os.getenv('COGNIX_UPLOAD_STORE',str(ROOT/'data'/'question_uploads'))).resolve()
MAX_UPLOAD = 10 * 1024 * 1024
MAX_ITEMS = 300
QUESTION_START = re.compile(r'^\s*(?:quest[aã]o\s*)?(\d{1,4})\s*[).:\-]\s*(.*)$', re.I)
OPTION = re.compile(r'^\s*([A-E])\s*[).:\-]\s*(.+)$', re.I)
ANSWER = re.compile(r'^\s*(?:gabarito|resposta(?:\s+correta)?)\s*[:\-]\s*([A-E])\s*$', re.I)
SUBJECTS = {'Física':('movimento','velocidade','aceleração','força','energia','cinemática','newton'),
            'Química':('molécula','átomo','reação','elemento','solução','ligação'),
            'Biologia':('célula','genética','ecologia','organismo','evolução'),
            'Matemática':('equação','função','geometria','probabilidade','polinômio'),
            'História':('revolução','império','reinado','guerra'),
            'Geografia':('clima','relevo','região','território')}
TOPIC_WORDS = {'Cinemática':('movimento','velocidade','aceleração','cinemática'),
               'Dinâmica':('força','newton','atrito'),
               'Energia':('energia','potência','trabalho'),
               'Genética':('genética','herança','cromossomo')}


def collection_for(user, collection_id):
    record=one('SELECT * FROM question_collections WHERE id=?',(collection_id,))
    if not record: raise HTTPException(404,'Acervo não encontrado.')
    if record['kind']=='personal':
        if record['owner_id']!=user['id']:
            raise HTTPException(403,'Acervo particular de outro professor.')
    elif user['role']=='coord':
        assert_school(user,record['school_id'])
    elif user['role']=='prof':
        assert_school(user,record['school_id'])
    else: raise HTTPException(403,'Acervo reservado a educadores.')
    return record


def question_access(user, qid, *, write=False):
    record=one('''SELECT r.*,c.kind,c.owner_id,c.school_id
        FROM question_records r JOIN question_collections c ON c.id=r.collection_id
        WHERE r.question_id=?''',(qid,))
    if record:
        collection_for(user,record['collection_id'])
        if record['kind']=='school' and user['role']=='prof':
            # Acesso escolar é delimitado pelas disciplinas realmente atribuídas.
            from .access import subjects_for
            q=one('SELECT discipline FROM questions WHERE id=?',(qid,))
            if not q or q['discipline'] not in subjects_for(user,record['school_id']):
                raise HTTPException(403,'Questão fora da disciplina atribuída.')
        return record
    # Itens antigos são ambíguos: continuam visíveis somente pela política legada,
    # mas nunca tornam-se automaticamente particulares ou transferíveis.
    from .main import question_visibility
    condition,args=question_visibility(user)
    if not one('SELECT q.id FROM questions q WHERE q.id=? AND '+condition,[qid]+args):
        raise HTTPException(404,'Questão indisponível.')
    if write:raise HTTPException(409,'Item legado requer revisão de propriedade antes da edição.')
    return None


def _collection_create(db,*,kind,owner=None,school=None):
    key=f'personal-{owner}' if kind=='personal' else f'school-{school}'
    db.execute('''INSERT OR IGNORE INTO question_collections(id,kind,owner_id,school_id,name)
                  VALUES(?,?,?,?,?)''',(key,kind,owner,school,'Meu acervo' if kind=='personal' else 'Acervo da escola'))
    return key


@router.get('/collections')
def collections(user=Depends(require('coord','prof'))):
    with session() as db:
        if user['role']=='prof':_collection_create(db,kind='personal',owner=user['id'])
        for school in allowed_schools(user):_collection_create(db,kind='school',school=school)
    results=rows('SELECT * FROM question_collections WHERE kind=? AND owner_id=?',('personal',user['id'])) if user['role']=='prof' else []
    schools=allowed_schools(user)
    if schools:
        results+=rows('SELECT * FROM question_collections WHERE kind=? AND school_id IN ('+
                      ','.join('?' for _ in schools)+') ORDER BY school_id',['school']+schools)
    return {'collections':results,'enem':True}


@router.get('/general')
def general_questions(q:str='',discipline:str='',topic:str='',source:str='',status:str='',
                      page:int=Query(1,ge=1),limit:int=Query(18,ge=1,le=60),
                      user=Depends(require('prof'))):
    """Visão agregada: acervos autorizados + catálogo central público.

    Catálogo central de autoria institucional é consultável em qualquer matéria,
    mas só pode compor provas se houver atribuição real da disciplina. Nenhuma
    coleção privada de terceiros ou escola sem vínculo pode entrar nesta lista.
    """
    from .main import question_visibility
    from .access import subjects_for
    restricted,args=question_visibility(user)
    public='''(q.school_id IS NULL AND q.creator_id IS NULL
               AND q.status='published' AND q.rights_status IN ('authorized','demo')
               AND NOT EXISTS(SELECT 1 FROM question_records r WHERE r.question_id=q.id))'''
    clauses=['('+restricted+' OR '+public+')']
    if q:
        clauses.append('(q.title LIKE ? OR q.prompt LIKE ? OR q.context LIKE ?)')
        args += ['%'+q[:80]+'%']*3
    if discipline:clauses.append('q.discipline=?');args.append(discipline[:80])
    if topic:clauses.append('q.topic LIKE ?');args.append('%'+topic[:100]+'%')
    if source:clauses.append('q.source=?');args.append(source[:100])
    if status:clauses.append('q.status=?');args.append(status[:30])
    where=' WHERE '+' AND '.join(clauses)
    count=one('SELECT COUNT(*) n FROM questions q'+where,args)['n']
    items=rows('''SELECT q.id,q.source,q.title,q.context,q.prompt,q.alternatives_json,
        q.media_json,q.correct_letter,q.discipline,q.area,q.topic,q.status,q.rights_status,
        q.difficulty,q.year,q.school_id,q.creator_id,
        (SELECT c.kind FROM question_records r JOIN question_collections c ON c.id=r.collection_id
           WHERE r.question_id=q.id) collection_kind
        FROM questions q'''+where+' ORDER BY q.imported_at DESC,q.id LIMIT ? OFFSET ?',
        args+[limit,(page-1)*limit])
    assigned=set(subjects_for(user))
    for item in items:
        item['alternatives']=json.loads(item.pop('alternatives_json'))
        item['media']=json.loads(item.pop('media_json'))
        item['exam_eligible']=item['discipline'] in assigned and item['status']=='published' and \
            item['rights_status'] in ('authorized','demo') and bool(item['correct_letter'])
        item['scope_label']=('Meu acervo' if item['collection_kind']=='personal' else
          'Acervo escolar' if item['school_id'] or item['collection_kind']=='school' else
          'Catálogo central')
    return {'total':count,'items':items,'page':page,'limit':limit,
            'scope':'acervos autorizados e catálogo central; sem acervos privados de terceiros'}


def _parse_text(text):
    text=text.replace('\r\n','\n').replace('\r','\n').strip()
    if not text: raise HTTPException(422,'Nenhum texto extraível foi encontrado. PDFs digitalizados exigem OCR externo.')
    chunks=[]; current=[]
    for line in text.splitlines():
        candidate=QUESTION_START.match(line)
        if candidate and current:
            chunks.append(current);current=[]
        current.append(line)
    if current:chunks.append(current)
    if len(chunks)>MAX_ITEMS:raise HTTPException(413,'O lote excede 300 questões.')
    results=[]
    for lines in chunks:
        prompt=[]; options={};answer=''
        for i,line in enumerate(lines):
            cleaned=QUESTION_START.sub(r'\2',line,count=1).strip() if i==0 else line.strip()
            m=ANSWER.match(cleaned)
            if m:answer=m.group(1).upper();continue
            m=OPTION.match(cleaned)
            if m:options[m.group(1).upper()]=m.group(2).strip();continue
            prompt.append(cleaned)
        text_prompt='\n'.join(prompt).strip()
        if not text_prompt and not options:continue
        missing=[]
        if len(text_prompt)<10:missing.append('enunciado')
        if len(options)<2:missing.append('alternativas')
        if not answer:missing.append('gabarito')
        if answer and answer not in options:missing.append('gabarito não corresponde às alternativas')
        results.append({'prompt':text_prompt,'alternatives':[{'letter':k,'text':v} for k,v in sorted(options.items())],
                        'correct_letter':answer,'missing':missing})
    return results


def _extract(contents, kind):
    media_by_position={}
    if kind=='text':
        try:text=contents.decode('utf-8-sig')
        except UnicodeDecodeError:raise HTTPException(422,'Texto deve usar UTF-8.')
    elif kind=='docx':
        if not contents.startswith(b'PK') or not zipfile.is_zipfile(io.BytesIO(contents)):
            raise HTTPException(422,'Arquivo DOCX inválido.')
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            if len(archive.infolist())>1500 or sum(f.file_size for f in archive.infolist())>30*1024*1024:
                raise HTTPException(413,'DOCX excede o limite de conteúdo descompactado.')
        from docx import Document
        try:
            doc=Document(io.BytesIO(contents))
            text='\n'.join(p.text for p in doc.paragraphs)
            pos=0
            for para in doc.paragraphs:
                for line in para.text.splitlines():
                    if QUESTION_START.match(line):pos+=1
                for image in para._p.xpath('.//a:blip'):
                    relation=image.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    part=doc.part.related_parts.get(relation)
                    if part and part.content_type in ('image/png','image/jpeg','image/gif','image/webp'):
                        media_by_position.setdefault(max(1,pos),[]).append((part.blob,part.content_type,part.partname.split('/')[-1]))
        except HTTPException:raise
        except Exception:raise HTTPException(422,'Não foi possível abrir o DOCX.')
    elif kind=='pdf':
        if not contents.startswith(b'%PDF'):raise HTTPException(422,'PDF inválido.')
        try:
            from pypdf import PdfReader
            doc=PdfReader(io.BytesIO(contents),strict=False)
            if len(doc.pages)>150:raise HTTPException(413,'PDF com mais de 150 páginas.')
            pages=[];pos=0
            for page in doc.pages:
                content=page.extract_text() or ''
                pages.append(content)
                starts=sum(1 for line in content.splitlines() if QUESTION_START.match(line))
                if starts:
                    for asset in page.images:
                        if asset.data.startswith(b'\x89PNG'):
                            media_by_position.setdefault(pos+1,[]).append((asset.data,'image/png',asset.name))
                        elif asset.data.startswith(b'\xff\xd8'):
                            media_by_position.setdefault(pos+1,[]).append((asset.data,'image/jpeg',asset.name))
                pos+=starts
            text='\n'.join(pages)
        except HTTPException:raise
        except Exception:raise HTTPException(422,'Falha ao extrair a camada de texto do PDF.')
    else:raise HTTPException(422,'Formato não permitido.')
    return _parse_text(text),media_by_position


def _suggest(prompt,categories):
    norm=prompt.casefold()
    discipline=next((name for name,terms in SUBJECTS.items() if any(t in norm for t in terms)),'')
    topic=next((name for name,terms in TOPIC_WORDS.items() if any(t in norm for t in terms)),'')
    match=next((c for c in categories if c['discipline']==discipline and c['topic'].casefold()==topic.casefold()),None)
    return {'discipline':discipline,'topic':match['topic'] if match else topic,
            'category_id':match['id'] if match else None,
            'origin':'regras','confidence':'heurística; requer confirmação'}


def normalize_topic(topic):
    folded=unicodedata.normalize('NFKD',topic.strip().casefold())
    folded=''.join(ch for ch in folded if not unicodedata.combining(ch))
    return ' '.join(re.sub(r'[^\w\s]',' ',folded).split())


def _import_bytes(db,user,collection,data,kind,filename):
    if not data or len(data)>MAX_UPLOAD:raise HTTPException(413,'Arquivo vazio ou maior que 10 MB.')
    parsed,media_by_position=_extract(data,kind)
    digest=hashlib.sha256(data).hexdigest()
    current=db.execute('''SELECT id FROM question_batches WHERE collection_id=? AND uploader_id=? AND content_sha256=?''',
                       (collection['id'],user['id'],digest)).fetchone()
    if current:return {'batch_id':current['id'],'resumed':True,'total':db.execute('SELECT COUNT(*) FROM question_import_items WHERE batch_id=?',(current['id'],)).fetchone()[0]}
    batch=secrets.token_hex(12)
    db.execute('INSERT INTO question_batches(id,collection_id,uploader_id,origin_format,filename,content_sha256) VALUES(?,?,?,?,?,?)',
               (batch,collection['id'],user['id'],kind,filename,digest))
    categories=[dict(r) for r in db.execute('SELECT * FROM question_categories WHERE collection_id=?',(collection['id'],))]
    for pos,item in enumerate(parsed,1):
        qid=secrets.token_hex(12)
        suggest=_suggest(item['prompt'],categories)
        school=collection['school_id']
        db.execute('''INSERT INTO questions(id,source,source_key,area,prompt,alternatives_json,correct_letter,
             discipline,topic,status,rights_status,creator_id,school_id)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
           (qid,'Importação docente',f'{batch}:{pos}','',item['prompt'],json.dumps(item['alternatives'],ensure_ascii=False),
            item['correct_letter'],suggest['discipline'],suggest['topic'],'review','pending',user['id'],school))
        db.execute('''INSERT INTO question_records(question_id,collection_id,registered_by,provenance,content_sha256)
                      VALUES(?,?,?,?,?)''',(qid,collection['id'],user['id'],f'{kind}:{filename}:{pos}',hashlib.sha256(item['prompt'].encode()).hexdigest()))
        db.execute('''INSERT INTO question_import_items(batch_id,position,question_id,missing_json,suggestion_json)
                      VALUES(?,?,?,?,?)''',(batch,pos,qid,json.dumps(item['missing'],ensure_ascii=False),json.dumps(suggest,ensure_ascii=False)))
        image_urls=[]
        for data_blob,mime,original in media_by_position.get(pos,[]):
            if len(data_blob)>5*1024*1024:continue
            sha=hashlib.sha256(data_blob).hexdigest()
            ext='png' if mime=='image/png' else 'jpg' if mime=='image/jpeg' else 'gif' if mime=='image/gif' else 'webp'
            storage_key=f'{sha}.{ext}';attachment_id=secrets.token_hex(12)
            STORE.mkdir(parents=True,exist_ok=True)
            destination=STORE/storage_key
            if not destination.exists():
                with destination.open('xb') as fp:fp.write(data_blob)
            db.execute('''INSERT INTO question_attachments(id,question_id,storage_key,filename,media_type,size_bytes,sha256)
                  VALUES(?,?,?,?,?,?,?)''',(attachment_id,qid,storage_key,original,mime,len(data_blob),sha))
            image_urls.append('/api/bank/attachments/'+attachment_id)
        if image_urls:
            db.execute('UPDATE questions SET media_json=? WHERE id=?',(json.dumps(image_urls),qid))
            current_missing=json.loads(db.execute('SELECT missing_json FROM question_import_items WHERE question_id=?',(qid,)).fetchone()[0])
            current_missing.append('verificar associação da mídia à questão')
            db.execute('UPDATE question_import_items SET missing_json=? WHERE question_id=?',
                       (json.dumps(current_missing,ensure_ascii=False),qid))
    return {'batch_id':batch,'resumed':False,'total':len(parsed)}


class TextImport(BaseModel):
    collection_id:str
    text:str=Field(min_length=1,max_length=500000)


@router.post('/import/text')
def import_text(body:TextImport,user=Depends(require('prof','coord'))):
    collection=collection_for(user,body.collection_id)
    with session() as db:
        db.execute('BEGIN IMMEDIATE')
        return _import_bytes(db,user,collection,body.text.encode(),'text','texto colado')


@router.post('/import/file')
async def import_file(request:Request,collection_id:str,filename:str=Query(max_length=180),user=Depends(require('prof','coord'))):
    collection=collection_for(user,collection_id)
    kind=Path(filename).suffix.lower().lstrip('.')
    if kind not in ('docx','pdf'):raise HTTPException(422,'Envie apenas DOCX ou PDF com texto.')
    cl=request.headers.get('content-length')
    if cl and int(cl)>MAX_UPLOAD:raise HTTPException(413,'Máximo de 10 MB.')
    data=await request.body()
    if len(data)>MAX_UPLOAD:raise HTTPException(413,'Máximo de 10 MB.')
    with session() as db:
        db.execute('BEGIN IMMEDIATE')
        result=_import_bytes(db,user,collection,data,kind,Path(filename).name)
        # O documento de origem contém potencialmente todas as questões do lote.
        # Nunca pode acompanhar a transferência isolada de uma questão.
        if result['total']:
            storage_key=f'{hashlib.sha256(data).hexdigest()}.{kind}'
            STORE.mkdir(parents=True,exist_ok=True)
            path=STORE/storage_key
            if not path.exists():
                with path.open('xb') as fp:fp.write(data)
            db.execute('''INSERT OR IGNORE INTO question_batch_files(batch_id,storage_key,filename,media_type,size_bytes,sha256)
                      VALUES(?,?,?,?,?,?)''',(result['batch_id'],storage_key,Path(filename).name,
                      'application/pdf' if kind=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                      len(data),hashlib.sha256(data).hexdigest()))
    return result


@router.get('/batches/{batch_id}')
def batch_detail(batch_id:str,user=Depends(require('coord','prof'))):
    batch=one('SELECT * FROM question_batches WHERE id=?',(batch_id,))
    if not batch:raise HTTPException(404,'Lote não encontrado.')
    collection_for(user,batch['collection_id'])
    items=rows('''SELECT i.position,i.missing_json,i.suggestion_json,q.id,q.prompt,q.alternatives_json,
        q.correct_letter,q.discipline,q.topic,r.review_state,r.category_id
        FROM question_import_items i JOIN questions q ON q.id=i.question_id
        JOIN question_records r ON r.question_id=q.id WHERE i.batch_id=? AND r.collection_id=?
        ORDER BY i.position''',(batch_id,batch['collection_id']))
    for item in items:
        for key in ('missing_json','suggestion_json','alternatives_json'):
            item[key.removesuffix('_json')]=json.loads(item.pop(key))
    return {'batch':batch,'items':items}


@router.get('/batches/{batch_id}/original')
def download_original(batch_id:str,user=Depends(require('coord','prof'))):
    batch=one('SELECT * FROM question_batches WHERE id=?',(batch_id,))
    if not batch:raise HTTPException(404,'Lote indisponível.')
    collection=collection_for(user,batch['collection_id'])
    if collection['kind']=='personal' and batch['uploader_id']!=user['id']:
        raise HTTPException(403,'Lote particular de outra conta.')
    row=one('SELECT * FROM question_batch_files WHERE batch_id=?',(batch_id,))
    if not row:raise HTTPException(404,'Não existe arquivo original para este lote.')
    path=(STORE/row['storage_key']).resolve()
    if path.parent!=STORE or not path.is_file():raise HTTPException(404,'Arquivo original ausente.')
    return FileResponse(path,media_type=row['media_type'],filename=row['filename'])


@router.get('/batches')
def list_batches(collection_id:str,user=Depends(require('coord','prof'))):
    collection_for(user,collection_id)
    return rows('SELECT * FROM question_batches WHERE collection_id=? ORDER BY created_at DESC',(collection_id,))


@router.get('/categories')
def categories(collection_id:str,user=Depends(require('coord','prof'))):
    collection_for(user,collection_id)
    return rows('SELECT * FROM question_categories WHERE collection_id=? ORDER BY discipline,topic',(collection_id,))


class ReviewItem(BaseModel):
    question_id:str
    discipline:str=Field(min_length=2,max_length=80)
    topic:str=Field(min_length=2,max_length=160)
    prompt:str|None=Field(default=None,max_length=10000)
    alternatives:list[dict]|None=None
    correct_letter:str|None=None
    rights_confirmed:bool=False


class ReviewBatch(BaseModel):
    batch_id:str
    items:list[ReviewItem]=Field(min_length=1,max_length=300)


@router.post('/review')
def review_batch(body:ReviewBatch,user=Depends(require('prof','coord'))):
    batch=one('SELECT * FROM question_batches WHERE id=?',(body.batch_id,))
    if not batch:raise HTTPException(404,'Lote não encontrado.')
    collection=collection_for(user,batch['collection_id'])
    if batch['uploader_id']!=user['id'] and not (user['role']=='coord' and collection['kind']=='school'):
        raise HTTPException(403,'A revisão pertence ao autor ou à coordenação escolar.')
    with session() as db:
        for item in body.items:
            if collection['kind']=='school' and user['role']=='prof':
                from .access import subjects_for
                if item.discipline.strip() not in subjects_for(user,collection['school_id']):
                    raise HTTPException(403,'A disciplina está fora das atribuições deste professor.')
            row=db.execute('''SELECT q.id,q.prompt,q.correct_letter,q.alternatives_json FROM questions q
                JOIN question_import_items i ON i.question_id=q.id WHERE i.batch_id=? AND q.id=?''',(body.batch_id,item.question_id)).fetchone()
            if not row:raise HTTPException(403,'Item não pertence ao lote.')
            normalized=normalize_topic(item.topic)
            cat=db.execute('''SELECT id FROM question_categories WHERE collection_id=? AND discipline=? AND normalized=?''',
                           (collection['id'],item.discipline.strip(),normalized)).fetchone()
            cid=cat['id'] if cat else secrets.token_hex(12)
            if not cat:db.execute('''INSERT INTO question_categories(id,collection_id,discipline,topic,normalized,confirmed_by)
                                 VALUES(?,?,?,?,?,?)''',(cid,collection['id'],item.discipline.strip(),item.topic.strip(),normalized,user['id']))
            prompt=item.prompt.strip() if item.prompt is not None else row['prompt']
            alternatives=item.alternatives if item.alternatives is not None else json.loads(row['alternatives_json'])
            if len(alternatives)>5 or any(not isinstance(a,dict) or a.get('letter') not in ('A','B','C','D','E') or
               not isinstance(a.get('text'),str) or len(a['text'])>3000 for a in alternatives):
                raise HTTPException(422,'Alternativas devem usar letras A–E e texto válido.')
            letters=[a['letter'] for a in alternatives]
            if len(set(letters))!=len(letters):raise HTTPException(422,'Alternativas repetidas.')
            correct=item.correct_letter.strip().upper() if item.correct_letter is not None else row['correct_letter']
            if correct and correct not in letters:raise HTTPException(422,'Gabarito não corresponde às alternativas.')
            ready=bool(correct and len(alternatives)>=2 and len(prompt)>=10)
            publish=bool(ready and item.rights_confirmed)
            db.execute('''UPDATE questions SET discipline=?,topic=?,prompt=?,alternatives_json=?,correct_letter=?,
                         status=?,rights_status=? WHERE id=?''',
                      (item.discipline.strip(),item.topic.strip(),prompt,
                       json.dumps(alternatives,ensure_ascii=False),correct,
                       'published' if publish else 'review','authorized' if item.rights_confirmed else 'pending',item.question_id))
            missing=[]
            if len(prompt)<10:missing.append('enunciado')
            if len(alternatives)<2:missing.append('alternativas')
            if not correct:missing.append('gabarito')
            db.execute('UPDATE question_import_items SET missing_json=? WHERE question_id=?',
                       (json.dumps(missing,ensure_ascii=False),item.question_id))
            db.execute('''UPDATE question_records SET category_id=?,review_state=?,confirmed_at=CURRENT_TIMESTAMP,
                         version=version+1,updated_at=CURRENT_TIMESTAMP WHERE question_id=?''',
                       (cid,'published' if publish else 'reviewed',item.question_id))
        db.execute('''UPDATE question_batches SET status=CASE WHEN
             (SELECT COUNT(*) FROM question_import_items i JOIN question_records r ON r.question_id=i.question_id
              WHERE i.batch_id=? AND r.review_state='draft')=0 THEN 'reviewed' ELSE 'imported' END WHERE id=?''',
             (body.batch_id,body.batch_id))
    return {'ok':True,'count':len(body.items)}


@router.post('/batches/{batch_id}/categorize')
def categorize_again(batch_id:str,user=Depends(require('prof','coord'))):
    batch=one('SELECT * FROM question_batches WHERE id=?',(batch_id,))
    if not batch:raise HTTPException(404,'Lote não encontrado.')
    collection=collection_for(user,batch['collection_id'])
    if batch['uploader_id']!=user['id'] and not (user['role']=='coord' and collection['kind']=='school'):
        raise HTTPException(403,'Lote de outro professor.')
    cats=rows('SELECT * FROM question_categories WHERE collection_id=?',(collection['id'],))
    candidates=rows('''SELECT q.id,q.prompt FROM question_import_items i
       JOIN question_records r ON r.question_id=i.question_id
       JOIN questions q ON q.id=i.question_id WHERE i.batch_id=? AND r.confirmed_at IS NULL''',(batch_id,))
    suggestions={x['id']:_suggest(x['prompt'],cats) for x in candidates}
    origin='regras'
    if provider.enabled and candidates:
        try:
            answer=provider.call(json.dumps({'task':'Classifique as questões no esquema {items:[{id,discipline,topic}]}.'
                ' Priorize categorias existentes. Não resolva, nem altere gabaritos.',
                'categories':[{'discipline':c['discipline'],'topic':c['topic']} for c in cats],
                'questions':candidates[:80]},ensure_ascii=False))
            for item in answer.get('items',[]):
                if item.get('id') in suggestions and isinstance(item.get('discipline'),str) and isinstance(item.get('topic'),str):
                    suggestions[item['id']]={'discipline':item['discipline'][:80],'topic':item['topic'][:160],
                                             'origin':'ia','confidence':'sugestão não confirmada'}
            origin='ia'
        except (LLMError,ValueError,TypeError):origin='regras (IA indisponível)'
    with session() as db:
        for qid,suggestion in suggestions.items():
            db.execute('''UPDATE question_import_items SET suggestion_json=? WHERE question_id=? AND EXISTS
                (SELECT 1 FROM question_records r WHERE r.question_id=? AND r.confirmed_at IS NULL)''',
                (json.dumps(suggestion,ensure_ascii=False),qid,qid))
    return {'ok':True,'suggested':len(suggestions),'origin':origin}


@router.get('/search')
def search(collection_id:str='',q:str='',discipline:str='',topic:str='',batch_id:str='',
           page:int=Query(1,ge=1),limit:int=Query(30,ge=1,le=100),user=Depends(require('coord','prof'))):
    if collection_id:collection_for(user,collection_id)
    available=collections(user)['collections']
    authorized=[c for c in available if not collection_id or c['id']==collection_id]
    from .access import subjects_for
    scopes=[];args=[]
    for coll in authorized:
        if coll['kind']=='personal' or user['role']=='coord':
            scopes.append('r.collection_id=?');args.append(coll['id'])
        else:
            permitted=subjects_for(user,coll['school_id'])
            if permitted:
                scopes.append('(r.collection_id=? AND q.discipline IN ('+','.join('?' for _ in permitted)+'))')
                args.extend([coll['id']]+permitted)
    if not scopes:return {'total':0,'items':[]}
    condition=['('+' OR '.join(scopes)+')']
    if q:condition.append('(q.prompt LIKE ? OR q.title LIKE ?)');args += ['%'+q[:80]+'%']*2
    if discipline:condition.append('q.discipline=?');args.append(discipline)
    if topic:condition.append('q.topic LIKE ?');args.append('%'+topic[:120]+'%')
    if batch_id:condition.append('i.batch_id=?');args.append(batch_id)
    sql=''' FROM question_records r JOIN questions q ON q.id=r.question_id
            LEFT JOIN question_import_items i ON i.question_id=q.id WHERE '''+' AND '.join(condition)
    count=one('SELECT COUNT(*) n'+sql,args)['n']
    items=rows('''SELECT q.id,q.prompt,q.discipline,q.topic,q.correct_letter,q.alternatives_json,
           q.status,r.review_state,r.collection_id,r.version,i.batch_id,i.position'''+sql+
          ' ORDER BY q.imported_at DESC,q.id LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])
    for item in items:item['alternatives']=json.loads(item.pop('alternatives_json'))
    return {'total':count,'items':items,'page':page}


@router.get('/attachments/{attachment_id}')
def download_attachment(attachment_id:str,user=Depends(require('coord','prof'))):
    row=one('SELECT * FROM question_attachments WHERE id=?',(attachment_id,))
    if not row:raise HTTPException(404,'Anexo não encontrado.')
    question_access(user,row['question_id'])
    path=(STORE/row['storage_key']).resolve()
    if path.parent!=STORE or not path.is_file():raise HTTPException(404,'Anexo indisponível.')
    return FileResponse(path,media_type=row['media_type'],filename=row['filename'])


@router.get('/attachments')
def attachments(question_id:str,user=Depends(require('coord','prof'))):
    question_access(user,question_id)
    return rows('SELECT id,question_id,filename,media_type,size_bytes,sha256 FROM question_attachments WHERE question_id=?',(question_id,))
