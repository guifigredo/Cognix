/* Experiência do estudante derivada do HTML original e do banco autenticado.
   As notas servem como evidências de estudo, não como diagnóstico de aptidão. */
export function createStudentExperience({state,api,e,head,pill,empty,alertUser,renderPage,drawApp,school}){
 const safe=x=>e(String(x??''));
 const fmt=(n,d=1)=>n===null||n===undefined||!Number.isFinite(Number(n))?'—':Number(n).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
 const data=()=>api('/student/dashboard?school='+encodeURIComponent(school()));
 const meter=(n,max=10)=>`<div class="learning-meter"><span style="width:${Math.min(100,Math.max(0,Number(n||0)/max*100))}%"></span></div>`;
 const more=(text,body)=>`<details class="student-more"><summary>Saiba mais · ${safe(text)}</summary><div>${body}</div></details>`;
 const intro=(title,teaser,detail)=>`<h2>${safe(title)}</h2><p class="feature-teaser">${safe(teaser)}</p>${detail?more('como interpretar',`<p>${safe(detail)}</p>`):''}`;
 const areas=r=>`<div class="grid cols4 student-area-grid">${(r.areas||[]).map(x=>`<article class="card student-area"><span class="eyebrow">${safe(x.area)}</span><div class="num">${fmt(x.average)}</div>${meter(x.average)}<p class="muted small">${x.subjects?`${x.subjects} disciplina(s) com nota registrada`:'Ainda sem avaliações nessa área'}</p></article>`).join('')}</div>`;
 const why=x=>`<ul class="student-reasons">${(x.reasons||['Precisa de mais observações']).map(a=>`<li>${safe(a)}</li>`).join('')}</ul>`;
 const suggestion=x=>{const s=x.subject.toLowerCase();return /matem|fís|quím|estat/.test(s)?'Refaça um exemplo resolvido, explique cada etapa e pratique duas variações.':/ling|port|red|liter/.test(s)?'Releia o texto, destaque pistas e explique sua interpretação em voz alta.':'Recupere o conceito com mapa visual e compare dois casos concretos.';};
 const topicCard=(x,i,student=true)=>`<article class="learning-topic-card"><div class="row spread"><div><span class="eyebrow">${safe(x.subject)} · ${safe(x.area||'Área curricular')}</span><h3>${safe(x.topic)}</h3></div>${pill(i===0?'Comece aqui':x.history_priority==='alta'?'Revisão prioritária':'Acompanhar',i===0?'red':'amber')}</div>
   <div class="learning-topic-metrics"><span>Média observada <b>${fmt(x.average)}</b></span><span>Prática <b>${x.accuracy===null?'Sem respostas':fmt(x.accuracy,0)+'%'}</b></span><span>${x.answers} tentativa(s)</span></div>
   <p class="muted small" style="margin-bottom:4px">Por que acompanhar este tópico?</p>${why(x)}
   <div class="student-next"><b>Uma forma de trabalhar:</b> ${safe(suggestion(x))}</div>
   ${more('evidências e limites',`<p>Estes indicadores descrevem registros de avaliações e prática. Uma nota baixa ou poucas respostas não identificam capacidade pessoal. A prioridade é um convite para estudar e observar novamente.</p>`)}
   ${student?`<button class="btn sm" data-student="study-topic" data-topic="${safe(x.topic)}">Praticar este tópico</button>`:''}</article>`;
 async function home(){const r=await data();const first=r.topics[0];const next=r.grades.flatMap(x=>x.assessments.filter(a=>a.score===null).map(a=>({...a,subject:x.subject}))).sort((a,b)=>(a.date||'9999').localeCompare(b.date||'9999')).slice(0,4);
  return head('Meu espaço de aprendizagem','Seu desempenho, seus pontos fortes e os próximos passos, sem comparação com colegas.')+
    `<section class="card student-section">${intro('Meu desempenho por áreas','Médias parciais de avaliações registradas, agrupadas por campo de conhecimento.','Uma área sem nota aparece sem dados. Esses resultados não definem talento, vocação ou potencial.')}${areas(r)}</section>
    <div class="grid cols2 student-main-grid"><section class="card">${intro('O que merece minha atenção','Conheça um conteúdo a revisitar e por que ele apareceu como prioridade.','A seleção considera notas por tópico, prática e histórico; nenhum dado isolado determina sua aprendizagem.')}${first?topicCard(first,0):'<p class="muted">Ainda não há avaliações e respostas suficientes para priorizar tópicos.</p>'}<button class="btn primary" data-student="navigate" data-page="meudesempenho">Ver todos os tópicos</button></section>
    <section class="card">${intro('Meu próximo passo','Avaliações pendentes e ações para organizar sua semana.','Consulte o cronograma da escola para ver aulas e planos de cada professor.')}${next.map(x=>`<div class="listline"><span class="pill blue">${safe(x.date||'A definir')}</span><div class="flex"><b>${safe(x.name)}</b><div class="muted small">${safe(x.subject)}</div></div></div>`).join('')||'<p class="muted">Sem avaliações pendentes registradas.</p>'}<div class="row" style="margin-top:16px"><button class="btn" data-student="navigate" data-page="cronogramaaluno">Meu cronograma</button><button class="btn" data-student="navigate" data-page="boletim">Notas e projeções</button>${state.me.has_third_year?'<button class="btn" data-student="navigate" data-page="minhatrilha">Trilha ENEM</button>':''}</div></section></div>
    <section class="card student-section">${intro('Plano de estudos sugerido','Distribuição de revisões por tópico a partir das suas evidências e horas disponíveis.','É uma sugestão flexível; altere a disponibilidade e o objetivo na Trilha ENEM.')}${r.study_plan.length?`<div class="grid cols4">${r.study_plan.map(x=>`<div class="student-plan-mini"><span class="pill blue">Semana ${x.week}</span><b>${safe(x.topic)}</b><small>${safe(x.subject)} · ${x.minutes} min</small></div>`).join('')}</div>`:'<p class="muted">Resolva atividades para receber sugestões.</p>'}</section>`;
 }
 function projection(x,i){const pending=x.assessments.filter(a=>a.score===null),known=x.assessments.filter(a=>a.score!==null),weighted=known.reduce((a,b)=>a+b.score*b.weight,0),total=x.assessments.reduce((a,b)=>a+b.weight,0);
   const id=`projection-${i}`;
   return `<details class="grade-projection" data-projection="${id}" data-total="${total}" data-known="${weighted}"><summary>Projetar nota final <span>${pending.length} avaliação(ões) pendente(s)</span></summary>
    <div class="grade-projection-inner"><p class="feature-teaser">Simule resultados para estudar cenários. Isso não altera nenhuma nota registrada.</p>
    ${pending.length?`<div class="formgrid">${pending.map(a=>`<label class="field">${safe(a.name)} · peso ${fmt(a.weight)}<input type="number" class="projection-input" min="0" max="10" step="0.5" data-weight="${a.weight}" placeholder="Nota estimada"></label>`).join('')}</div>`:'<p class="muted">Todas as avaliações cadastradas já possuem nota.</p>'}
    <div class="grade-projection-result"><strong>Projeção: <span class="projection-value">${pending.length?'Preencha as notas':fmt(total?weighted/total:null)}</span></strong><small class="projection-interpretation muted">${pending.length?'As notas simuladas só aparecem neste navegador.':'Média das avaliações registradas.'}</small></div>
    <p class="muted small">${x.needed===null?'Sem avaliações pendentes para calcular nota necessária.':`Para média 6,0, seria necessária aproximadamente ${fmt(x.needed)} de média ponderada nas avaliações restantes. ${safe(x.needed_message||'')}`}</p></div></details>`;
 }
 async function grades(){const r=await data();return head('Notas da escola','Boletim individual com uma projeção opcional dentro de cada disciplina.')+
  `<div class="grid cols2">${r.grades.map((x,i)=>`<section class="card student-grade-card">${intro(x.subject+' · '+x.class_name,'Média parcial '+fmt(x.average)+' · '+x.remaining+' avaliação(ões) pendente(s).','A projeção usa pesos de todas as avaliações cadastradas, sem gravar notas simuladas.')}
    <div class="tablewrap"><table><thead><tr><th>Avaliação</th><th>Peso</th><th>Nota</th></tr></thead><tbody>${x.assessments.map(a=>`<tr><td>${safe(a.name)}</td><td>${fmt(a.weight)}</td><td><b>${fmt(a.score)}</b></td></tr>`).join('')}</tbody></table></div>${projection(x,i)}</section>`).join('')||empty('Sem notas','A coordenação ainda não cadastrou avaliações.')}</div>`;}
 async function performance(){const r=await data();return head('Meu desempenho','Mapa individual de evidências por área, disciplina e tópico, com explicações e próximos passos.')+
  `<section class="card student-section">${intro('Médias por áreas de conhecimento','Visão de Exatas, Natureza, Humanas e Linguagens a partir das avaliações disponíveis.','Compare a evolução de um tópico com suas próprias evidências anteriores, nunca com rótulos de aptidão.')}${areas(r)}</section>
   <section class="card student-section">${intro('Meus tópicos para acompanhamento','Cada prioridade informa a razão, a quantidade de evidências e uma atividade inicial.','A ordem pode mudar ao responder novas questões ou receber avaliações. Seu professor pode ajudar a interpretar as dificuldades.')}<div class="learning-topic-grid">${r.topics.map((x,i)=>topicCard(x,i)).join('')||'<p class="muted">Ainda não existem tópicos avaliados.</p>'}</div></section>`;}
 const days=['Seg','Ter','Qua','Qui','Sex','Sáb'];
 const styles={misto:'Teoria e questões',questoes:'Mais questões',guiada:'Revisão guiada'};
 const steps={misto:['Rever e explicar a teoria','Resolver questões do banco','Retomar os erros e anotar dúvidas'],
   questoes:['Resolver questões em tempo curto','Conferir erros e justificar respostas','Variar a dificuldade das questões'],
   guiada:['Rever conceitos com exemplos','Explicar um exemplo em voz alta','Criar um resumo e testar o entendimento']};
 function studyWeek(r){const hours=Math.max(1,Number(r.preferences.hours||4)),blocks=Math.max(1,Math.round(hours*60/50)),topics=r.topics.slice(0,Math.min(5,r.topics.length));if(!topics.length)return '<p class="muted">Ainda não há tópicos acompanhados para distribuir.</p>';
   const selected=days.filter(day=>(r.preferences.study_days||days).includes(day));if(!selected.length)return '<p class="muted">Escolha ao menos um dia para distribuir seus blocos de estudo.</p>';
   const week=selected.map(d=>({day:d,items:[]})),tasks=steps[r.preferences.study_style]||steps.misto;
   for(let i=0;i<blocks;i++){const t=topics[i%topics.length];week[i%week.length].items.push({topic:t.topic,subject:t.subject,task:tasks[Math.floor(i/topics.length)%tasks.length]});}
   return `<div class="study-week-grid">${week.map(d=>`<div class="study-day"><b>${d.day}</b>${d.items.map(x=>`<div><strong>${safe(x.topic)}</strong><small>${safe(x.subject)} · ${safe(x.task)}</small></div>`).join('')||'<span class="muted small">Descanso</span>'}</div>`).join('')}</div>`;
 }
 async function trail(){if(!state.me.has_third_year)return empty('Trilha ENEM somente para a 3ª série','Você pode acompanhar os tópicos em Meu desempenho.');const r=await data();const pref=r.preferences;
   const objectives=r.objectives.map(x=>`<option value="${safe(x)}" ${x===pref.objective?'selected':''}>${safe(x)}</option>`).join('');
   const styleOptions=Object.entries(styles).map(([id,label])=>`<option value="${id}" ${pref.study_style===id?'selected':''}>${safe(label)}</option>`).join('');
   const focusOptions=r.topics.slice(0,12).map(x=>`<label class="student-chip"><input type="checkbox" name="focus_topics" value="${safe(x.topic)}" ${pref.focus_topics.includes(x.topic)?'checked':''}><span>${safe(x.topic)} <small>· ${safe(x.subject)}</small></span></label>`).join('');
   return head('Minha Trilha ENEM','Escolha seu objetivo e sua disponibilidade; o plano se ajusta às evidências e à prática, sem presumir capacidade.')+
    `<section class="card student-section">${intro('Personalize sua trilha','Objetivo opcional, tempo disponível e prioridades explicadas.','O objetivo altera somente a ordem das revisões; nenhuma área é descartada. Você pode mudar suas escolhas quando quiser.')}
      <form id="student-trail-settings" class="student-trail-form"><div class="row student-trail-settings"><label class="field">Objetivo de estudo<select name="objective">${objectives}</select></label><label class="field">Horas por semana<input type="number" name="hours" min="1" max="40" value="${pref.hours}" required></label><label class="field">Prefiro estudar com<select name="study_style">${styleOptions}</select></label></div>
      <div class="student-trail-custom"><div><h3>Quando posso estudar</h3><p class="feature-teaser">A sugestão da semana usa apenas os dias marcados.</p><div class="student-chips">${days.map(day=>`<label class="student-chip"><input type="checkbox" name="study_days" value="${day}" ${(pref.study_days||days).includes(day)?'checked':''}><span>${day}</span></label>`).join('')}</div></div>
       <div><h3>Até três assuntos que eu quero priorizar</h3><p class="feature-teaser">Sua escolha influencia a ordem, mas o histórico de dificuldades continua visível.</p><div class="student-chips">${focusOptions||'<span class="muted small">Ainda sem tópicos analisados.</span>'}</div></div></div>
      <button class="btn primary">Salvar preferências e atualizar trilha</button></form></section>
     <section class="card student-section">${intro('Meu desempenho por área','As médias refletem apenas as disciplinas avaliadas em cada campo.','Uma área sem nota não deve ser entendida como dificuldade. As prioridades abaixo também consideram prática e histórico.')}${areas(r)}</section>
     <div class="grid cols2 student-main-grid"><section class="card">${intro('Estude primeiro','Cada tópico traz a explicação da prioridade e uma maneira de iniciar.','A ordem combina seu objetivo com evidências disponíveis; não é previsão de resultado no ENEM.')}
       <div class="learning-topic-grid single">${r.topics.slice(0,5).map((x,i)=>topicCard(x,i)).join('')||'<p class="muted">Ainda sem tópicos registrados.</p>'}</div></section>
     <section class="card">${intro('Mapa das prioridades','Resumo das observações que alimentam sua trilha.','Mais respostas e avaliações tornam as sugestões melhor fundamentadas, mas nenhuma nota determina sua capacidade.')}
       <div class="student-priority-summary">${['alta','média','baixa'].map(level=>{const found=r.longitudinal.filter(x=>x.priority===level);return `<div><b>${found.length}</b><span>Prioridade ${level}</span>${meter(found.length,Math.max(1,r.longitudinal.length))}</div>`}).join('')}</div>
       ${more('histórico do 9º ano à série atual',`<div class="tablewrap"><table><thead><tr><th>Assunto</th><th>9º</th><th>1ª</th><th>2ª</th><th>Atual</th></tr></thead><tbody>${r.longitudinal.map(x=>`<tr><td>${safe(x.topic)}</td>${['9º ano','1ª série','2ª série','Atual'].map(y=>`<td>${fmt(x.years[y])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`)}</section></div>
     <section class="card student-section">${intro('Minha semana de estudos',pref.hours+' h semanais organizadas em blocos sugeridos de 50 minutos.','Distribuição ilustrativa e ajustável, diferente do cronograma de aulas da escola.')}${studyWeek(r)}</section>
     <section class="card student-section">${intro('Plano de revisão em quatro semanas','Focos e ações conectados às questões respondidas, notas e interesses de estudo.','Metas de questões são pessoais, flexíveis e não são critério de qualidade ou comparação entre estudantes.')}
       <div class="grid cols2">${r.study_plan.map(x=>`<article class="student-plan"><div class="row spread"><b>Semana ${x.week} · ${safe(x.topic)}</b>${pill(x.minutes+' min','blue')}</div><p class="muted small">${safe(x.subject)} · ${safe(x.task)}</p><p class="small">Por quê: ${safe(x.reason)}</p></article>`).join('')||'<p class="muted">Sem evidências para gerar um plano.</p>'}</div>
       <h3 style="margin-top:24px">Metas de prática que posso ajustar</h3><div class="grid cols2">${r.topics.slice(0,6).map(x=>`<form class="pg-goal row student-goal" data-topic="${safe(x.topic)}"><span class="flex"><b>${safe(x.topic)}</b><small class="muted">${x.answers} respostas registradas no histórico</small></span><label class="field">Questões por semana<input name="target" type="number" min="1" max="200" value="${x.goal}" required></label><button class="btn sm">Salvar</button></form>`).join('')}</div></section>`;
 }
 function chips(items,name,selected){return `<div class="student-chips">${items.map(x=>`<label class="student-chip"><input type="checkbox" name="${name}" value="${safe(x)}" ${selected.includes(x)?'checked':''}><span>${safe(x)}</span></label>`).join('')}</div>`;}
 async function vocation(){const r=await api('/student/vocational?school='+encodeURIComponent(school()));const p=r.profile;
    const course=(x)=>`<article class="student-career"><div class="row spread"><h3>${safe(x.name)}</h3>${x.feedback?pill(({sim:'Interessante',mais:'Conhecer melhor',nao:'Não me interessa'})[x.feedback]||'','blue'):''}</div>
      <p class="feature-teaser">${safe(x.reasons.slice(0,2).join(' · '))}</p><div class="career-weights"><span>Gostos ${x.taste_score}% ${meter(x.taste_score,100)}</span><span>Evidência de notas ${x.performance_score}% ${meter(x.performance_score,100)}</span></div>
      ${more('o curso e sua preparação',`<p><b>Na graduação:</b> ${safe(x.graduation)}</p><p><b>Caminhos profissionais:</b> ${safe(x.work)}</p><p><b>Preparação:</b> ${x.preparation.map(y=>safe(y.topic)+' ('+safe(y.subject)+')').join(', ')||'Explorar disciplinas relacionadas e conversar com profissionais.'}</p><p>Confira informações oficiais das instituições de ensino; isto não constitui indicação de profissão.</p>`)}
      <div class="row career-feedback"><button class="btn sm" data-student="career-choice" data-course="${safe(x.id)}" data-choice="sim">Interessante</button><button class="btn sm" data-student="career-choice" data-course="${safe(x.id)}" data-choice="mais">Conhecer melhor</button><button class="btn sm" data-student="career-choice" data-course="${safe(x.id)}" data-choice="${x.feedback==='nao'?'':'nao'}">${x.feedback==='nao'?'Desfazer':'Não me interessa'}</button></div></article>`;
    return head('Vocação','Explore seus interesses e carreiras possíveis. Você pode mudar suas escolhas a qualquer momento.')+
     `<div class="hint warn">As notas não determinam vocação, inteligência ou sucesso futuro. As opções servem para exploração, como no HTML original.</div>
      <section class="card student-section">${intro('Meus gostos','Matérias, atividades, valores e ambientes que despertam sua curiosidade.','O sistema só sugere caminhos para pesquisar. Você decide o que deseja experimentar.')}
       <form id="student-vocation-form" class="stack"><div><h3>Matérias de que gosto</h3>${chips(r.subjects,'subjects',p.subjects)}</div><div><h3>O que desperta minha curiosidade</h3>${chips(r.activities,'activities',p.activities)}</div>
       <div><h3>O que valorizo no trabalho</h3>${chips(r.values,'values',p.values)}</div><div><h3>Onde me imagino trabalhando</h3>${chips(r.environments,'environments',p.environments)}</div>
       <div class="formgrid"><label class="field">Um problema que gostaria de ajudar a resolver<input name="problem" maxlength="400" value="${safe(p.problem)}" placeholder="Ex.: melhorar a mobilidade da minha cidade"></label><label class="field">Peso das notas nas sugestões: <b id="career-weight-label">${p.performance_weight}%</b><input type="range" name="performance_weight" min="0" max="100" step="10" value="${p.performance_weight}"><small class="muted">0%: só interesses · 100%: só evidências de desempenho</small></label></div><button class="btn primary">Salvar meus gostos</button></form></section>
      <section class="card student-section">${intro('Carreiras para explorar','Sugestões ordenadas por suas escolhas, com explicação da relação proposta.','A porcentagem, quando houver, é somente um índice interno de exploração, não uma probabilidade de êxito.')}
        <div class="learning-career-grid">${r.courses.filter(x=>x.feedback!=='nao').slice(0,7).map(course).join('')}</div>${r.courses.some(x=>x.feedback==='nao')?more('opções que deixei de lado',r.courses.filter(x=>x.feedback==='nao').map(course).join('')):''}</section>
      <section class="card student-section">${intro('Estudos ligados às carreiras marcadas','Exemplos de tópicos que você pode revisitar, se fizer sentido para seus interesses.','Marque uma carreira como Interessante ou Conhecer melhor para ver os estudos relacionados.')}
        <div class="grid cols2">${r.study_topics.map(x=>`<div class="student-plan"><b>${safe(x.topic)}</b><small class="muted">${safe(x.subject)} · ${safe(x.career)}</small><p class="small">${safe((x.reasons||[]).slice(0,2).join('; '))}</p><button class="btn sm" data-student="study-topic" data-topic="${safe(x.topic)}">Praticar assunto</button></div>`).join('')||'<p class="muted">Escolha alguma carreira acima para conectar interesses e estudos.</p>'}</div></section>`;
 }
 function bind(root){root.addEventListener('submit',async ev=>{
    const form=ev.target;if(!['student-trail-settings','student-vocation-form'].includes(form.id))return;
    ev.preventDefault();const fd=new FormData(form);
    try{let payload={school_id:school()};if(form.id==='student-trail-settings'){
      payload={...payload,objective:fd.get('objective'),hours:Number(fd.get('hours')),
        study_style:fd.get('study_style'),study_days:fd.getAll('study_days'),focus_topics:fd.getAll('focus_topics')};
      if(!payload.study_days.length)throw Error('Selecione ao menos um dia para sua semana de estudo.');
      if(payload.focus_topics.length>3)throw Error('Selecione no máximo três assuntos prioritários.');
    }else{
      payload={...payload,subjects:fd.getAll('subjects'),activities:fd.getAll('activities'),values:fd.getAll('values'),
        environments:fd.getAll('environments'),problem:fd.get('problem')||'',performance_weight:Number(fd.get('performance_weight'))};
    }await api('/student/preferences',payload);alertUser('Suas preferências foram salvas.');await renderPage();
    }catch(err){alertUser(err.message,false);}
  });
  root.addEventListener('input',ev=>{
    if(ev.target.name==='performance_weight'){const label=document.getElementById('career-weight-label');if(label)label.textContent=ev.target.value+'%';}
    if(!ev.target.classList.contains('projection-input'))return;
    const container=ev.target.closest('.grade-projection');if(!container)return;
    const inputs=[...container.querySelectorAll('.projection-input')],allFilled=inputs.every(x=>x.value!==''&&!Number.isNaN(Number(x.value))&&Number(x.value)>=0&&Number(x.value)<=10);
    const value=container.querySelector('.projection-value'),message=container.querySelector('.projection-interpretation');
    if(!allFilled){value.textContent='Preencha as notas';message.textContent='Nenhum valor foi alterado no boletim.';return;}
    const total=Number(container.dataset.total),known=Number(container.dataset.known);
    const simulated=(known+inputs.reduce((s,x)=>s+Number(x.value)*Number(x.dataset.weight),0))/total;
    value.textContent=fmt(simulated);message.textContent='Cenário hipotético · '+(simulated>=6?'média igual ou superior a 6,0':'média abaixo de 6,0');
  });
  root.addEventListener('click',async ev=>{
    const button=ev.target.closest('[data-student]');if(!button)return;
    try{if(button.dataset.student==='navigate'){state.page=button.dataset.page;await drawApp();return;}
      if(button.dataset.student==='study-topic'){state.page='praticar';state.studyTopic=button.dataset.topic;await drawApp();return;}
      if(button.dataset.student==='career-choice'){
        button.disabled=true;try{await api('/student/vocational/feedback',{
          school_id:school(),course_id:button.dataset.course,choice:button.dataset.choice});await renderPage();}
        finally{button.disabled=false;}
      }
    }catch(err){alertUser(err.message,false);}
  });
 }
 return {home,grades,performance,trail,vocation,bind};
}
