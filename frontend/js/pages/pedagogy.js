import {stats, histogram, evolution, boxplots, heatColor} from './analytics.js';
import {createLearningInsights} from './learning_insights.js';
import {createStudentExperience} from './student_experience.js';
/* Cognix · telas pedagógicas do HTML original adaptadas ao SQLite.
   Todo dado individual vem da API com autorização no servidor. */
export function createPedagogy({state,api,e,head,pill,empty,role,alertUser,drawApp,renderPage}){
 const st={context:'',student:'',week:false,lessonAssistant:null};
 const insights=createLearningInsights({state,api,e,head,pill,empty,role,alertUser,renderPage});
 const fmt=(n,d=1)=>n===undefined||n===null||Number.isNaN(Number(n))?'—':Number(n).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
 const school=()=>state.school==='todas'?state.me.schools[0]?.id:state.school;
 const studentExperience=createStudentExperience({state,api,e,head,pill,empty,alertUser,renderPage,drawApp,school});
 const qs=o=>new URLSearchParams(Object.entries(o).filter(([,v])=>v!==''&&v!=null)).toString();
 const C=(id,s)=>({id,subject:s});
 const classKey=o=>`${o.id}|${o.subject}`;
 const text=(t)=>e(String(t??''));
 const note=(t)=>`<p class="muted small">${text(t)}</p>`;
 const metric=(name,val,subtitle='',color='#6678c5')=>`<div class="card kpi" style="--kc:${color}"><div class="label">${text(name)}</div><div class="num">${text(val)}</div><small>${text(subtitle)}</small></div>`;
 const warn=()=>`<div class="hint warn">Atenção: indicadores demonstrativos são calculados sobre dados fictícios. Não constituem diagnóstico individual definitivo.</div>`;
 async function combos(){const classes=await api('/classes?'+qs({school:state.school==='todas'?'':state.school}));const out=[];
   for(const c of classes)for(const sub of c.subjects||[])out.push({...c,subject:sub});return out;}
 function picker(list,chosen,compact=false){return `<form id="pg-context" class="row ${compact?'compact-filter':'filter-row'}" style="align-items:end"> <label class="field flex">Turma e disciplina<select name="context">${list.map(x=>`<option value="${text(classKey(x))}" ${classKey(x)===chosen?'selected':''}>${list.length>1&&state.me.schools.length>1?text(x.school_name)+' · ':''}${text(x.name)} · ${text(x.subject)}</option>`).join('')}</select></label><button class="btn ${compact?'':'primary'}">Aplicar</button></form>`;}
 async function selectContext(compact=false,thirdOnly=false){const list=(await combos()).filter(x=>!thirdOnly||x.grade?.startsWith('3ª'));if(!list.length)return {list,selected:null,header:empty(thirdOnly?'Trilha ENEM exclusiva da 3ª série':'Sem turmas vinculadas',thirdOnly?'Não há atribuição na terceira série para esta conta.':'Solicite à coordenação o vínculo ou matrícula.')};
   let x=list.find(y=>classKey(y)===st.context)||list[0];st.context=classKey(x);return {list,selected:x,header:picker(list,st.context,compact)};}
 const miniBar=(n)=>`<div class="resultbar"><span style="width:${Math.max(0,Math.min(100,Number(n||0)*10))}%"></span></div>`;
 const table=(headers,body)=>`<div class="tablewrap"><table><thead><tr>${headers.map(h=>`<th>${text(h)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
 async function institution(){if(role()!=='coord')return empty('Acesso restrito','Somente coordenação.');const id=school();if(!id)return empty('Sem escola','Associe uma instituição à coordenação.');
  const r=await api('/pedagogy/institution?'+qs({school:id}));const subjects=r.subjects||[];
  const total=subjects.reduce((a,x)=>a+x.student_count,0),success=subjects.filter(x=>x.approved_pct!==null);
  const critical=subjects.reduce((a,x)=>a+(x.critical||0),0);const falls=subjects.reduce((a,x)=>a+x.falls,0);
  const threshold=subjects[0]?.school_threshold;
  const byClass=[...new Set(subjects.map(x=>x.class_name))];const disciplines=[...new Set(subjects.map(x=>x.subject))];
  const grouped=byClass.map(name=>({name,items:subjects.filter(x=>x.class_name===name)}));
  return head('Visão institucional','A mesma visão por turmas, disciplinas, professores e alertas do protótipo, limitada à sua escola.')+
  `<div class="grid cols4">${metric('Alunos acompanhados',r.enrollments,'Matrículas distintas')}${metric('Aprovação parcial',success.length?fmt(success.reduce((a,b)=>a+b.approved_pct,0)/success.length,0)+'%':'—','Média das turmas-disciplina','#4c9690')}${metric('Alertas de queda',falls,'Redução ≥ 2,5 pontos','#d47790')}${metric('Tópicos críticos',critical,'Média abaixo de '+fmt(threshold),'#d19e58')}</div>
  <section class="card" style="margin-top:20px"><h2>Visão geral por série e área</h2><p class="muted small">Médias parciais por disciplina. A escola ativa é a única incluída nestes indicadores.</p>
    ${table(['Turma',...disciplines,'Média geral'],grouped.map(g=>{const observed=g.items.filter(x=>x.average!==null);return `<tr><td><b>${text(g.name)}</b></td>${disciplines.map(sub=>{const r=g.items.find(x=>x.subject===sub);return `<td class="grade-heat" style="${heatColor(r?.average)}">${fmt(r?.average)}</td>`}).join('')}<td><b>${fmt(observed.length?observed.reduce((n,x)=>n+x.average,0)/observed.length:null)}</b></td></tr>`}).join(''))}</section>
  <div class="grid cols2" style="margin-top:20px"><section class="card"><h2>Áreas e disciplinas</h2><p class="muted small">Todas as turmas com seu docente responsável e aprovação parcial.</p>
    ${table(['Turma / disciplina','Professor(a)','Média','Aprovação'],subjects.map(x=>`<tr><td><b>${text(x.class_name)}</b><br><span class="muted small">${text(x.subject)}</span></td><td>${text(x.teacher_name)}</td><td class="grade-heat" style="${heatColor(x.average)}">${fmt(x.average)}</td><td>${x.approved_pct===null?'—':fmt(x.approved_pct,0)+'%'}</td></tr>`).join(''))}</section>
  <section class="card"><h2>Professores e acompanhamento</h2>${table(['Professor(a)','Disciplinas','Turmas','Quedas'],[...new Set(subjects.map(x=>x.teacher_name))].map(n=>{const t=subjects.filter(x=>x.teacher_name===n);return `<tr><td>${text(n)}</td><td class="wrap">${text([...new Set(t.map(x=>x.subject))].join(', '))}</td><td>${t.length}</td><td>${t.reduce((a,x)=>a+x.falls,0)}</td></tr>`}).join(''))}
  <h3 style="margin-top:22px">Alunos para acompanhamento</h3><p class="muted small">Queda recente ou média abaixo do critério da escola (${fmt(threshold)}).</p>${(r.students_to_follow||[]).slice(0,12).map(x=>`<div class="listline"><span class="pill red">${x.drop>=2.5?'↓ '+fmt(x.drop):'Apoio'}</span><div class="flex"><b>${text(x.student_name)}</b><div class="muted small">${text(x.class_name)} · ${text(x.subject)} · média ${fmt(x.average)}</div></div></div>`).join('')||note('Nenhum estudante classificado como prioridade nesta escola.')}</section></div>`;
 }
 async function teacherPanel(){const id=state.school==='todas'?'':state.school;
  const [alerts,lessons]=await Promise.all([api('/pedagogy/attention?'+qs({school:id})),api('/pedagogy/schedule?'+qs({school:id}))]);
  const list=alerts.classes||[],unique=new Set(list.map(x=>x.school_id+'|'+x.class_id));
  const topics=alerts.critical_topics||[],students=alerts.students_to_follow||[];
  const needSchool=state.me.user.account_plan==='individual'&&state.me.schools.length>1;
  const scope=x=>`${text(x.subject)} · ${text(x.class_name)}${needSchool?' · '+text(state.me.schools.find(s=>s.id===x.school_id)?.name||''):''}`;
  return head('Seu painel','Os assuntos críticos e os estudantes que precisam de acompanhamento aparecem primeiro. Abra o diagnóstico apenas para aprofundar.')+
   `<section class="priority-board"><div class="row spread"><div><span class="eyebrow">Prioridades pedagógicas</span><h2>Precisa da sua atenção</h2><p class="muted small">Alertas calculados com notas, evolução e atividades registradas, não com previsões.</p></div><button class="btn sm" data-action="nav" data-page="analise">Investigar os dados →</button></div>
   <div class="grid cols2 attention-grid">
   <article class="attention-card critical"><div class="row spread"><h3>Assuntos críticos</h3>${pill(topics.length+' tópico(s)','amber')}</div>
     ${topics.slice(0,5).map(x=>`<button class="attention-item" data-pg="focus-diagnostic" data-context="${text(classKey({id:x.class_id,subject:x.subject}))}" data-topic="${text(x.subject+'::'+x.topic)}"><span class="attention-icon">!</span><span class="flex"><strong>${text(x.topic)}</strong><small>${scope(x)} · ${text(x.reason||'Atenção aos resultados recorrentes')}</small></span><b class="attention-score">${fmt(x.mean)}</b></button>`).join('')||note('Sem dificuldades persistentes detectadas nos registros disponíveis.')}</article>
   <article class="attention-card falling"><div class="row spread"><h3>Alunos em queda ou risco</h3>${pill(students.length+' acompanhamento(s)','red')}</div>
     ${students.slice(0,6).map(x=>`<button class="attention-item" data-pg="focus-diagnostic" data-context="${text(classKey({id:x.class_id,subject:x.subject}))}"><span class="attention-icon">↓</span><span class="flex"><strong>${text(x.student_name)}</strong><small>${scope(x)} · ${x.drop>=2.5?'Queda de '+fmt(x.drop)+' ponto(s)':'Média abaixo do mínimo'}</small></span><b class="attention-score">${fmt(x.average)}</b></button>`).join('')||note('Nenhum aluno em queda ou abaixo do mínimo nesta seleção.')}</article></div>
   </section>
   <div class="grid cols4" style="margin-top:18px">${metric('Turmas',unique.size,'Atribuições ativas')}${metric('Acima do mínimo',list.some(x=>x.mean!==null)?fmt(list.filter(x=>x.mean!==null&&x.mean>=x.threshold).length/list.filter(x=>x.mean!==null).length*100,0)+'%':'—','Turmas-disciplina avaliadas','#4c9690')}${metric('Alunos em atenção',alerts.unique_students_to_follow,'Pessoas distintas com queda ou média baixa','#d47790')}${metric('Tópicos críticos',topics.length,'Média abaixo do mínimo','#d19e58')}</div>
   <div class="grid cols2" style="margin-top:18px"><section class="card"><div class="row spread"><h2>Próximas aulas</h2><button class="btn sm" data-action="nav" data-page="agenda">Minha semana →</button></div>
     ${lessons.filter(x=>x.status==='planejada').slice(0,6).map(x=>`<div class="listline"><span class="pill blue">${['Seg','Ter','Qua','Qui','Sex'][x.weekday]||'Dia'} · ${Number(x.slot)+1}ª</span><div class="flex"><b>${text(x.topic)}</b><p class="muted small">${text(x.class_name)} · ${text(x.subject)}</p></div><button class="btn sm" data-pg="prepare-lesson" data-id="${text(x.id)}">Preparar revisão</button></div>`).join('')||note('Sem aulas planejadas.')}</section>
     <section class="card"><h2>Duas áreas complementares</h2><div class="listline"><b>Notas da turma</b><span class="muted small">Registros de avaliações e médias por estudante.</span></div><div class="listline"><b>Desempenho e diagnóstico</b><span class="muted small">Evolução, estatísticas, padrões por tópico e revisões, sem repetir telas.</span></div><button class="btn sm" data-action="nav" data-page="analise">Abrir análise completa</button></section></div>
   <div id="teacher-prep" class="teacher-prep-area"></div><details class="card advanced-details" style="margin-top:18px"><summary>Resumo de todas as turmas <span>Indicadores consolidados</span></summary><div class="advanced-body">${table(['Turma','Disciplina','Alunos','Média','Tópicos críticos','Alunos em atenção'],list.map(x=>`<tr><td>${text(x.class_name)}</td><td>${text(x.subject)}</td><td>${x.students}</td><td style="${heatColor(x.mean)}">${fmt(x.mean)}</td><td>${x.critical_topics}</td><td>${x.students_to_follow}</td></tr>`).join('')||'<tr><td colspan="6">Nenhuma turma atribuída.</td></tr>')}</div></details>`;
 }
 async function agenda(){const id=state.school==='todas'?'':state.school;const [data,contexts]=await Promise.all([
    api('/pedagogy/schedule?'+qs({school:id})),role()==='prof'?combos():Promise.resolve([])]);
  const names=['Segunda','Terça','Quarta','Quinta','Sexta'];st.lessons=data;
  const showSchool=state.me.schools.length>1;
  const slots=[...new Set(data.map(x=>x.slot))].sort((a,b)=>a-b);
  const cell=(day,slot)=>data.filter(a=>a.weekday===day&&a.slot===slot).map(a=>`<button type="button" class="lesson-card ${text(a.status)}" data-pg="edit-lesson" data-id="${text(a.id)}"><b>${text(a.subject)}</b><span>${text(a.class_name)}</span><small>${showSchool?text(a.school_name)+' · ':''}${text(a.room)}</small><small>${text(a.topic)}</small>${a.status!=='planejada'?`<em>${text(a.status)}</em>`:''}</button>`).join('')||'<span class="quiet">—</span>';
  return head(role()==='coord'?'Cronogramas':'Minha semana',role()==='coord'?'Grade semanal e registro de aulas da sua instituição.':'Horários, conteúdos e registros da sua semana, como no HTML original.')+
    `<section class="card nopad"><div class="cardhead row spread"><div><h2>Grade semanal</h2><p>Selecione uma aula para consultar ou alterar o planejamento permitido para seu perfil.</p></div>${pill(data.length+' aulas','blue')}</div>
    <div class="tablewrap"><table class="weekly"><thead><tr><th>Horário</th>${names.map(d=>`<th>${d}</th>`).join('')}</tr></thead><tbody>
    ${slots.map(sl=>`<tr><th>${Number(sl)+1}ª aula</th>${names.map((_,d)=>`<td>${cell(d,sl)}</td>`).join('')}</tr>`).join('')||'<tr><td colspan="6">Nenhuma aula na semana.</td></tr>'}</tbody></table></div></section>
    <div id="pg-lesson-panel"></div>
    ${role()==='prof'&&contexts.length?`<details class="card lesson-create-panel" style="margin-top:18px"><summary>Adicionar atividade à minha semana <span>Criar aula e salvar no cronograma da turma</span></summary><div class="advanced-body"><form id="pg-new-lesson" class="stack"><label class="field">Turma e disciplina<select name="combo">${contexts.map((x,i)=>`<option value="${i}">${text(x.name)} · ${text(x.subject)}${showSchool?' · '+text(x.school_name):''}</option>`).join('')}</select></label><div class="formgrid"><label class="field">Dia<select name="weekday">${names.map((d,i)=>`<option value="${i}">${d}</option>`).join('')}</select></label><label class="field">Horário (nº da aula)<input type="number" name="slot" min="1" max="16" value="1" required></label><label class="field">Sala<input name="room" maxlength="80" placeholder="Opcional"></label><label class="field">Tópico<input name="topic" maxlength="120" minlength="2" required placeholder="O que será estudado"></label></div><label class="field">Plano da atividade<textarea name="plan" rows="3" maxlength="3000" placeholder="Atividade, recursos e abordagem para a aula"></textarea></label><label class="field">Situação<select name="status"><option value="planejada">Planejada</option><option value="dada">Realizada</option><option value="cancelada">Cancelada</option></select></label><label class="field">Observações privadas do professor<textarea name="notes" rows="2" maxlength="3000"></textarea></label><button class="btn primary">Salvar nova atividade</button></form><script id="pg-new-lesson-combos" type="application/json">${JSON.stringify(contexts.map(x=>({id:x.id,subject:x.subject}))).replace(/</g,'\\u003c')}</script></div></details>`:''}
    <section class="card" style="margin-top:18px"><h2>Resumo das aulas por turma</h2>${table(['Turma','Disciplina',...(showSchool?['Escola']:[]),'Planejadas','Dadas','Canceladas'],[...new Set(data.map(x=>x.class_id+'|'+x.subject))].map(key=>{const t=data.filter(x=>x.class_id+'|'+x.subject===key),a=t[0];return `<tr><td>${text(a.class_name)}</td><td>${text(a.subject)}</td>${showSchool?'<td>'+text(a.school_name)+'</td>':''}<td>${t.length}</td><td>${t.filter(x=>x.status==='dada').length}</td><td>${t.filter(x=>x.status==='cancelada').length}</td></tr>`}).join(''))}</section>`;
 }
 async function gradeBook(){if(role()==='aluno')return studentGrades();const {selected,header}=await selectContext();if(!selected)return head('Notas da turma','')+header;
  const d=await api('/pedagogy/matrix?'+qs({class_id:selected.id,subject:selected.subject}));const assessments=d.assessments;
  const threshold=d.school_threshold,recovery=d.school_recovery;
  const status=m=>m===null?'Sem notas':m>=threshold?'Acima do mínimo':m>=recovery?'Recuperação':'Em risco';
  const gradeCells=d.students.map((student,i)=>`<tr><td class="muted small">${String(i+1).padStart(2,'0')}</td><td><b>${text(student.name)}</b></td>
    ${assessments.map(a=>{const value=student.grades[a.name];return `<td class="num-cell" style="${heatColor(value)}">${fmt(value)}</td>`}).join('')}
    <td class="num-cell" style="${heatColor(student.average)}"><b>${fmt(student.average)}</b></td><td>${pill(status(student.average),student.average===null?'blue':student.average>=threshold?'teal':student.average>=recovery?'amber':'red')}</td></tr>`).join('');
  const averages=assessments.map(a=>{const vals=d.students.map(x=>x.grades[a.name]).filter(x=>x!==null);return vals.length?vals.reduce((x,y)=>x+y,0)/vals.length:null});
  return head(role()==='coord'?'Lançar notas':'Notas da turma',role()==='coord'?'As alterações ficam registradas e alimentam os indicadores e a trilha do aluno.':'A mesma grade do HTML original em modo de leitura; só a coordenação edita.')+header+
  `<div class="hint ${role()==='coord'?'good':''}" style="margin:14px 0">${role()==='coord'?'Lançamento e correção de notas exclusivos da coordenação da escola.':'As notas são lançadas pela coordenação; professores acompanham os resultados.'}</div>
  <section class="card nopad"><div class="cardhead"><h2>${text(selected.name)} · ${text(selected.subject)}</h2><p>${d.students.length} alunos · ${assessments.length} avaliações · média parcial da turma ${fmt(d.stats.mean)}</p></div>
   <div class="tablewrap gradebook-scroll"><table class="gradebook"><thead><tr><th>#</th><th>Aluno</th>${assessments.map(a=>`<th title="Tópicos: ${text(a.topics.join(', '))}">${text(a.name)}<small>${text(a.scheduled_on||'')} · peso ${fmt(a.weight,0)}</small></th>`).join('')}<th>Média</th><th>Situação</th></tr></thead>
   <tbody>${gradeCells}<tr class="totals"><td></td><td>Média da avaliação</td>${averages.map(x=>`<td class="num-cell">${fmt(x)}</td>`).join('')}<td class="num-cell"><b>${fmt(d.stats.mean)}</b></td><td></td></tr></tbody></table></div></section>
  ${role()==='coord'?`<div class="grid cols2" style="margin-top:20px"><section class="card"><h2>Lançar ou corrigir nota</h2><form id="pg-grade" class="stack" style="margin-top:12px">
    <input type="hidden" name="class_id" value="${text(selected.id)}"><input type="hidden" name="subject" value="${text(selected.subject)}">
    <label class="field">Aluno<select name="student_id">${d.students.map(x=>`<option value="${text(x.id)}">${text(x.name)}</option>`).join('')}</select></label>
    <label class="field">Avaliação<select name="assessment">${assessments.map(a=>`<option value="${text(a.name)}" data-topics="${text(JSON.stringify(a.topics||[]))}">${text(a.name)}</option>`).join('')}</select></label>
    <label class="field">Nota (de 0 a 10)<input type="number" name="score" min="0" max="10" step="0.1" required></label><div id="pg-topic-breakdown" class="topic-breakdown">${(assessments[0]?.topics||[]).length>1?`<p class="muted small">Notas por tópico (opcionais; não inferidas da nota total).</p>${assessments[0].topics.map(t=>`<label class="field">${text(t)}<input name="topic__${text(t)}" type="number" min="0" max="10" step="0.1" placeholder="Sem evidência específica"></label>`).join('')}`:''}</div><button class="btn primary">Salvar nota</button></form></section>
    <section class="card"><h2>Nova avaliação</h2><p class="muted small">Como no HTML original, cadastre um tipo e os tópicos trabalhados para receber análises por conteúdo.</p><form id="pg-assessment" class="stack">
    <input type="hidden" name="class_id" value="${text(selected.id)}"><input type="hidden" name="subject" value="${text(selected.subject)}">
    <label class="field">Nome<input name="name" placeholder="Ex.: Prova 4" required minlength="2"></label>
    <div class="formgrid"><label class="field">Peso<input name="weight" type="number" min="0.5" max="100" step="0.5" value="3" required></label><label class="field">Data<input name="scheduled_on" type="date"></label></div>
    <label class="field">Tópicos separados por vírgula<input name="topics" placeholder="Ex.: Funções, Estatística"></label><button class="btn">Cadastrar avaliação</button></form></section></div>`:''}
  <p class="muted small" style="margin-top:12px">Critérios configurados nesta escola: média mínima ${fmt(threshold)} e recuperação a partir de ${fmt(recovery)}. A média parcial não substitui a avaliação final.</p>`;
 }
 async function desempenho(){if(role()==='aluno')return studentPerformance();const {selected,header}=await selectContext();if(!selected)return head('Desempenho','')+header;
  const d=await api('/pedagogy/matrix?'+qs({class_id:selected.id,subject:selected.subject}));const s=d.stats;
  const valid=d.students.map(x=>x.average).filter(x=>x!==null);const approved=valid.filter(v=>v>=6).length;
  const first=d.evolution.find(x=>x.stats.mean!==null),last=[...d.evolution].reverse().find(x=>x.stats.mean!==null),trend=first&&last&&first!==last?last.stats.mean-first.stats.mean:null;
  const adv=[['Quantidade de notas',s.n],['Média',s.mean],['Mediana',s.median],['Moda (arred. a 0,5)',s.mode],['Desvio médio',s.dm],['Desvio padrão amostral',s.sd],['Variância amostral',s.variance],['Coeficiente de variação',s.cv],['Q1',s.q1],['Q3',s.q3],['Amplitude',s.amplitude],['Assimetria',s.skew]];
  const ordered=d.topics.slice().sort((a,b)=>(a.stats.mean??99)-(b.stats.mean??99));
  const allGrades=d.assessments.map(a=>({assessment:a.name,stats:stats(d.students.map(x=>x.grades[a.name]))}));
  return head('Desempenho','Medidas de dispersão, evolução, distribuição e análise por tópico da turma.')+header+
   `<div class="grid cols4" style="margin-top:18px">${metric('Média da turma',fmt(s.mean),'Média parcial ponderada')}${metric('Acima do mínimo',valid.length?fmt(approved/valid.length*100,0)+'%':'—',`${approved} de ${valid.length} com média ≥ 6,0`,'#4c9690')}${metric('Dispersão',fmt(s.dm)+' pt','Desvio médio absoluto','#d19e58')}${metric('Tendência',trend===null?'—':(trend>0?'+':'')+fmt(trend),'Última menos primeira avaliação','#d47790')}</div>
   <div class="grid cols2" style="margin-top:18px"><section class="card"><h2>Evolução ao longo do bimestre</h2>${evolution(d.evolution)}</section>
    <section class="card"><h2>Tópicos que exigem atenção</h2><p class="muted small">Os conteúdos com médias mais baixas.</p>${ordered.slice(0,5).map(x=>`<div class="stat-row"><b>${text(x.topic)}</b><span>${fmt(x.stats.mean)} · ${fmt(x.pct_below,0)}% abaixo</span>${miniBar(x.stats.mean)}</div>`).join('')||note('Nenhum tópico analisado.')}</section></div>
   <details class="card advanced-details" style="margin-top:18px"><summary>Análise avançada <span>Estatísticas, gráficos e comparação entre avaliações</span></summary>
   <div class="advanced-body"><p class="muted small">Todos os valores abaixo são calculados com as notas registradas nesta turma e disciplina, conforme o protótipo original.</p>
    <div class="grid cols2"><section class="subcard"><h3>Distribuição das notas</h3>${histogram(valid)}</section>
    <section class="subcard"><h3>Medidas descritivas</h3>${table(['Indicador','Valor'],adv.map(([label,v])=>`<tr><td>${text(label)}</td><td>${fmt(v,2)}${label==='Coeficiente de variação'&&v!==null?'%':''}</td></tr>`).join(''))}</section>
    <section class="subcard"><h3>Boxplot por avaliação</h3>${boxplots(allGrades)}</section>
    <section class="subcard"><h3>Comparar avaliações</h3>${table(['Avaliação','Média','Mediana','Desvio padrão'],d.evolution.map(x=>`<tr><td>${text(x.assessment)}</td><td>${fmt(x.stats.mean)}</td><td>${fmt(x.stats.median)}</td><td>${fmt(x.stats.sd)}</td></tr>`).join(''))}</section></div>
    <h3>Escore z e dispersão por aluno</h3>${table(['Aluno','Média','Diferença da turma','Escore z'],d.students.map(x=>{const v=x.average;return `<tr><td>${text(x.name)}</td><td>${fmt(v)}</td><td>${v===null||s.mean===null?'—':fmt(v-s.mean,2)}</td><td>${v===null||s.sd===null||!s.sd?'—':fmt((v-s.mean)/s.sd,2)}</td></tr>`}).join(''))}
    <div class="hint" style="margin-top:15px">Desvio padrão mostra a dispersão das notas; coeficiente de variação permite comparar turmas com médias diferentes. Indicadores estatísticos não substituem avaliação pedagógica.</div>
   </div></details>`;
 }
 async function diagnostico(){const {selected,header}=await selectContext();if(!selected)return head('Diagnóstico por tópico','')+header;
  const [d,obs]=await Promise.all([api('/pedagogy/analysis?'+qs({class_id:selected.id,subject:selected.subject})),
                                  api('/pedagogy/observations?'+qs({class_id:selected.id,subject:selected.subject}))]);const topics=d.topics||[];
  const order=[...d.topic_heatmap].sort((a,b)=>{const x=d.students.find(s=>s.id===a.student_id)?.average,y=d.students.find(s=>s.id===b.student_id)?.average;return (x??99)-(y??99)});
  return head('Diagnóstico pedagógico','Investigue padrões por conteúdo, estudantes que precisam de apoio e revise o plano da semana.')+header+
  `<section class="card ai-diagnostic-card" style="margin-top:16px"><div class="row spread"><div><span class="eyebrow">Análise assistida</span><h2>Diagnóstico com IA e sugestões de revisão</h2><p class="muted small">Analisa médias, quedas, prática e tópicos de provas, cruzando as prioridades com o cronograma semanal. Dados enviados à IA são agregados e sem nomes de alunos.</p></div><button class="btn primary" data-pg="run-ai-diagnosis" data-school="${text(selected.school_id)}" data-class="${text(selected.id)}" data-subject="${text(selected.subject)}">Executar análise com IA</button></div>
   <div id="pg-ai-result" class="hint" style="margin-top:12px">Nenhum diagnóstico com IA foi executado nesta sessão. O resumo estatístico abaixo é calculado diretamente do banco de notas.</div></section>
  <div class="hint" style="margin:15px 0">${d.recommendations.map(r=>`<p style="margin:4px 0">${text(r)}</p>`).join('')}</div>
   <div class="grid cols2"><section class="card span2"><h2>Resumo por tópico</h2>${table(['Tópico','Média','DP','Desvio médio','Abaixo do mínimo','Tendência'],topics.map(t=>`<tr><td><b>${text(t.topic)}</b></td><td style="${heatColor(t.stats.mean)}">${fmt(t.stats.mean)}</td><td>${fmt(t.stats.sd)}</td><td>${fmt(t.stats.dm)}</td><td>${fmt(t.pct_below,0)}%</td><td>${t.trend===null?'—':(t.trend>0?'+':'')+fmt(t.trend)}</td></tr>`).join(''))}</section>
   <section class="card"><h2>Próximas aulas desta turma</h2><p class="muted small">Sugestões automáticas cruzando planejamento e desempenho.</p>${d.schedule.map(x=>`<div class="listline"><div class="flex"><b>${text(x.topic)}</b><p class="muted small">${text(x.suggestion)}</p>${x.notes?`<p class="muted small">Anotação: ${text(x.notes)}</p>`:''}</div>${pill(x.status,x.status==='dada'?'teal':'blue')}</div>`).join('')||note('Sem aulas planejadas.')}</section>
   <section class="card"><h2>Alunos para acompanhamento</h2><p class="muted small">Inclui queda ≥ 2,5 pontos ou média persistentemente abaixo de 6,0.</p>${obs.students_to_follow.slice(0,20).map(x=>`<div class="listline"><div class="flex"><b>${text(x.student_name)}</b><p class="muted small">${text(x.reason)} · média ${fmt(x.average)}${x.assessment?' · '+text(x.assessment)+' ('+fmt(x.previous)+' → '+fmt(x.current)+')':''}</p></div>${pill(x.drop>=2.5?'↓ '+fmt(x.drop):'Apoio','red')}</div>`).join('')||note('Sem estudantes classificados como prioridade pelas regras atuais.')}</section></div>
   <section class="card" style="margin-top:20px"><h2>Mapa de calor: aluno × tópico</h2><p class="muted small">Médias de cada aluno por conteúdo. Ordenado pela média parcial, da menor para a maior.</p>
   <div class="tablewrap heatmap-scroll"><table class="heatmap"><thead><tr><th>Aluno</th>${topics.map(x=>`<th>${text(x.topic)}</th>`).join('')}<th>Média</th></tr></thead><tbody>
   ${order.map(x=>{const stud=d.students.find(y=>y.id===x.student_id);return `<tr><td><b>${text(x.name)}</b></td>${topics.map(t=>`<td style="${heatColor(x.topics[t.topic])}">${fmt(x.topics[t.topic])}</td>`).join('')}<td><b>${fmt(stud?.average)}</b></td></tr>`}).join('')}</tbody></table></div>
   <div class="legend-heat"><span>Menor que 4: atenção</span><span>4 a 5,9: recuperação</span><span>6 a 7,9: mínimo atingido</span><span>8 ou mais: domínio elevado</span></div></section>${warn()}`;
 }
 async function trail(){if(role()==='aluno')return studentTrail();const {selected,header}=await selectContext(true,true);if(!selected)return head('Trilha ENEM','')+header;
  const m=await api('/pedagogy/matrix?'+qs({class_id:selected.id,subject:selected.subject}));
  if(!m.students.length)return head('Trilha ENEM','')+note('Sem estudantes nesta turma.');
  const stu=m.students.find(x=>x.id===st.student),general=!stu;
  const data=await api((general?'/pedagogy/trail-overview?':'/pedagogy/trail?')+
    qs({class_id:selected.id,subject:selected.subject,...(!general?{student_id:stu.id}:{})}));
  const sorted=data.topics||[];
  const scope=general?'Visão geral da turma':stu.name;
  const actionable=sorted.map((item,i)=>{
    const cases=(m.topic_heatmap||[]).map(row=>({id:row.student_id,name:row.name,score:row.topics?.[item.topic]}))
      .filter(row=>row.score!==undefined&&row.score!==null&&row.score<6&&
        (general||row.id===stu.id)).sort((a,b)=>a.score-b.score);
    const reasons=[];
    if(item.domain!==null&&item.domain<5.5)reasons.push('Histórico ponderado em '+fmt(item.domain)+', abaixo da faixa de referência 5,5.');
    else if(item.domain!==null&&item.domain<7)reasons.push('Histórico ponderado em '+fmt(item.domain)+': vale consolidar os conceitos.');
    if(item.trend!==null&&item.trend<=-1.5)reasons.push('Queda longitudinal de '+fmt(Math.abs(item.trend))+' ponto(s), comparando as observações disponíveis.');
    if(cases.length)reasons.push(general?cases.length+' estudante(s) com média atual abaixo de 6,0 neste tópico.':'Nota atual abaixo de 6,0 neste tópico.');
    if(!reasons.length)reasons.push('O histórico disponível indica manutenção ou aprofundamento; verifique novas avaliações antes de decidir.');
    const sub=selected.subject.toLowerCase();
    const action=/matem|fís|quím|estat/.test(sub)?'Retome um exemplo resolvido, explicite o raciocínio e proponha duas variações de dificuldade crescente.':/port|ling|red|liter/.test(sub)?'Trabalhe uma leitura guiada, peça a justificativa das respostas e proponha revisão em duplas.':'Discuta um caso concreto, identifique conceitos que geraram dúvidas e faça uma verificação curta após a revisão.';
    return `<article class="trail-priority-card ${item.priority==='alta'?'high':''}"><div class="row spread"><div><span class="eyebrow">Prioridade ${text(item.priority)} · ${i+1}º foco</span><h3>${text(item.topic)}</h3></div>${pill(item.priority,item.priority==='alta'?'red':item.priority==='média'?'amber':'teal')}</div>
      <p class="feature-teaser">${reasons[0]}</p><div class="trail-evidence"><b>Por que este tema?</b><ul>${reasons.map(x=>`<li>${text(x)}</li>`).join('')}</ul></div>
      <div class="trail-intervention"><b>Como trabalhar:</b> ${text(action)}</div>
      ${general?`<div class="trail-students"><b>Alunos que precisam de acompanhamento (${cases.length})</b><p>${cases.length?cases.slice(0,6).map(c=>`${text(c.name)} · ${fmt(c.score)}`).join(' · '):'Nenhum estudante com média atual abaixo de 6,0 neste tópico.'}${cases.length>6?' · e outros '+(cases.length-6):''}</p></div>`:''}
      <details class="inline-details"><summary>Saiba mais · histórico e interpretação</summary><div class="inline-details-body"><p>9º ano, 1ª série, 2ª série e atual são observações discretas; não representam um monitoramento contínuo nem uma medida de aptidão.</p><p>Registros disponíveis: ${data.years.map(year=>`${text(year)}: ${fmt(item.series[year])}`).join(' · ')}</p></div></details>
      <button class="btn sm" data-pg="focus-diagnostic" data-context="${text(classKey(selected))}" data-topic="${text(selected.subject+'::'+item.topic)}">Abrir diagnóstico detalhado</button>
    </article>`;
  });
  return head('Trilha ENEM · 3ª série','Comece pela visão geral da sala; selecione um aluno somente quando precisar acompanhar seu histórico.')+
   `<div class="row trail-toolbar">${header}<form id="pg-student" class="row compact-filter"><label class="field">Visualizar<select name="student"><option value="geral" ${general?'selected':''}>Geral da turma</option>${m.students.map(x=>`<option value="${text(x.id)}" ${!general&&x.id===stu.id?'selected':''}>${text(x.name)}</option>`).join('')}</select></label><button class="btn sm">Aplicar</button></form></div>
   <div class="grid cols3" style="margin-top:18px">${metric('Tópicos acompanhados',sorted.length,general?data.student_count+' estudantes':'Histórico individual')}${metric('Prioridade alta',sorted.filter(x=>x.priority==='alta').length,'Requer revisão','#d47790')}${metric('Domínio médio',fmt(stats(sorted.map(x=>x.domain))?.mean),'Resultado longitudinal','#4c9690')}</div>
   <section class="card trail-priority-section" style="margin-top:20px"><h2>Mapa das prioridades · ${text(scope)}</h2><p class="feature-teaser">O que merece atenção, por quais motivos e como intervir. ${general?'Os nomes abaixo estão disponíveis somente ao professor e à coordenação; esta tela não é compartilhada com os estudantes.':'Resultados individuais para acompanhamento pedagógico.'}</p>
    <div class="trail-priority-counts">${['alta','média','baixa'].map(level=>`<div><strong>${sorted.filter(x=>x.priority===level).length}</strong><span>Prioridade ${level}</span></div>`).join('')}</div>
    <div class="trail-priority-grid">${actionable.join('')||note('Ainda não há histórico por tópico suficiente para estabelecer prioridades.')}</div>
    <details class="inline-details trail-history"><summary>Saiba mais · tabela completa de evolução por série</summary><div class="inline-details-body">${table(['Tópico',...data.years,'Tendência','Domínio','Prioridade'],sorted.map(x=>`<tr><td><b>${text(x.topic)}</b></td>${data.years.map(y=>`<td style="${heatColor(x.series[y])}">${fmt(x.series[y])}</td>`).join('')}<td>${x.trend===null?'—':(x.trend>0?'+':'')+fmt(x.trend)}</td><td><b>${fmt(x.domain)}</b></td><td>${pill(x.priority,x.priority==='alta'?'red':x.priority==='média'?'amber':'teal')}</td></tr>`).join('')||'<tr><td colspan="8">Sem histórico nesta disciplina.</td></tr>')}</div></details>
   </section>${warn()}`;
 }
 async function config(){if(role()!=='coord')return empty('Acesso restrito','Somente coordenação.');const id=school();const d=await api('/pedagogy/configuration?'+qs({school:id}));
  return head('Configurações da escola','Critérios pedagógicos somente para a coordenação da instituição selecionada.')+
  `<section class="card"><form id="pg-config" class="formgrid"><input type="hidden" name="school_id" value="${text(id)}"><label class="field">Média de aprovação<input name="mediaAprov" type="number" step="0.5" min="0" max="10" value="${d.mediaAprov}" required></label>
  <label class="field">Média para recuperação<input name="mediaRec" type="number" step="0.5" min="0" max="10" value="${d.mediaRec}" required></label>
  <label class="field">Ano letivo<input name="anoLetivo" type="number" min="2020" max="2100" value="${d.anoLetivo}" required></label><button class="btn primary">Salvar critérios</button></form></section>
  <section class="card" style="margin-top:18px"><h2>Calendário da escola</h2>${table(['Evento','Início','Fim'],(d.calendario||[]).map(x=>`<tr><td>${text(x.nome)}</td><td>${text(x.inicio)}</td><td>${text(x.fim)}</td></tr>`).join(''))}</section>`;}
 async function studentData(){return api('/student/dashboard?'+qs({school:school()}));}
 async function studentHome(){const r=await studentData();const pri=r.topics[0],history=r.longitudinal||[];
  const next=r.grades.flatMap(x=>x.assessments.filter(a=>a.score===null).map(a=>({...a,subject:x.subject}))).sort((a,b)=>(a.date||'9999').localeCompare(b.date||'9999')).slice(0,4);
  return head('Início','Seu espaço pessoal: notas, prática, histórico, objetivos e próximos passos.')+
    `<div class="grid cols4">${metric('Disciplinas',r.grades.length,'Do seu boletim')}${metric('Questões resolvidas',r.practice.n,'Histórico de prática','#4c9690')}${metric('Aproveitamento',r.practice.accuracy===null?'—':fmt(r.practice.accuracy,0)+'%','Nas questões respondidas','#d19e58')}${state.me.has_third_year?metric('Prioridades ENEM',history.filter(x=>x.priority==='alta').length,'Tópicos para revisão','#d47790'):metric('Assuntos para revisar',r.topics.filter(x=>x.priority_score>=5).length,'A partir de seus registros','#d47790')}</div>
    <div class="grid cols2" style="margin-top:18px"><section class="card"><div class="row spread"><h2>Continue de onde parou</h2><button class="btn sm" data-action="nav" data-page="praticar">Praticar →</button></div>${pri?`<div class="study-focus"><span class="pill amber">Prioridade de estudo</span><h3>${text(pri.topic)}</h3><p class="muted small">${text(pri.subject)} · média ${fmt(pri.average)} · ${pri.misses} erro(s) registrado(s)</p></div>`:note('Nenhum tópico prioritário ainda.')}<div class="row"><button class="btn primary" data-action="nav" data-page="${state.me.has_third_year?'minhatrilha':'meudesempenho'}">${state.me.has_third_year?'Abrir minha Trilha ENEM':'Ver meu desempenho'}</button></div></section>
    <section class="card"><h2>Próximas avaliações</h2>${next.map(x=>`<div class="listline"><span class="pill blue">${text(x.date||'a definir')}</span><div class="flex"><b>${text(x.name)}</b><p class="muted small">${text(x.subject)} · peso ${fmt(x.weight,0)}</p></div></div>`).join('')||note('Nenhuma avaliação pendente no momento.')}</section></div>
    <section class="card" style="margin-top:18px"><h2>Minha aprendizagem por disciplina</h2>${table(['Disciplina','Turma','Média parcial','Avaliações pendentes','Situação'],r.grades.map(x=>`<tr><td><b>${text(x.subject)}</b></td><td>${text(x.class_name)}</td><td class="grade-heat" style="${heatColor(x.average)}">${fmt(x.average)}</td><td>${x.remaining}</td><td>${x.average===null?'Sem notas':x.average>=6?'Acima do mínimo':'Precisa de atenção'}</td></tr>`).join(''))}</section>${warn()}`;
 }
 async function studentGrades(){const r=await studentData();return head('Notas da escola','Somente suas notas e avaliações — nunca as notas dos colegas.')+
  `<div class="grid cols2">${r.grades.map(x=>`<section class="card"><h2>${text(x.subject)} · ${text(x.class_name)}</h2><p><b>Média parcial ${fmt(x.average)}</b></p>${table(['Avaliação','Peso','Nota'],x.assessments.map(a=>`<tr><td>${text(a.name)}</td><td>${fmt(a.weight,0)}</td><td>${fmt(a.score)}</td></tr>`).join(''))}</section>`).join('')||empty('Sem notas','A coordenação ainda não registrou avaliações.')}</div>`;}
 async function studentSchedule(){
   const r=await api('/student/schedule?'+qs({school:school()}));
   const days=['Segunda','Terça','Quarta','Quinta','Sexta'];
   const slots=[...new Set(r.lessons.map(x=>x.slot))].sort((a,b)=>a-b);
   const cell=(day,slot)=>r.lessons.filter(x=>x.weekday===day&&x.slot===slot).map(x=>
      `<div class="lesson-card ${text(x.status)}"><b>${text(x.subject)}</b><span>${text(x.class_name)}${x.room?' · '+text(x.room):''}</span><small>${text(x.topic)}</small>${x.plan?`<details class="lesson-plan-details"><summary>Plano desta aula</summary><p>${text(x.plan)}</p></details>`:''}${x.status==='dada'?'<em>Aula realizada</em>':x.status==='cancelada'?'<em>Aula cancelada</em>':''}</div>`).join('')||'<span class="quiet">—</span>';
   return head('Meu cronograma','O mesmo quadro semanal usado pelos professores, atualizado com as aulas e avaliações que eles registram.')+
    `<section class="card nopad"><div class="cardhead row spread"><div><h2>Minha semana</h2><p>Conteúdo planejado, aulas realizadas e alterações persistidas na escola.</p></div>${pill(r.lessons.length+' aula(s)','blue')}</div>
    <div class="tablewrap"><table class="weekly"><thead><tr><th>Horário</th>${days.map(d=>`<th>${d}</th>`).join('')}</tr></thead><tbody>
    ${slots.map(sl=>`<tr><th>${Number(sl)+1}ª aula</th>${days.map((_,d)=>`<td>${cell(d,sl)}</td>`).join('')}</tr>`).join('')||'<tr><td colspan="6">Ainda não existem aulas no seu cronograma.</td></tr>'}</tbody></table></div></section>
    <section class="card" style="margin-top:18px"><div class="row spread"><h2>Próximas avaliações</h2>${pill(r.assessments.length+' cadastrada(s)','blue')}</div>
    <div class="grid cols2">${r.assessments.map(x=>`<article class="subcard"><span class="pill blue">${text(x.scheduled_on||'Data a definir')}</span><h3>${text(x.name)}</h3><p class="muted small">${text(x.subject)} · ${text(x.class_name)} · peso ${fmt(x.weight)}</p></article>`).join('')||note('Nenhuma avaliação cadastrada pela escola.')}</div></section>`;
 }
 async function studentNeeded(){const r=await studentData();return head('Quanto preciso tirar','Cálculo da média necessária nas avaliações pendentes, conforme o modelo demonstrativo.')+
  `<div class="grid cols2">${r.grades.map(x=>`<section class="card"><h2>${text(x.subject)} · ${text(x.class_name)}</h2>
  <div class="stat-bignum">${x.needed===null?'—':fmt(x.needed)}</div><p class="muted">${text(x.needed_message||'Média necessária nas avaliações restantes')} · ${x.remaining} avaliações sem nota</p>
  ${x.needed!==null?miniBar(x.needed):''}</section>`).join('')}</div>`;}
 async function studentPerformance(){const r=await studentData();return head('Meu desempenho','Acompanhamento individual por matéria e tópico, sem expor notas de outros estudantes.')+
  `<div class="grid cols3">${metric('Média entre disciplinas',fmt(r.grades.length?r.grades.map(x=>x.average).filter(x=>x!==null).reduce((a,b)=>a+b,0)/Math.max(1,r.grades.filter(x=>x.average!==null).length):null),'Médias parciais')}${metric('Questões praticadas',r.practice.n,'Respostas registradas','#43a49d')}${metric('Acertos',fmt(r.practice.accuracy,0)+'%','Percentual observado','#d19e58')}</div>
  <section class="card" style="margin-top:18px"><h2>Mapa de domínio por tópico</h2>${table(['Matéria','Tópico','Média','Acertos na prática','Prioridade'],r.topics.map(x=>`<tr><td>${text(x.subject)}</td><td>${text(x.topic)}</td><td>${fmt(x.average)}</td><td>${x.accuracy===null?'—':fmt(x.accuracy,0)+'%'}</td><td>${fmt(x.priority_score)}</td></tr>`).join(''))}</section>`;}
 async function studentTrail(){if(!state.me.has_third_year)return empty('Trilha ENEM exclusiva da 3ª série','O acompanhamento das outras séries permanece em Meu desempenho.');const r=await studentData();const history=r.longitudinal||[],years=r.history_years||['9º ano','1ª série','2ª série','Atual'];
  return head('Minha Trilha ENEM','Histórico do 9º ano à série atual, prioridades de revisão e metas semanais.')+
    `<div class="grid cols3" style="margin-bottom:18px">${metric('Tópicos acompanhados',history.length,'Diferentes anos de estudo')}${metric('Prioridade alta',history.filter(x=>x.priority==='alta').length,'Conteúdos a reforçar','#d47790')}${metric('Plano semanal',r.study_plan.length+' etapas','Revisão por regras','#4c9690')}</div>
    <section class="card"><h2>Meu histórico por tópico</h2><p class="muted small">Os mesmos dados fictícios longitudinais do HTML; a coluna Atual é calculada com as notas do SQLite.</p>
    ${table(['Disciplina','Tópico',...years,'Tendência','Domínio','Prioridade'],history.map(x=>`<tr><td>${text(x.subject)}</td><td><b>${text(x.topic)}</b></td>${years.map(y=>`<td style="${heatColor(x.years[y])}">${fmt(x.years[y])}</td>`).join('')}<td>${x.trend===null?'—':(x.trend>0?'+':'')+fmt(x.trend)}</td><td><b>${fmt(x.domain)}</b></td><td>${pill(x.priority,x.priority==='alta'?'red':x.priority==='média'?'amber':'teal')}</td></tr>`).join(''))}</section>
    <div class="grid cols2" style="margin-top:18px"><section class="card"><h2>Plano de revisão — quatro semanas</h2>${r.study_plan.map(x=>`<div class="listline"><span class="pill blue">Semana ${x.week}</span><div class="flex"><b>${text(x.topic)} · ${text(x.subject)}</b><p class="muted small">${x.minutes} minutos · ${text(x.task)}</p></div></div>`).join('')||note('Sem dados suficientes.')}</section>
    <section class="card"><h2>Minhas metas de estudo</h2><p class="muted small">Escolha quantas questões pretende resolver por tópico nesta semana.</p>
    ${r.topics.slice(0,8).map(x=>`<form class="pg-goal row" data-topic="${text(x.topic)}"><span class="flex">${text(x.subject)} · ${text(x.topic)}</span><label class="field">Questões/semana<input name="target" type="number" min="1" max="200" value="${x.goal}" style="width:100px"></label><button class="btn sm">Salvar</button></form>`).join('')}</section></div>${warn()}`;
 }
 async function vocation(){const d=await api('/student/vocational?'+qs({school:school()}));const r=await studentData();return head('Vocação','Explore interesses profissionais sem confundir notas escolares com aptidão ou vocação.')+
  `<div class="grid cols2"><section class="card"><h2>Meus interesses</h2><form id="pg-preferences"><div class="interest-grid">${d.values.map(x=>`<label class="interest"><input type="checkbox" name="values" value="${text(x)}" ${d.selected.includes(x)?'checked':''}> ${text(x)}</label>`).join('')}</div><label class="field">Horas semanais para estudo<input type="number" min="1" max="30" name="hours" value="${r.preferences.hours||4}"></label><button class="btn primary">Salvar preferências</button></form></section>
  <section class="card"><h2>Áreas para explorar</h2>${d.suggestions.map(x=>`<div class="listline"><b>${text(x)}</b></div>`).join('')||note('Selecione interesses para receber possibilidades.')}<p class="muted small">${text(d.message)}</p></section></div>`;}
 async function practice(){const topic=state.studyTopic||'';const [q,p,r]=await Promise.all([api('/student/practice/queue?'+qs({school:school(),topic,limit:6})),api('/practice/progress'),studentData()]);st.practice=q.items;return head('Praticar',topic?'Questões para revisar '+topic+'. Escolha uma alternativa e confira a explicação.':'Questões liberadas do banco central, sem gabarito antes da resposta.')+
  (topic?`<div class="row" style="margin-bottom:16px">${pill('Foco: '+topic,'amber')}<button class="btn sm" data-pg="clear-practice-topic">Mostrar todos os assuntos</button></div>`:'')+
  `<div class="grid cols3" style="margin-bottom:18px">${metric('Questões respondidas',p.n,'Histórico')}${metric('Acertos',p.hits,'Respostas corretas','#43a49d')}${metric('Aproveitamento',fmt(p.accuracy,0)+'%','Da prática','#d19e58')}</div>
  ${q.items.map(x=>`<article class="q-card"><div class="q-meta">${pill(x.discipline)}${pill(x.topic||'Geral','amber')}</div><h3>${text(x.title)}</h3><p>${text(x.context||'')}</p><p><b>${text(x.prompt)}</b></p>${(x.alternatives||[]).map(a=>`<label class="alternative"><input type="radio" name="pg-answer-${text(x.id)}" value="${text(a.letter)}"> ${text(a.letter)} — ${text(a.text)}</label>`).join('')}<div class="row"><button class="btn primary" data-pg="answer" data-id="${text(x.id)}">Responder</button><span id="pg-result-${text(x.id)}"></span></div></article>`).join('')||empty('Sem questões liberadas','A coordenação precisa revisar e disponibilizar questões para a sua matéria.')}<div class="row" style="margin-top:20px"><button class="btn" data-pg="refresh-practice">Sortear outras questões</button></div>
  <section class="card" style="margin-top:20px"><h2>Caderno de erros</h2><p class="muted small">Registro de exercícios respondidos incorretamente. Use os motivos para direcionar revisões.</p>
   ${table(['Disciplina','Tópico','Data','Motivo identificado'],(r.practice.recent||[]).filter(x=>!x.correct).slice(0,10).map(x=>`<tr><td>${text(x.discipline)}</td><td>${text(x.topic)}</td><td>${text(x.created_at)}</td><td>${text(x.reason||'Ainda não informado')}</td></tr>`).join('')||'<tr><td colspan="4">Nenhum erro recente registrado.</td></tr>')}</section>`;}
 async function permissionPage(){const d=await api('/permissions');const cols=[['student','Aluno'],['teacher','Professor'],['coordinator','Coordenação']];const col={'aluno':'student','prof':'teacher','coord':'coordinator'}[role()];return head('Projeto do sistema','Permissões do HTML original, agora aplicadas no servidor e limitadas aos vínculos de cada escola.')+
 `<section class="card"><h2>Matriz de permissões</h2><p class="muted small">A coluna destacada é a sua função. Nesta versão, “todas” significa apenas turmas, alunos e disciplinas da escola atribuída.</p>
 ${table(['Recurso',...cols.map(x=>x[1])],d.matrix.map(x=>`<tr><td class="wrap"><b>${text(x.resource)}</b></td>${cols.map(([key])=>`<td class="${key===col?'own-column':''}">${text(x[key])}</td>`).join('')}</tr>`).join(''))}</section>
 <section class="card" style="margin-top:18px"><h2>Segurança e escopos</h2><p>Uma conta de coordenação não pode editar outra escola; cada docente recebe somente suas disciplinas e turmas; cada aluno vê apenas seus dados pessoais.</p><p class="muted small">A coordenação pode consultar enunciado, alternativas e gabarito das questões ENEM, IA e do acervo particular de sua própria escola. Não pode consultar acervos privados de outras instituições ou modificar a curadoria central. O professor vê questões das matérias atribuídas; o aluno acessa questões liberadas na prática, sem gabarito prévio.</p></section>`;}
 async function audit(){if(role()!=='coord')return empty('Acesso restrito','Somente coordenação.');const id=school();const d=await api('/audit/grades?'+qs({school:id}));return head('Registro de acesso','Histórico de alterações de notas da instituição vinculada.')+`<section class="card">${table(['Quando','Responsável','Aluno','Turma','Matéria','Avaliação','Antes','Depois'],d.map(x=>`<tr><td>${text(x.created_at)}</td><td>${text(x.coordinator_name)}</td><td>${text(x.student_name)}</td><td>${text(x.class_name)}</td><td>${text(x.subject)}</td><td>${text(x.assessment)}</td><td>${fmt(x.previous_score)}</td><td>${fmt(x.new_score)}</td></tr>`).join('')||'<tr><td colspan="8">Sem alterações registradas.</td></tr>')}</section>`;}
 const pages={institucional:institution,docentepainel:teacherPanel,agenda,cronograma:agenda,cronogramaaluno:studentSchedule,notas:gradeBook,analise:insights.page,diagnostico:insights.page,trilha:trail,configuracoes:config,inicio:studentExperience.home,boletim:studentExperience.grades,preciso:studentExperience.grades,meudesempenho:studentExperience.performance,minhatrilha:studentExperience.trail,vocacao:studentExperience.vocation,praticar:practice,projeto:permissionPage,auditoria:audit};
 function bind(root){root.addEventListener('change',ev=>{
   if(ev.target.matches('#pg-grade select[name=assessment]')){
     const sel=ev.target,topics=JSON.parse(sel.selectedOptions[0]?.dataset.topics||'[]');
     const area=document.getElementById('pg-topic-breakdown');if(!area)return;
     area.innerHTML=topics.length>1?`<p class="muted small">Notas específicas por tópico (opcionais). A nota global não é dividida artificialmente entre tópicos.</p>${topics.map(t=>`<label class="field">${text(t)}<input name="topic__${text(t)}" type="number" min="0" max="10" step="0.1" placeholder="Sem evidência específica"></label>`).join('')}`:'';
   }
 });root.addEventListener('submit',async ev=>{
   const form=ev.target;if(!form.id?.startsWith('pg-')&&!form.classList.contains('pg-goal'))return;
   ev.preventDefault();try{const data=Object.fromEntries(new FormData(form).entries());
    if(form.id==='pg-context'){st.context=data.context;st.student='';await renderPage()}
    if(form.id==='pg-student'){st.student=data.student;await renderPage()}
    if(form.id==='pg-grade'){
      const topicScores={};for(const [key,value] of new FormData(form).entries())if(key.startsWith('topic__')&&value!=='')topicScores[key.slice(7)]=Number(value);
      Object.keys(data).filter(k=>k.startsWith('topic__')).forEach(k=>delete data[k]);
      data.score=Number(data.score);if(Object.keys(topicScores).length)data.topic_scores=topicScores;
      const result=await api('/grades',data);alertUser(result.note||'Nota salva pela coordenação.');await renderPage()}
    if(form.id==='pg-assessment'){await api('/pedagogy/assessments',{...data,weight:Number(data.weight),topics:data.topics.split(',').map(x=>x.trim()).filter(Boolean)});alertUser('Avaliação cadastrada.');await renderPage()}
    if(form.id==='pg-config'){await api('/pedagogy/configuration',{...data,mediaAprov:Number(data.mediaAprov),mediaRec:Number(data.mediaRec),anoLetivo:Number(data.anoLetivo)},'PATCH');alertUser('Configurações atualizadas.');await renderPage()}
    if(form.id==='pg-lesson'){const d={topic:data.topic,plan:data.plan,status:data.status,notes:data.notes};const saved=await api('/pedagogy/schedule/'+encodeURIComponent(data.id),d,'PATCH');if(!saved.ok||!saved.lesson||saved.lesson.topic!==d.topic.trim())throw Error('Não foi possível confirmar a gravação da aula.');await renderPage();alertUser('Atividade salva no banco e confirmada após a gravação.');}
    if(form.id==='pg-new-lesson'){
      const options=JSON.parse(document.getElementById('pg-new-lesson-combos')?.textContent||'[]');const c=options[Number(data.combo)];
      if(!c)throw Error('Escolha uma turma e disciplina.');
      const saved=await api('/pedagogy/schedule',{class_id:c.id,subject:c.subject,
        weekday:Number(data.weekday),slot:Number(data.slot)-1,room:data.room||'',
        topic:data.topic,plan:data.plan||'',status:data.status,notes:data.notes||''});
      if(!saved.ok||!saved.lesson||saved.lesson.topic!==data.topic.trim())throw Error('O banco não confirmou a nova atividade.');
      await renderPage();alertUser('Atividade criada e salva no cronograma da turma.');
    }
    if(form.classList.contains('pg-goal')){await api('/student/goals',{school_id:school(),topic:form.dataset.topic,target:Number(data.target)});alertUser('Meta atualizada.')}
    if(form.id==='pg-preferences'){const fd=new FormData(form);await api('/student/preferences',{school_id:school(),values:fd.getAll('values'),hours:Number(data.hours),feedback:{}});alertUser('Preferências salvas.');await renderPage()}
   }catch(err){alertUser(err.message,false)}
 });
 root.addEventListener('click',async ev=>{const el=ev.target.closest('[data-pg]');if(!el)return;try{
  const a=el.dataset.pg;
  if(a==='focus-diagnostic'){
    st.context=el.dataset.context;st.student='';insights.focus(el.dataset.context,el.dataset.topic||'');state.page='analise';await drawApp();return;
  }
  if(a==='prepare-lesson'){
    const panel=document.getElementById('teacher-prep');if(!panel)return;
    panel.innerHTML='<section class="card"><p class="muted">Preparando revisão com as evidências disponíveis…</p></section>';
    const result=await api('/teacher-tools/lesson/'+encodeURIComponent(el.dataset.id));st.lessonAssistant=result;
    panel.innerHTML=`<section class="card"><div class="row spread"><div><span class="eyebrow">Assistente da próxima aula</span><h2>${text(result.class_name)} · ${text(result.subject)}</h2><p class="muted small">Foco sugerido: ${text(result.focus_topic)}. Ajuste antes de salvar.</p></div>${pill('Atividade individual','teal')}</div>
      <div class="teacher-evidence">${result.reasons.map(x=>`<p>${text(x)}</p>`).join('')}</div>
      <div class="lesson-steps">${result.steps.map(s=>`<div><b>${s.minutes} min · ${text(s.title)}</b><p>${text(s.activity)}</p></div>`).join('')}</div>
      <label class="field">Plano ajustável<textarea id="teacher-plan-editor" rows="7" maxlength="3000">${text(result.plan)}</textarea></label>
      ${result.question_suggestions.length?`<p class="muted small">Questões relacionadas no banco: ${result.question_suggestions.map(q=>text(q.title||q.topic||q.id)).join(' · ')}.</p>`:''}
      <div class="row"><button class="btn primary" data-pg="apply-prepared-lesson">Salvar em Minha semana</button><button class="btn" data-pg="quick-diagnostic">Preparar diagnóstico rápido (3 questões)</button></div>
      <p class="muted small">${text(result.note)}</p></section>`;
    panel.scrollIntoView({behavior:'smooth',block:'nearest'});return;
  }
  if(a==='apply-prepared-lesson'){
    const item=st.lessonAssistant,plan=document.getElementById('teacher-plan-editor')?.value?.trim();
    if(!item||!plan)throw Error('Revise o plano antes de salvá-lo.');
    await api('/teacher-tools/lesson/'+encodeURIComponent(item.lesson_id)+'/apply',{plan});
    alertUser('Revisão salva no planejamento de Minha semana.');return;
  }
  if(a==='quick-diagnostic'){
    const item=st.lessonAssistant;if(!item)return;
    state.quickDiagnostic={class_id:item.class_id,subject:item.subject,topic:item.focus_topic};
    state.page='provas';await drawApp();return;
  }
  if(a==='run-ai-diagnosis'){
    const target=document.getElementById('pg-ai-result');if(!target)return;
    el.disabled=true;target.textContent='Analisando os padrões disponíveis e cruzando-os com as aulas…';
    try{
      const report=await api('/ai/diagnose',{school_id:el.dataset.school,class_id:el.dataset.class,subject:el.dataset.subject});
      const days=['Segunda','Terça','Quarta','Quinta','Sexta'];
      target.innerHTML=`<div class="row spread"><b>${text(report.generated?'Diagnóstico elaborado com IA':'Análise estatística local')}</b>${pill(report.generated?'IA ativa':'Regras locais',report.generated?'teal':'amber')}</div>
       <p>${text(report.summary)}</p><h3>Padrões observados</h3><ul>${(report.patterns||[]).map(x=>`<li>${text(x)}</li>`).join('')}</ul>
       <h3>Revisões sugeridas na semana</h3>${(report.weekly_plan||[]).map(x=>`<div class="listline"><span class="pill blue">${text(days[x.weekday]||days[x.dia]||'Aula')} · ${Number(x.slot??x.aula??0)+1}ª</span><div class="flex"><b>${text(x.focus_topic||x.topico||'Revisão')}</b><div class="muted small">${text(x.activity||x.atividade||'Exercícios guiados')} · ${text(x.minutes||x.minutos||10)} min</div></div></div>`).join('')||note('Sem aulas futuras registradas para distribuir revisões.')}
       <p class="muted small">${text(report.message)}</p>`;
    }finally{el.disabled=false}
    return;
  }
  if(a==='clear-practice-topic'){state.studyTopic='';await renderPage();return}
  if(a==='refresh-practice'){await renderPage();return}
  if(a==='edit-lesson'){const x=(st.lessons||[]).find(v=>v.id===el.dataset.id);if(!x)return;document.querySelector('#pg-lesson-panel').innerHTML=`<div class="card" style="margin-top:18px"><h2>Plano · ${text(x.class_name)} · ${text(x.subject)}</h2><form id="pg-lesson" class="stack"><input type="hidden" name="id" value="${text(x.id)}"><label class="field">Tópico<input name="topic" value="${text(x.topic)}" required></label><label class="field">Plano de aula<textarea name="plan" rows="3">${text(x.plan)}</textarea></label><label class="field">Situação<select name="status">${['planejada','dada','cancelada'].map(v=>`<option ${v===x.status?'selected':''}>${v}</option>`).join('')}</select></label><label class="field">Observações<textarea name="notes" rows="3">${text(x.notes)}</textarea></label><button class="btn primary">Salvar aula</button></form></div>`;return}
  if(a==='answer'){const q=el.dataset.id;const box=document.querySelector(`input[name="pg-answer-${CSS.escape(q)}"]:checked`);if(!box){alertUser('Escolha uma alternativa.');return}const ans=await api('/practice/answer',{question_id:q,school_id:school(),letter:box.value});document.getElementById('pg-result-'+q).innerHTML=ans.correct?pill('Correto!','teal'):pill('Gabarito: '+ans.correct_letter,'amber');el.disabled=true;return}
 }catch(err){alertUser(err.message,false)}});
 }
 insights.bind(root);
 studentExperience.bind(root);
 return {pages,bind};
}
