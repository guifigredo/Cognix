"""Importador idempotente da API ENEM: não trata exemplos como questões oficiais."""
import argparse, json, os, re, time, uuid
import httpx
from .db import session, init_db

DEFAULT_BASE='https://api.enem.dev/v1'
AREA = {'matematica':'Matemática', 'ciencias-natureza':'Ciências da Natureza',
        'ciencias-humanas':'Ciências Humanas','linguagens':'Linguagens'}

def normalize(item):
    """Transforma uma questão da API sem inventar subdivisões das áreas do ENEM."""
    year = int(item['year'])
    raw_index = str(item['index']).strip()
    match = re.match(r'^(\d+)(?:[-_](.+))?$',raw_index)
    if not match: raise ValueError('Índice de questão ENEM inválido')
    index = int(match.group(1))
    language_input=item.get('language') or match.group(2) or 'geral'
    if isinstance(language_input,dict):
        language_input=language_input.get('value') or language_input.get('label') or 'geral'
    language=str(language_input).strip().lower()
    language={'english':'ingles','spanish':'espanhol','en':'ingles','es':'espanhol'}.get(language,language)
    disc=item.get('discipline') or ''
    if isinstance(disc,dict): disc=disc.get('value') or disc.get('label') or ''
    raw=str(disc).strip().lower()
    aliases={
        'matematica':'Matemática','matemática':'Matemática','mathematics':'Matemática',
        'ciencias-natureza':'Ciências da Natureza','ciências da natureza':'Ciências da Natureza',
        'natural-sciences':'Ciências da Natureza',
        'ciencias-humanas':'Ciências Humanas','ciências humanas':'Ciências Humanas',
        'human-sciences':'Ciências Humanas',
        'linguagens':'Linguagens','languages':'Linguagens',
    }
    area = aliases.get(raw, str(disc))
    # Respostas resumidas da API podem omitir a área. O caderno ENEM convencional
    # (2009–2023) utiliza quatro blocos de 45 itens; confirmaremos metadados
    # na curadoria antes de liberar qualquer item em provas.
    if not area and 2009<=year<=2023:
        area = ('Linguagens' if 1<=index<=45 else
                'Ciências Humanas' if 46<=index<=90 else
                'Ciências da Natureza' if 91<=index<=135 else
                'Matemática' if 136<=index<=180 else '')
    alternatives = [{'letter':str(a.get('letter','')).upper()[:2],
                     'text':str(a.get('text') or ''),
                     'file':a.get('file') or a.get('filePath') or ''}
                    for a in (item.get('alternatives') or [])]
    correct = str(item.get('correctAlternative') or '').upper()
    if not correct and any(a.get('isCorrect') for a in item.get('alternatives',[])):
        correct=next(str(a.get('letter') or '').upper() for a in item['alternatives'] if a.get('isCorrect'))
    # Matemática é disciplina única. As outras áreas podem conter várias disciplinas;
    # somente a classificação local e revisada libera essa consulta ao professor.
    return {'id': 'enem-'+str(year)+'-'+str(index)+'-'+language,
       'source':'ENEM API','source_key':f'{year}:{index}:{language}', 'year':year,
       'question_number':index,'area':area,
       'discipline':'Matemática' if area=='Matemática' else '',
       'language':language if language!='geral' else '',
       'title':str(item.get('title') or f'Questão {index} · ENEM {year}'),
       'context':str(item.get('context') or ''),'prompt':str(item.get('alternativesIntroduction') or ''),
       'alternatives_json':json.dumps(alternatives,ensure_ascii=False),
       'media_json':json.dumps(item.get('files') or [],ensure_ascii=False),
       'correct_letter':correct,'topic':'','difficulty':'', 'status':'review',
       'rights_status':'pending',
       'source_url':f'https://api.enem.dev/v1/exams/{year}/questions/{raw_index}'}

def store_questions(payload, year=None):
    if not isinstance(payload,list):
        raise ValueError('A resposta não contém uma lista de questões')
    n=0
    sql='''INSERT INTO questions (id,source,source_key,year,question_number,area,discipline,language,title,context,prompt,
     alternatives_json,media_json,correct_letter,topic,difficulty,status,rights_status,source_url)
     VALUES (:id,:source,:source_key,:year,:question_number,:area,:discipline,:language,:title,:context,:prompt,
     :alternatives_json,:media_json,:correct_letter,:topic,:difficulty,:status,:rights_status,:source_url)
     ON CONFLICT(source,source_key) DO UPDATE SET
       title=excluded.title,context=excluded.context,prompt=excluded.prompt,
       alternatives_json=excluded.alternatives_json,media_json=excluded.media_json,
       correct_letter=excluded.correct_letter,source_url=excluded.source_url,
       imported_at=CURRENT_TIMESTAMP'''
    with session() as db:
        for item in payload:
            try:
                source=dict(item)
                if year is not None: source.setdefault('year',int(year))
                row=normalize(source)
            except (KeyError,ValueError,TypeError,AttributeError): continue
            db.execute(sql,row); n+=1
    return n

def fetch_retry(client, endpoint, params=None):
    for attempt in range(5):
        try:
            res=client.get(endpoint,params=params)
            if res.status_code==429 or res.status_code>=500:
                wait=min(30,2**attempt)
                if res.status_code==429:
                    try: wait=min(40,max(1,float(res.headers.get('Retry-After',str(wait)))))
                    except ValueError: pass
                time.sleep(wait); continue
            res.raise_for_status()
            return res.json()
        except (httpx.RequestError,ValueError):
            if attempt==4: raise
            time.sleep(min(10,2**attempt))
    raise RuntimeError('O serviço ENEM não respondeu após várias tentativas')

def sync_year(year, base_url=DEFAULT_BASE, progress=None, client=None):
    if not 2009<=int(year)<=2100: raise ValueError('Ano inválido')
    base=base_url.rstrip('/')
    own=client is None
    client=client or httpx.Client(timeout=35.0,follow_redirects=False)
    seen=set(); total=0; offset=0; page_size=50
    try:
        while True:
            data=fetch_retry(client, f'{base}/exams/{year}/questions',{'limit':page_size,'offset':offset})
            if not isinstance(data,dict) or not isinstance(data.get('questions'),list):
                raise ValueError(f'Resposta inesperada da API para {year}')
            arr=data['questions']; meta=data.get('metadata') or {}
            # Evita loop infinito quando a API repete uma página.
            page_ids=tuple((x.get('year'),x.get('index'),x.get('language')) for x in arr)
            if page_ids in seen: raise ValueError('A API repetiu uma página; sincronização interrompida.')
            seen.add(page_ids)
            if not arr: break
            count=store_questions(arr,year=year);total+=count;offset+=len(arr)
            if progress: progress(count)
            has_more=meta.get('hasMore',data.get('hasMore'))
            total_hint=meta.get('total',data.get('total'))
            if has_more is False: break
            if total_hint is not None and offset>=int(total_hint): break
            if len(arr)<page_size: break
            time.sleep(1.1)
        return total
    finally:
        if own: client.close()

def sync_all(years=None,base_url=DEFAULT_BASE,progress=None,client=None):
    years=years or list(range(2009,2024))
    result={}
    for index,year in enumerate(years):
        if index: time.sleep(1.1)
        result[year]=sync_year(year,base_url,progress,client)
    return result

def run_job(job_id,year):
    with session() as db: db.execute("UPDATE import_jobs SET state='running' WHERE id=?",(job_id,))
    def tick(n):
        with session() as db: db.execute('UPDATE import_jobs SET imported=imported+?,processed=processed+? WHERE id=?',(n,n,job_id))
    try:
        result=sync_all([int(year)] if year!='todos' else None, os.getenv('ENEM_API_BASE',DEFAULT_BASE),tick)
        with session() as db: db.execute("UPDATE import_jobs SET state='done',message=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(json.dumps(result),job_id))
    except Exception as e:
        with session() as db: db.execute("UPDATE import_jobs SET state='error',message=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(str(e)[:500],job_id))

def main():
    a=argparse.ArgumentParser(description='Importa questões verdadeiras da API ENEM para SQLite')
    a.add_argument('--year',type=int)
    a.add_argument('--all-years',action='store_true')
    a.add_argument('--base-url',default=os.getenv('ENEM_API_BASE',DEFAULT_BASE),help='Para API ENEM self-hosted / testes')
    args=a.parse_args()
    if args.year is None and not args.all_years:a.error('Use --year 2023 ou --all-years')
    init_db()
    try:
        result=sync_all([args.year] if args.year else None,args.base_url)
        print(json.dumps({'imported':result,'total':sum(result.values())},ensure_ascii=False,indent=2))
    except (httpx.RequestError,httpx.HTTPStatusError,ValueError,RuntimeError) as exc:
        a.exit(1,f'Importação não concluída: {exc}\n')
if __name__=='__main__':main()
