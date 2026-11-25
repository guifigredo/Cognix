import {stats,histogram,evolution,boxplots,heatColor} from './analytics.js';

/* Uma tela de análise: leitura rápida visível e detalhamento no próprio indicador. */
export function createLearningInsights({state,api,e,head,pill,empty,role,alertUser,renderPage}){
 const st={class_id:'',topic:'',period:'avaliacao',result:null,resultKey:''};
 const safe=x=>e(String(x??''));
 const qs=o=>new URLSearchParams(Object.entries(o).filter(([,v])=>v!==''&&v!=null)).toString();
 const fmt=(v,d=1)=>v===null||v===undefined||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
 const note=x=>`<p class="muted small">${safe(x)}</p>`;
 const thead=(titles)=>`<thead><tr>${titles.map(x=>`<th>${safe(x)}</th>`).join('')}</tr></thead>`;
 const tab=(titles,rows)=>`<div class="tablewrap"><table>${thead(titles)}<tbody>${rows||`<tr><td colspan="${titles.length}">Não há observações nesse recorte.</td></tr>`}</tbody></table></div>`;
 const more=(label,children)=>`<details class="inline-details"><summary>${safe(label)}</summary><div class="inline-details-body">${children}</div></details>`;
 const metric=(label,value,context,detail='')=>`<div class="card kpi"><span class="label">${safe(label)}</span><div class="num">${safe(value)}</div><small>${safe(context)}</small>${detail?more('Ver detalhes',detail):''}</div>`;
 const days=['Segunda','Terça','Quarta','Quinta','Sexta'];
 const periods=[['avaliacao','Avaliação'],['semana','Semana'],['quinzena','Quinzena'],['mes','Mês'],['bimestre','Bimestre'],['semestre','Semestre']];
 const currentSchool=()=>state.school==='todas'?state.me.schools[0]?.id:state.school;
 const choices=(items,value)=>items.map(([id,label])=>`<option value="${safe(id)}" ${String(id)===String(value)?'selected':''}>${safe(label)}</option>`).join('');
 async function page(){
  if(role()==='aluno')return empty('Acesso de educadores','As informações individuais do aluno permanecem em Meu desempenho.');
  const school=currentSchool();
  if(!school)return empty('Sem instituição','Selecione uma escola para acompanhar.');
  const classes=await api('/classes?'+qs({school}));
  if(st.class_id&&!classes.some(x=>x.id===st.class_id)){st.class_id='';st.topic='';}
  let data;
  try{data=await api('/pedagogy/evidence?'+qs({school,class_id:st.class_id,topic:st.topic,period:st.period}));}
  catch(err){if(st.topic&&err.message.includes('Tópico indisponível')){
     st.topic='';data=await api('/pedagogy/evidence?'+qs({school,class_id:st.class_id,period:st.period}));
  }else throw err;}
  const topicOptions=data.topic_options||[],topic=data.topics[0],counts=data.statistics||{};
  const currentTopic=st.topic?topicOptions.find(x=>x.key===st.topic):null;
  const title=role()==='coord'?'Desempenho e diagnóstico institucional':'Desempenho e diagnóstico';
  const desc='Resultados de avaliações registradas, evolução por intervalo, evidências por assunto e recomendações em uma só página.';
  const alerts=await api('/pedagogy/attention?'+qs({school}));
  const watched=(alerts.students_to_follow||[]).filter(x=>(!st.class_id||x.class_id===st.class_id)&&(!currentTopic||x.subject===currentTopic.subject));
  const levels={'nao_observado':'Ainda não observado','em_desenvolvimento':'Em desenvolvimento',
      'com_apoio':'Compreensão com apoio','autonomia':'Autonomia observada','transferencia':'Aplicação em novo contexto'};
  const competence={'conceito':'Conceito','aplicacao':'Aplicação','autonomia':'Autonomia','transferencia':'Transferência','erros':'Erros recorrentes'};
  const key=JSON.stringify([school,st.class_id,st.topic,st.period]);
  const showAI=st.result&&st.resultKey===key;
  let students=[];
  if(st.class_id&&currentTopic){
    const m=await api('/pedagogy/matrix?'+qs({class_id:st.class_id,subject:currentTopic.subject}));
    students=m.students||[];
  }
  const errorNotebook=st.class_id&&currentTopic?
    await api('/teacher-tools/error-notebook?'+qs({class_id:st.class_id,subject:currentTopic.subject,topic:currentTopic.topic})):null;
  const periodRows=data.timeline.map(x=>`<tr><td>${safe(x.period)}</td><td>${fmt(x.mean)}</td><td>${x.students}</td><td>${x.count}</td></tr>`).join('');
  const teacherDetails=data.topics.map(x=>`<div class="evidence-topic"><div class="row spread"><div><strong>${safe(x.topic)}</strong><small class="muted">${safe(x.subject)} · ${safe(x.classification)}</small></div><span class="evidence-mean">${fmt(x.mean)}</span></div>
    ${more('Ver evidências',`<p>${x.students} estudante(s), ${x.assessments} avaliação(ões), ${x.count} registro(s) por tópico.</p><p>Variação entre avaliações: ${x.trend===null?'Indeterminada':(x.trend>=0?'+':'')+fmt(x.trend)}. Períodos com média abaixo do critério da escola (${fmt(data.school_threshold)}): ${x.weak_periods}.</p><p>Esses valores não descrevem capacidade ou autonomia por si só.</p>`)}</div>`).join('');
  const scale=['mean','median','sd','variance','q1','q3','min','max','cv'];
  const captions=['Média','Mediana','Desvio padrão amostral','Variância','Q1','Q3','Mínimo','Máximo','CV (%)'];
  const detailsTable=tab(['Medida','Valor'],scale.map((k,i)=>`<tr><td>${captions[i]}</td><td>${fmt(counts[k],2)}</td></tr>`).join(''));
  const selectedPeriods=data.timeline.slice(-8).map(x=>x.period);
  const heatmap=tab(['Assunto',...selectedPeriods],(data.period_heatmap||[]).map(x=>`<tr><td>${safe(x.topic)}<small class="muted">${safe(x.subject)}</small></td>${selectedPeriods.map(p=>`<td style="${heatColor(x.periods[p])}">${fmt(x.periods[p])}</td>`).join('')}</tr>`).join(''));
  const topicsForStudent=data.topics.slice(0,12);
  const studentTable=tab(['Estudante',...topicsForStudent.map(x=>x.topic),'Média dos registros'],
    (data.student_heatmap||[]).map(x=>`<tr><td>${safe(x.name)}</td>${topicsForStudent.map(t=>`<td style="${heatColor(x.topics[t.key])}">${fmt(x.topics[t.key])}</td>`).join('')}<td>${fmt(x.average)}</td></tr>`).join(''));
  const observed=data.qualitative||[],interventions=data.interventions||[];
  const activity=data.practice||[];
  const practices=activity.slice(0,6).map(x=>{
    const ratio=x.attempts?x.misses/x.attempts:0;
    return `<div class="evidence-topic"><div class="row spread"><strong>${safe(x.key.split('::')[1]||'Assunto')}</strong><span class="muted small">${x.misses} erros / ${x.attempts} respostas</span></div><div class="resultbar"><span style="width:${Math.min(100,ratio*100)}%"></span></div></div>`;
  }).join('');
  const wrongAnswerCards=(errorNotebook?.questions||[]).slice(0,5).map(q=>`<div class="evidence-topic"><div class="row spread"><strong>${safe(q.topic)} · ${safe(q.title)}</strong><span class="muted small">${q.misses} erros / ${q.attempts} tentativas</span></div>
    <div class="resultbar"><span style="width:${Math.min(100,100-q.accuracy)}%"></span></div>
    ${Object.entries(q.hypotheses).map(([letter,hyp])=>`<div class="misconception-row"><span>Alternativa ${safe(letter)} · ${q.choices[letter]} resposta(s)</span><span class="muted small">${hyp?safe(hyp):'Causa ainda não classificada'}</span><button class="btn sm" data-insights="tag-error" data-question="${safe(q.question_id)}" data-letter="${safe(letter)}" data-subject="${safe(currentTopic.subject)}">${hyp?'Revisar hipótese':'Descrever possível erro'}</button></div>`).join('')}</div>`).join('');
  const qualitative=observed.slice(0,5).map(x=>`<div class="listline"><span class="pill teal">${safe(competence[x.competency]||x.competency)}</span><div class="flex"><b>${safe(levels[x.evidence_level]||x.evidence_level)}</b><div class="muted small">${safe(x.topic)} · ${safe(x.observed_on)} · ${safe(x.student_name)}</div>${x.note?`<p>${safe(x.note)}</p>`:''}</div></div>`).join('');
  const linkedExams=(data.applied_exam_results||[]).map(x=>`<div class="listline"><div class="flex"><strong>${safe(x.assessment)}</strong><div class="muted small">Média observada: ${fmt(x.grade_mean)} · ${x.students} estudantes com nota</div></div></div>`).join('');
  const examDetails=tab(['Assunto','Questões em provas montadas'],(data.exam_patterns||[]).map(x=>`<tr><td>${safe(x.topic)}</td><td>${x.quantity}</td></tr>`).join(''));
  const interventionCards=interventions.slice(0,6).map(x=>`<div class="listline"><div class="flex"><b>${safe(x.topic)} · ${safe(x.applied_on)}</b><div class="muted small">${safe(x.activity)}</div><div class="small">Antes: ${fmt(x.before)} → Depois: ${fmt(x.after)}</div><small class="muted">${safe(x.status)}</small></div></div>`).join('');
  const interventionForm=st.class_id&&currentTopic?`<form id="insights-intervention" class="stack evidence-inline-form" data-subject="${safe(currentTopic.subject)}" data-topic="${safe(currentTopic.topic)}"><h3>Registrar atividade de revisão</h3><div class="formgrid"><label class="field">Data<input type="date" name="applied_on" required value="${new Date().toISOString().slice(0,10)}"></label><label class="field">O que foi realizado?<input name="activity" required minlength="5" maxlength="500" placeholder="Ex.: revisão de gráficos com exemplos"></label></div><label class="field">Observações (opcional)<textarea name="notes" rows="2" maxlength="800"></textarea></label><button class="btn sm primary" type="submit">Salvar intervenção</button></form>`:'';
  const qualitativeForm=st.class_id&&currentTopic&&students.length?`<form id="insights-observation" class="stack evidence-inline-form" data-subject="${safe(currentTopic.subject)}" data-topic="${safe(currentTopic.topic)}"><h3>Registrar evidência de aprendizagem</h3><div class="formgrid"><label class="field">Estudante<select name="student_id">${choices(students.map(x=>[x.id,x.name]),students[0].id)}</select></label><label class="field">Dimensão<select name="competency">${choices(Object.entries(competence),'conceito')}</select></label><label class="field">O que foi observado?<select name="evidence_level">${choices(Object.entries(levels),'em_desenvolvimento')}</select></label><label class="field">Data<input type="date" name="observed_on" required value="${new Date().toISOString().slice(0,10)}"></label></div><label class="field">Evidência concreta (opcional)<textarea name="note" rows="2" maxlength="800" placeholder="Ex.: explicou seu raciocínio com apoio e depois resolveu outro exemplo"></textarea></label><button type="submit" class="btn sm primary">Salvar observação</button></form>`:'';
  return head(title,desc)+
    `<section class="card compact-analytics-controls"><div class="row analysis-filter-row"><label class="field">Turma<select id="insights-class">${choices([['', 'Geral · todas as turmas'],...classes.map(x=>[x.id,x.name])],st.class_id)}</select></label><label class="field">Tópico<select id="insights-topic">${choices([['','Geral · todos os tópicos'],...topicOptions.map(x=>[x.key,x.topic+' · '+x.subject])],st.topic)}</select></label></div><div class="row evidence-periods"><span class="muted small">Comparar por:</span>${periods.map(([id,label])=>`<button type="button" class="btn sm ${st.period===id?'primary':''}" data-insights="period" data-period="${id}" aria-pressed="${st.period===id}">${label}</button>`).join('')}</div>${st.class_id&&currentTopic?`<a class="btn sm" href="/api/teacher-tools/report.csv?${qs({class_id:st.class_id,subject:currentTopic.subject})}">Baixar relatório pedagógico (CSV)</a>`:''}</section>
     <div class="grid cols4" style="margin-top:18px">${metric('Estudantes observados',data.student_count,'Somente com registros nesse recorte',`<p>Estudantes distintos com pelo menos uma nota por tópico: ${data.student_count}. Quem não foi avaliado não entra no denominador.</p>`)}${metric('Tópicos',data.topics.length,'Com evidências registradas',`<p>Assuntos distintos neste recorte: ${data.topics.map(x=>safe(x.topic)).join(', ')||'nenhum'}.</p>`)}${metric('Avaliações',data.basis.assessments,'Com dados neste recorte',`<p>Avaliações distintas por turma e disciplina: ${data.basis.assessments}. A divisão em ${safe(st.period)} usa apenas as datas registradas.</p>`)}${metric('Registros',data.observations_count,'Tópico × avaliação × estudante',`<p>${data.basis.dated} registros associados a avaliações datadas; ${data.basis.unstructured} observações qualitativas consultadas. Uma nota por tópico não é um estudante adicional.</p>`)}</div>
     <p class="muted small evidence-disclaimer">${safe(data.warning)} ${data.observations_count?`Média dos registros: ${fmt(counts.mean)}; distribuição e tendências requerem interpretação pedagógica.`:''}</p>
     <div class="grid cols2 analytics-panels"><section class="card"><div class="row spread"><div><span class="eyebrow">Evolução</span><h2>Aprendizagem ao longo do tempo</h2></div>${pill(st.period,'blue')}</div>${data.timeline.length?evolution(data.timeline.slice(-8).map(x=>({assessment:x.period,stats:{mean:x.mean,n:x.count}}))):note('Não existem avaliações datadas compatíveis com o período selecionado.')}
       ${data.timeline.length>8?note('Gráfico: oito últimos intervalos observados. O detalhamento contém todos os registros.'):''}
       ${more('Ver resultados de cada período',tab(['Período','Média','Estudantes','Observações'],periodRows))}</section>
     <section class="card"><span class="eyebrow">Tópicos</span><h2>Dificuldades, avanços e consistência</h2><p class="muted small">A classificação indica o padrão dos resultados disponíveis, não uma habilidade fixa do estudante.</p>${teacherDetails||note('Sem tópicos registrados.')}</section>
     <section class="card"><span class="eyebrow">Distribuição</span><h2>Variação dos resultados</h2>${data.scores.length?histogram(data.scores):note('Ainda sem notas por tópico nesta seleção.')}${more('Ver medidas estatísticas e boxplots',detailsTable+(data.period_distributions.length?boxplots(data.period_distributions.slice(-8)):''))}</section>
     <section class="card"><span class="eyebrow">Questões e competências</span><h2>Caderno de erros e evidências qualitativas</h2>${practices||note('Ainda não há respostas suficientes em questões de prática para identificar erros recorrentes.')}
       ${errorNotebook?`${more('Ver erros por questão e alternativa',wrongAnswerCards||note('Nenhuma resposta individual foi registrada nesta turma e disciplina. Provas apenas montadas não são contadas como aplicadas.'))}<p class="muted small">${safe(errorNotebook.note)}</p>`:note('Selecione uma turma e um tópico para examinar erros por alternativa.')}
       ${(data.applied_exam_results||[]).length||(data.exam_patterns||[]).length?`<h3 class="small-subheading">Provas relacionadas às avaliações</h3>${linkedExams||note('Existem provas montadas, mas nenhuma está vinculada a notas de uma avaliação.')}${more('Ver tópicos das provas montadas',examDetails)}`:''}
       <h3 class="small-subheading">Observações registradas pelo professor</h3>${qualitative||note('Compreensão conceitual, autonomia e transferência ainda não foram observadas qualitativamente neste recorte.')}
       ${more('Ver todas as observações',tab(['Estudante','Tópico','Dimensão','Evidência','Data'],observed.map(x=>`<tr><td>${safe(x.student_name)}</td><td>${safe(x.topic)}</td><td>${safe(competence[x.competency])}</td><td>${safe(levels[x.evidence_level])}</td><td>${safe(x.observed_on)}</td></tr>`).join('')))}</section></div>
     <section class="card" style="margin-top:18px"><div class="row spread"><div><span class="eyebrow">Mapa de padrões</span><h2>Tópicos × períodos observados</h2><p class="muted small">As células vazias indicam falta de dados. Não são preenchidas por estimativas.</p></div>${pill(data.period_heatmap.length+' assuntos','blue')}</div>${heatmap}</section>
     <div class="grid cols2" style="margin-top:18px"><section class="card"><h2>Estudantes para acompanhamento</h2><p class="muted small">Os alertas consideram evolução e evidências, não um índice de capacidade.</p>${watched.slice(0,10).map(x=>`<div class="listline"><div class="flex"><b>${safe(x.student_name)}</b><div class="muted small">${safe(x.class_name)} · ${safe(x.subject)} · ${safe(x.reason||'Acompanhamento')}</div></div>${x.student_id?`<button class="btn sm" data-insights="feedback" data-class="${safe(x.class_id)}" data-subject="${safe(x.subject)}" data-student="${safe(x.student_id)}">Preparar devolutiva</button>`:''}</div>`).join('')||note('Sem estudantes sinalizados pelas regras atuais.')}<div id="insights-feedback-result"></div>
       ${more('Ver mapa individual por assunto',studentTable)}</section>
     <section class="card"><h2>Intervenções e resultados posteriores</h2><p class="muted small">A diferença entre avaliações anteriores e posteriores não estabelece causalidade por si só.</p>${interventionCards||note('Ainda não há intervenções pedagógicas registradas para esta seleção.')}${more('Ver todas as intervenções',tab(['Tópico','Data','Atividade','Antes','Depois','Limitação'],interventions.map(x=>`<tr><td>${safe(x.topic)}</td><td>${safe(x.applied_on)}</td><td>${safe(x.activity)}</td><td>${fmt(x.before)}</td><td>${fmt(x.after)}</td><td>${safe(x.status)}</td></tr>`).join('')))}</section></div>
     ${qualitativeForm||interventionForm?`<section class="card evidence-registration"><h2>Registrar o que a avaliação não mostra</h2><p class="muted small">Selecione uma turma e um tópico acima para relacionar evidências de compreensão, atividades de revisão e resultados posteriores.</p><div class="grid cols2">${qualitativeForm||''}${interventionForm||''}</div></section>`:''}
     <section class="card ai-diagnostic-card" style="margin-top:20px"><div class="row spread"><div><span class="eyebrow">Depois de consultar as evidências</span><h2>Executar diagnóstico e sugerir revisões com IA</h2><p class="muted small">A análise considera as avaliações e intervalos acima, erros e observações disponíveis. Recomendações são submetidas à decisão do professor.</p></div><button type="button" class="btn primary" data-insights="diagnose">Executar diagnóstico</button></div>
       <div id="insights-ai-result" class="ai-result">${showAI?renderAI(st.result):'<p class="muted small">Nenhum diagnóstico com IA foi executado para esta seleção. Os gráficos anteriores são calculados diretamente dos dados.</p>'}</div></section>`;
 }
 function renderAI(report){
  return `<div class="row spread"><b>${safe(report.generated?'Interpretação com IA':'Leitura estatística local')}</b>${pill(report.generated?'IA ativa':'Sem chave · regras','teal')}</div><p>${safe(report.summary)}</p><h3>Padrões e limitações</h3><ul>${(report.patterns||[]).map(x=>`<li>${safe(x)}</li>`).join('')}</ul><h3>Sugestões conectadas ao cronograma</h3>${(report.weekly_plan||[]).map(x=>`<div class="listline"><span class="pill blue">${safe(days[x.weekday]||'Aula')} · ${Number(x.slot??0)+1}ª</span><div class="flex"><b>${safe(x.focus_topic||x.topico||'Tópico')} ${x.class_name?`· ${safe(x.class_name)}`:''}</b><div class="muted small">${safe(x.subject||'')} · aula prevista: ${safe(x.scheduled_topic||'não informada')}</div><div class="muted small">${safe(x.activity||x.atividade||'Atividade de aprofundamento')} · ${safe(x.minutes||x.minutos||15)} min</div></div></div>`).join('')||note('Não há aulas planejadas nessa seleção. Registre a semana para receber sugestões em horários reais.')}<p class="muted small">${safe(report.message)}</p>`;
 }
 function bind(root){
  root.addEventListener('change',async ev=>{
    try{
      if(ev.target.id==='insights-class'){st.class_id=ev.target.value;st.topic='';st.result=null;await renderPage();}
      if(ev.target.id==='insights-topic'){st.topic=ev.target.value;st.result=null;await renderPage();}
    }catch(err){alertUser(err.message,false);}
  });
  root.addEventListener('click',async ev=>{
    const button=ev.target.closest('[data-insights]');if(!button)return;
    try{
      if(button.dataset.insights==='period'){st.period=button.dataset.period;st.result=null;await renderPage();return;}
      if(button.dataset.insights==='tag-error'){
        const description=prompt(`Qual dificuldade a escolha da alternativa ${button.dataset.letter} pode indicar? (hipótese pedagógica)`);
        if(description===null)return;
        if(description.trim().length<5)throw Error('Descreva a hipótese com pelo menos cinco caracteres.');
        await api('/teacher-tools/error-notebook/'+encodeURIComponent(button.dataset.question)+'/hypothesis?'+
          qs({class_id:st.class_id,subject:button.dataset.subject}),
          {letter:button.dataset.letter,description:description.trim()});
        alertUser('Hipótese salva e identificada como interpretação docente.');await renderPage();return;
      }
      if(button.dataset.insights==='feedback'){
        const target=document.getElementById('insights-feedback-result');if(!target)return;
        target.innerHTML='<p class="muted small">Preparando rascunho a partir dos registros…</p>';
        const result=await api('/teacher-tools/feedback?'+qs({class_id:button.dataset.class,subject:button.dataset.subject,student_id:button.dataset.student}));
        target.innerHTML=`<div class="feedback-review"><h3>Devolutiva para ${safe(result.student_name)}</h3><p class="muted small">${safe(result.note)}</p><textarea id="insights-feedback-draft" rows="6">${safe(result.draft)}</textarea><button class="btn sm" data-insights="copy-feedback">Copiar texto revisado</button></div>`;
        target.scrollIntoView({behavior:'smooth',block:'nearest'});return;
      }
      if(button.dataset.insights==='copy-feedback'){
        const text=document.getElementById('insights-feedback-draft')?.value||'';
        if(!text)throw Error('Não há devolutiva para copiar.');
        await navigator.clipboard.writeText(text);alertUser('Devolutiva copiada. Ela não foi enviada automaticamente.');return;
      }
      if(button.dataset.insights==='diagnose'){
        const place=document.getElementById('insights-ai-result');if(!place)return;
        place.textContent='Reunindo as evidências e analisando os padrões…';button.disabled=true;
        try{const report=await api('/ai/diagnose-evidence',{
          school_id:currentSchool(),class_id:st.class_id,topic:st.topic,period:st.period});
          st.result=report;st.resultKey=JSON.stringify([currentSchool(),st.class_id,st.topic,st.period]);
          place.innerHTML=renderAI(report);
        }finally{button.disabled=false;}
      }
    }catch(err){alertUser(err.message,false);const place=document.getElementById('insights-ai-result');if(place)place.textContent=err.message;}
  });
  root.addEventListener('submit',async ev=>{
    if(!['insights-observation','insights-intervention'].includes(ev.target.id))return;
    ev.preventDefault();const form=ev.target,fd=Object.fromEntries(new FormData(form).entries());
    const subject=form.dataset.subject,topic=form.dataset.topic;
    try{const url=form.id==='insights-observation'?'/pedagogy/evidence/observations':'/pedagogy/evidence/interventions';
      const button=form.querySelector('[type=submit]');if(button)button.disabled=true;
      try{await api(url,{school_id:currentSchool(),class_id:st.class_id,subject,topic,...fd});
       alertUser('Registro gravado no histórico pedagógico.');await renderPage();}
      finally{if(button)button.disabled=false;}
    }catch(err){alertUser(err.message,false);}
  });
 }
 return {page,bind,focus:(context,topic='')=>{
   st.class_id=context.split('|')[0]||'';st.topic=topic;st.period='avaliacao';st.result=null;
 }};
}
