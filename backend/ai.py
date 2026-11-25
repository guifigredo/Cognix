"""Orquestração pedagógica: LLM Gemini ou seleção local explicitamente simulada."""
import hashlib, json, os, secrets, random, re, time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .auth import require
from .access import assert_school, assert_class, assert_subject
from .db import rows, one, session
from .llm.provider import provider, LLMError

router=APIRouter(prefix='/api/ai',tags=['IA pedagógica'])

def _scope(user,school,subject,cls=None):
    assert_school(user,school)
    assert_subject(user,subject,school)
    if cls:
        row=assert_class(user,cls)
        if row['school_id']!=school:raise HTTPException(403,'A turma pertence a outra escola.')
        if user['role']=='prof' and not one('SELECT 1 FROM teaching_assignments WHERE teacher_id=? AND class_id=? AND subject=?',(user['id'],cls,subject)):
            raise HTTPException(403,'Disciplina não atribuída nesta turma.')

class GenerateInput(BaseModel):
    school_id:str=''
    collection_id:str=''
    subject:str
    grade:str='3ª série EM'
    topic:str=Field(min_length=2,max_length=100)
    difficulty:str='média'
    count:int=Field(1,ge=1,le=8)
    instructions:str=Field('',max_length=600)
    kind:str='multipla'

class ExamAIInput(BaseModel):
    school_id:str
    class_id:str
    subject:str
    title:str=Field('Avaliação personalizada',min_length=3,max_length=120)
    topics:list[str]=Field(default_factory=list,max_length=10)
    count:int=Field(5,ge=1,le=20)
    difficulty:str='equilibrada'
    instructions:str=Field('',max_length=600)
    allow_new:bool=False

class LegacyInput(BaseModel):
    school_id:str
    subject:str|None=None
    prompt:str=Field(min_length=15,max_length=10000)
    kind:str='json'

RATE={}
def throttle(uid):
    now=time.monotonic()
    history=[x for x in RATE.get(uid,[]) if now-x<60]
    if len(history)>=8:raise HTTPException(429,'Limite de oito solicitações por minuto.')
    RATE[uid]=history+[now]

def _sanitize_questions(payload,body):
    items=payload.get('questoes',payload.get('questions',[])) if isinstance(payload,dict) else []
    if not isinstance(items,list):raise HTTPException(502,'Formato inválido do LLM.')
    result=[]
    for x in items[:body.count]:
        if not isinstance(x,dict):continue
        prompt=str(x.get('enunciado') or x.get('prompt') or '').strip()
        alts=x.get('alternativas') or x.get('choices') or []
        if not isinstance(alts,list):continue
        alts=[str(c).strip()[:600] for c in alts]
        if len(prompt)<25 or len(alts) not in (2,4,5):continue
        # Gabaritos ausentes nunca são presumidos a partir de texto gerado.
        letter=str(x.get('gabarito') or x.get('correct_letter') or '').strip().upper()
        if letter.isdigit():letter=chr(65+int(letter)) if 0<=int(letter)<len(alts) else ''
        if len(letter)!=1 or not 'A'<=letter<chr(65+len(alts)):continue
        result.append({'prompt':prompt[:5000],'choices':alts,'correct_letter':letter,
            'topic':body.topic,'difficulty':body.difficulty,
            'explanation':str(x.get('justificativa') or x.get('explanation') or '')[:2000]})
    if not result:raise HTTPException(502,'A resposta do LLM não passou pela validação das questões.')
    return result

def _generate(body,user):
    throttle(user['id'])
    prompt=(f'Elabore {body.count} questões INÉDITAS de múltipla escolha para {body.grade}. '
       f'Disciplina: {body.subject}. Tópico: {body.topic}. Dificuldade: {body.difficulty}. '
       f'Orientação docente: {body.instructions}. '
       'Crie alternativas plausíveis sem ambiguidades; exatamente uma correta. '
       'Retorne JSON no formato {"questoes":[{"enunciado":"...",'
       '"alternativas":["...","...","...","...","..."],"gabarito":"A",'
       '"justificativa":"resolução pedagógica"}]}. Confira a consistência do gabarito.')
    try:raw=provider.call(prompt,'json')
    except LLMError as exc:raise HTTPException(503,str(exc)) from exc
    return _sanitize_questions(raw,body)

@router.get('/status')
def status(user=Depends(require('coord','prof'))):
    return {'provider':'gemini','mode':'llm' if provider.enabled else 'demonstracao',
            'model':provider.model if provider.enabled else None,
            'fallback_model':provider.fallback_model if provider.enabled else None,
            'description':('Chave configurada; use Testar conexão para validar acesso ao modelo.' if provider.enabled
            else 'Sem chave: configure GEMINI_API_KEY no servidor. Sem credencial, exibimos apenas exemplos locais identificados.')}

@router.post('/probe')
def probe(user=Depends(require('coord','prof'))):
    """Teste opt-in de uma chamada real; nunca devolve a credencial."""
    throttle(user['id'])
    if not provider.enabled:raise HTTPException(503,'Configure GEMINI_API_KEY no servidor antes do teste.')
    try:
        result=provider.call('Responda apenas com JSON: {"conexao":"ok"}.','json')
    except LLMError as exc:raise HTTPException(503,str(exc)) from exc
    if not isinstance(result,dict) or result.get('conexao')!='ok':
        raise HTTPException(502,'A API respondeu, mas a verificação de formato não passou.')
    return {'ok':True,'model':provider.used_model or provider.model,'message':'Conexão com o modelo validada por chamada real.'}

class DiagnoseInput(BaseModel):
    school_id:str
    class_id:str
    subject:str

class EvidenceDiagnosisInput(BaseModel):
    school_id:str
    class_id:str=''
    topic:str=''
    period:str='avaliacao'

@router.post('/diagnose-evidence')
def diagnose_evidence(body:EvidenceDiagnosisInput,user=Depends(require('coord','prof'))):
    """Analisa a seleção visível na área unificada com escopo e evidência verificados."""
    from .evidence import evidence, combinations
    report=evidence(body.school_id,body.class_id,body.topic,body.period,user)
    topics=report['topics']
    patterns=[]
    for item in topics[:5]:
        if item['assessments']<2:
            patterns.append(f"{item['topic']} ({item['subject']}): só {item['assessments']} avaliação registrada; tendência inconclusiva.")
        else:
            patterns.append(f"{item['topic']} ({item['subject']}): {item['classification'].lower()} em {item['assessments']} avaliações; mudança observada {item['trend']:+.1f} ponto(s).")
    if not patterns:patterns=['Não há evidência suficiente nessa seleção para identificar padrões.']
    if report['practice']:
        p=report['practice'][0]
        patterns.append(f"Nas respostas registradas, o assunto {p['key'].split('::',1)[-1]} reuniu {p['misses']} erros em {p['attempts']} tentativas.")
    if report['applied_exam_results']:
        linked=report['applied_exam_results'][0]
        patterns.append(f"Avaliação vinculada à prova '{linked['assessment']}': média registrada {linked['grade_mean']:.1f} em {linked['students']} estudantes. Associação descritiva, não causal.")
    # A sugestão de revisão é ancorada em aulas que *existem* na grade do docente.
    # Não se criam horários fictícios nem se altera a aula sem confirmação humana.
    relevant=combinations(user,body.school_id,body.class_id)
    scheduled=[]
    for combo in relevant:
        sql='''SELECT weekday,slot,topic FROM lesson_schedule
               WHERE class_id=? AND subject=? AND status='planejada' '''
        args=[combo['class_id'],combo['subject']]
        if user['role']=='prof':
            sql+=' AND teacher_id=?'
            args.append(user['id'])
        for lesson in rows(sql+' ORDER BY weekday,slot',args):
            scheduled.append({**lesson,'class_name':combo['class_name'],
                              'subject':combo['subject']})
    scheduled.sort(key=lambda x:(x['weekday'],x['slot'],x['class_name']))
    selected_topic=body.topic.split('::',1)[-1] if body.topic else ''
    priorities=[x for x in topics if x['classification']=='Dificuldade persistente']
    if not priorities:
        priorities=topics
    weekly_plan=[]
    for lesson in scheduled[:12]:
        aligned=next((x for x in priorities if x['subject']==lesson['subject']
                      and x['topic'].casefold()==lesson['topic'].casefold()),None)
        selected=next((x for x in priorities if x['subject']==lesson['subject']
                       and x['topic']==selected_topic),None)
        chosen=aligned or selected or next((x for x in priorities if x['subject']==lesson['subject']),None)
        focus=chosen['topic'] if chosen else lesson['topic']
        weekly_plan.append({'weekday':lesson['weekday'],'slot':lesson['slot'],
            'class_name':lesson['class_name'],'subject':lesson['subject'],
            'scheduled_topic':lesson['topic'],'focus_topic':focus,
            'activity':('Propor exemplos comentados, conversa sobre estratégias e exercícios em níveis; '
                        'relacionar à aula planejada.'),
            'minutes':15 if chosen and chosen['classification']=='Dificuldade persistente' else 10})
    base={'mode':'regras','generated':False,
          'summary':'Leitura dos registros por período: nenhuma nota isolada define a aprendizagem ou a capacidade de um estudante.',
          'patterns':patterns,'weekly_plan':weekly_plan,
          'message':('Sem GEMINI_API_KEY: leitura descritiva local e sugestões ligadas à grade real. '
                     'Compare sempre a qualidade e a quantidade das evidências; a revisão depende da decisão docente.')}
    if not provider.enabled:return base
    throttle(user['id'])
    safe_context={'periodo':body.period,'quantidade_estudantes':report['student_count'],
          'total_registros':report['observations_count'],'estatisticas':report['statistics'],
          'assuntos':topics[:20],'evolucao':report['timeline'][-16:],
          'erros_na_pratica':report['practice'][:12],
          'assuntos_de_provas_preparadas':report['exam_patterns'][:12],
          'avaliacoes_vinculadas_a_provas':report['applied_exam_results'][:12],
          'evidencias_qualitativas_resumo':{},
          'aulas_semanais_registradas':weekly_plan,
          'intervencoes':[{'assunto':x['topic'],'antes':x['before'],'depois':x['after'],
                           'limite':x['status']} for x in report['interventions'][:10]]}
    for x in report['qualitative']:
        key=x['competency']+' / '+x['evidence_level']
        safe_context['evidencias_qualitativas_resumo'][key]=safe_context['evidencias_qualitativas_resumo'].get(key,0)+1
    prompt=('Você observa padrões pedagógicos, não classifica a capacidade do aluno. '
        'Não invente dados de lacunas temporais nem infira causalidade de intervenções. '
        'Explique limitações de amostra e comparabilidade, conecte compreensão, aplicação, '
        'evolução, erros e registros qualitativos quando existirem. '
        'Não trate notas como medida única de aprendizagem. '
        'Devolva JSON com {"resumo":"...","padroes":["..."],'
        '"revisoes":[{"topico":"...","atividade":"...","minutos":15}]}. Dados agregados: '
        +json.dumps(safe_context,ensure_ascii=False))
    try:raw=provider.call(prompt,'json')
    except LLMError as exc:raise HTTPException(503,str(exc)) from exc
    if not isinstance(raw,dict) or not isinstance(raw.get('padroes'),list):
        raise HTTPException(502,'Diagnóstico em formato inválido.')
    summary=str(raw.get('resumo','')).strip()[:1800]
    patterns=[str(v)[:500] for v in raw['padroes'] if isinstance(v,str)][:10]
    if not summary or not patterns:raise HTTPException(502,'A IA não retornou análise suficiente.')
    # O modelo pode sugerir uma atividade, mas não inventar uma aula na agenda.
    activities=[x for x in raw.get('revisoes',[]) if isinstance(x,dict)] if isinstance(raw.get('revisoes',[]),list) else []
    revisions=[]
    for item in weekly_plan:
        suggestion=next((x for x in activities if str(x.get('topico','')).casefold()==item['focus_topic'].casefold()),None)
        revisions.append({**item,'activity':str(suggestion.get('atividade',''))[:500] or item['activity'] if suggestion else item['activity']})
    return {**base,'mode':'llm','generated':True,'summary':summary,
            'patterns':patterns,'weekly_plan':revisions,
            'message':'Análise elaborada por IA com indicadores agregados e sem identificação de estudantes. Revise antes de aplicar.'}

@router.post('/diagnose')
def diagnose(body:DiagnoseInput,user=Depends(require('coord','prof'))):
    """Analise real com LLM quando configurado; sem chave, apenas regras verificaveis."""
    from .insights import class_observations
    _scope(user,body.school_id,body.subject,body.class_id)
    info=class_observations(body.class_id,body.subject,
                            user['id'] if user['role']=='prof' else '')
    recommendations=[]
    threshold=info['school_threshold']
    for t in info['weak_topics'][:4]:
        recommendations.append((
            f"Reforçar {t['topic']}: média {t['mean']:.1f}; "
            f"{t['pct_below']:.0f}% dos estudantes avaliados abaixo de {threshold:.1f}.")
            if t['mean'] is not None and t['mean']<threshold else
            f"Observar {t['topic']}: {t.get('reason','padrão de dificuldade observado')}.")
    if info['students_to_follow']:
        recommendations.append(
            f"Acompanhar individualmente {len(info['students_to_follow'])} aluno(s) "
            "com média baixa ou queda recente.")
    if not recommendations:
        recommendations.append('Não foram detectadas prioridades graves nas notas registradas.')
    report=dict(mode='regras',generated=False,
        summary='Observações calculadas localmente a partir das avaliações e da prática.',
        patterns=recommendations,weekly_plan=info['weekly_plan'],
        observations=info,
        message='A análise por IA exige configurar GEMINI_API_KEY no servidor. Estes resultados são regras estatísticas, não um parecer gerado por IA.')
    if not provider.enabled:
        return report
    throttle(user['id'])
    # Dados agregados e sem nomes, identificadores, emails ou anotacoes livres.
    context={
        'materia':body.subject,'quantidade_alunos':info['student_count'],
        'media_turma':info['class_mean'],
        'topicos_criticos':info['weak_topics'],
        'alunos_abaixo_ou_em_queda':len(info['students_to_follow']),
        'erros_por_topico':info['practice'],
        'topicos_de_provas_preparadas':info['previous_exam_topics'],
        'medias_de_provas_vinculadas_a_avaliacoes':info['applied_exams'],
        'cronograma':[{'dia':x['weekday'],'aula':x['slot'],
                       'topico':x['scheduled_topic'],'foco_sugerido':x['focus_topic']}
                      for x in info['weekly_plan']]}
    prompt=('Voce e assistente de analise pedagogica. Observe padroes reais, sem inventar notas, '
       'previsoes ou atributos pessoais. Use SOMENTE os dados anonimizados abaixo e sugira '
       'revisoes compativeis com a grade semanal. Escreva em portugues claro, com prioridades '
       'e a evidência numerica que justifica cada recomendacao. '
       'Retorne JSON: {"resumo":"texto","padroes":["texto"],'
       '"revisoes":[{"dia":0,"aula":1,"topico":"texto","atividade":"texto","minutos":15}]}. '
       'Dados: '+json.dumps(context,ensure_ascii=False))
    try:result=provider.call(prompt,'json')
    except LLMError as exc:raise HTTPException(503,str(exc)) from exc
    if not isinstance(result,dict):
        raise HTTPException(502,'Resposta do LLM em formato inválido.')
    summary=str(result.get('resumo') or '').strip()[:1800]
    patterns=[str(x)[:600] for x in result.get('padroes',[]) if isinstance(x,str)][:10]
    revisions=[{'weekday':x.get('dia'),'slot':x.get('aula'),
                'focus_topic':str(x.get('topico',''))[:120],
                'activity':str(x.get('atividade',''))[:700],
                'minutes':x.get('minutos',15)}
               for x in result.get('revisoes',[])[:15] if isinstance(x,dict)]
    if not summary or not patterns:
        raise HTTPException(502,'Análise retornada pela IA estava incompleta.')
    return {**report,'mode':'llm','generated':True,'summary':summary,
            'patterns':patterns,'weekly_plan':revisions,
            'message':'Análise produzida com IA sobre indicadores anonimizados. Revise as sugestões antes de aplicar.'}

@router.post('/questions')
def generate_questions(body:GenerateInput,user=Depends(require('coord','prof'))):
    from .question_bank import collection_for, _collection_create
    if body.collection_id:
        collection=collection_for(user,body.collection_id)
        if collection['kind']=='school':assert_subject(user,body.subject,collection['school_id'])
    else:
        if not body.school_id:raise HTTPException(422,'Selecione um acervo em Salvar em.')
        _scope(user,body.school_id,body.subject)
        with session() as db:
            collection_id=_collection_create(db,kind='school',school=body.school_id)
        collection=collection_for(user,collection_id)
    if body.kind!='multipla':raise HTTPException(422,'Nesta rota, somente múltipla escolha está habilitada.')
    if not provider.enabled:
        qs=rows('''SELECT id,source,prompt,context,alternatives_json,correct_letter,topic,difficulty FROM questions
          WHERE discipline=? AND source='Cognix Demo' AND status='published'
          AND (topic LIKE ? OR ?='') ORDER BY id LIMIT ?''',
          (body.subject,'%'+body.topic+'%',body.topic,body.count))
        if not qs:qs=rows('''SELECT id,source,prompt,context,alternatives_json,correct_letter,topic,difficulty FROM questions
          WHERE discipline=? AND source='Cognix Demo' AND status='published' ORDER BY id LIMIT ?''',(body.subject,body.count))
        for q in qs:q['alternatives']=json.loads(q.pop('alternatives_json'))
        return {'mode':'demonstracao','generated':False,'questions':qs,
                'message':'Sem chave Gemini: exemplos selecionados do acervo fictício, sem geração por LLM.'}
    generated=_generate(body,user)
    output=[]
    batch=secrets.token_hex(12)
    import_hash=hashlib.sha256((batch+body.topic).encode()).hexdigest()
    with session() as db:
        db.execute('''INSERT INTO question_batches(id,collection_id,uploader_id,origin_format,filename,content_sha256)
            VALUES(?,?,?,?,?,?)''',(batch,collection['id'],user['id'],'llm',f'Geração IA · {body.topic}',import_hash))
        for pos,x in enumerate(generated,1):
            qid='llm-'+secrets.token_hex(12)
            alternatives=[{'letter':chr(65+i),'text':v,'file':''} for i,v in enumerate(x['choices'])]
            db.execute('''INSERT INTO questions(id,source,source_key,area,discipline,title,context,prompt,alternatives_json,
                media_json,correct_letter,topic,difficulty,status,rights_status,source_url,creator_id,school_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (qid,'Cognix LLM',qid,body.subject,body.subject,body.topic,x['explanation'],x['prompt'],
                 json.dumps(alternatives,ensure_ascii=False),'[]',x['correct_letter'],x['topic'],x['difficulty'],
                 'review','pending','',user['id'],collection['school_id']))
            db.execute('''INSERT INTO question_records(question_id,collection_id,registered_by,provenance,content_sha256)
                VALUES(?,?,?,?,?)''',(qid,collection['id'],user['id'],f'llm:{batch}:{pos}',hashlib.sha256(x['prompt'].encode()).hexdigest()))
            db.execute('''INSERT INTO question_import_items(batch_id,position,question_id,missing_json,suggestion_json)
                VALUES(?,?,?,?,?)''',(batch,pos,qid,'[]',json.dumps({'discipline':body.subject,'topic':body.topic,
                'origin':'LLM; requer revisão docente','confidence':'não confirmada'},ensure_ascii=False)))
            output.append({'id':qid,'prompt':x['prompt'],'alternatives':alternatives,'correct_letter':x['correct_letter'],
                           'topic':x['topic'],'difficulty':x['difficulty'],'status':'review','explanation':x['explanation']})
    return {'mode':'llm','generated':True,'questions':output,'batch_id':batch,'collection_id':collection['id'],
            'message':'Rascunhos salvos no acervo escolhido: revisão docente obrigatória antes de publicar.'}

@router.post('/exam')
def generate_exam(body:ExamAIInput,user=Depends(require('coord','prof'))):
    _scope(user,body.school_id,body.subject,body.class_id)
    args=[body.subject,body.school_id,user['id']]
    sql="""SELECT * FROM questions WHERE discipline=? AND status='published'
        AND rights_status IN ('demo','authorized') AND correct_letter != ''
        AND (school_id IS NULL OR school_id=?)
        AND (creator_id IS NULL OR creator_id=?)"""
    if body.topics:
        sql+=' AND topic IN ('+','.join('?' for _ in body.topics)+')'
        args+=body.topics
    pool=rows(sql,args)
    if body.difficulty in ('fácil','média','difícil'):
        pool=[q for q in pool if q['difficulty']==body.difficulty]
    # Sorteio determinístico por requisição não expõe outras disciplinas nem conteúdo não revisado.
    random.SystemRandom().shuffle(pool)
    chosen=pool[:body.count]
    newly=[]
    if body.allow_new and len(chosen)<body.count and provider.enabled:
        to_create=body.count-len(chosen)
        topic=body.topics[0] if body.topics else body.subject
        draft=generate_questions(GenerateInput(school_id=body.school_id,subject=body.subject,
                  topic=topic,grade=one('SELECT grade FROM classes WHERE id=?',(body.class_id,))['grade'],
                  difficulty=body.difficulty if body.difficulty in ('fácil','média','difícil') else 'média',
                  count=min(8,to_create),instructions=body.instructions),user)
        newly=draft['questions']
    selected=[x['id'] for x in chosen]+[x['id'] for x in newly]
    if not selected:raise HTTPException(422,'Nenhuma questão disponível. Ajuste os filtros ou crie novas questões com LLM.')
    exam_id=secrets.token_hex(12)
    with session() as db:
        db.execute('INSERT INTO exam_sets(id,creator_id,class_id,subject,title) VALUES (?,?,?,?,?)',
                   (exam_id,user['id'],body.class_id,body.subject,body.title))
        for i,qid in enumerate(selected):db.execute('INSERT INTO exam_items(exam_id,question_id,position) VALUES(?,?,?)',(exam_id,qid,i))
    return {'id':exam_id,'mode':'llm' if newly else 'selecao','count':len(selected),
            'draft_questions':len(newly), 'message':('Prova rascunho: revise questões geradas pelo LLM.' if newly
                else 'Prova montada com questões já cadastradas; não houve geração pelo LLM.')}

@router.post('/legacy')
def legacy_llm(body:LegacyInput,user=Depends(require('coord','prof','aluno'))):
    assert_school(user,body.school_id)
    if body.subject:assert_subject(user,body.subject,body.school_id)
    throttle(user['id'])
    if not provider.enabled:raise HTTPException(503,'LLM indisponível: configure GEMINI_API_KEY; use os recursos locais de demonstração.')
    if body.kind not in ('json','text'):raise HTTPException(422,'Tipo inválido.')
    # O navegador envia apenas dados da escola liberada pela sessão e prompts sem identidade dos alunos.
    try:result=provider.call(body.prompt,body.kind)
    except LLMError as exc:raise HTTPException(503,str(exc)) from exc
    return {'mode':'llm','result':result}
