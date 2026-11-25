import {createPedagogy} from './pages/pedagogy.js';
/* Cognix v10.0 · acervos explícitos, importação recuperável e vínculos revogáveis */
const root=document.getElementById('root');
const state={me:null,page:'docentepainel',school:'todas',q:{text:'',year:'',area:'',subject:'',topic:'',difficulty:'',source:'',status:'',rights_status:'',creator_id:'',scope:'',page:1},selected:new Set(),selectedClass:'',selectedSubject:'',team:null,authMode:'login',signupPlan:'individual',authError:'',busy:false,questionsTab:'all',allSearch:{q:'',discipline:'',topic:'',source:'',status:'',page:1},bankCollection:'',bankBatch:'',bankQ:'',bankSubject:'',bankTopic:'',mineSubject:'',minePage:1,examDraft:null,examView:null,examEditing:null,examAnswers:false,formDrafts:{},draftPromptInEdit:null,questionPreviewId:null,questionEditorId:null,minePreviewId:null,draftOwner:null,quickDiagnostic:null};
const escapeHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e=escapeHtml;
const opts=(list,v)=>list.map(x=>`<option value="${e(x[0])}" ${String(x[0])===String(v)?'selected':''}>${e(x[1])}</option>`).join('');
const qstr=o=>new URLSearchParams(Object.entries(o).filter(([k,v])=>v!==''&&v!=null)).toString();
const urlAllowed=x=>{try{const v=new URL(String(x));return v.protocol==='https:'?v.href:''}catch{return ''}};
const role=()=>state.me?.user?.role;
const pill=(label,color='blue')=>`<span class="pill ${color}">${e(label)}</span>`;
const empty=(title,text)=>`<div class="empty"><strong>${e(title)}</strong>${e(text||'')}</div>`;
const field=(name,title,type='text',value='',extra='')=>`<label class="field">${e(title)}<input type="${type}" name="${e(name)}" value="${e(value)}" ${extra}></label>`;
const fselect=(name,title,options,value)=>`<label class="field">${e(title)}<select name="${name}">${opts(options,value)}</select></label>`;
const pageLabel=()=>navs().find(([id])=>id===state.page)?.[1]||({escolas:'Minhas escolas',turmas:'Turmas e disciplinas'})[state.page]||'Visão geral';
const pageGroup=()=>({escolas:'Conta',turmas:'Acompanhamento',docentepainel:'Acompanhamento',institucional:'Acompanhamento',inicio:'Aprendizagem',agenda:'Acompanhamento',cronograma:'Acompanhamento',cronogramaaluno:'Aprendizagem',notas:'Acompanhamento',analise:'Acompanhamento',diagnostico:'Acompanhamento',trilha:'Acompanhamento',minhatrilha:'Aprendizagem',vocacao:'Aprendizagem',praticar:'Aprendizagem',meudesempenho:'Aprendizagem',boletim:'Aprendizagem',preciso:'Aprendizagem',questoes:'Conteúdo e avaliações',provas:'Conteúdo e avaliações',configuracoes:'Administração',equipe:'Administração',auditoria:'Administração',importar:'Administração',perfil:'Conta',projeto:'Conta'})[state.page]||'Cognix';
const head=(title,desc,action='')=>`<header class="pagehead"><div><span class="eyebrow">${e(pageGroup())} / ${e(pageLabel())}</span><h1>${e(title)}</h1><p>${e(desc)}</p></div>${action}</header>`;
const icon={escolas:'⌂',turmas:'▤',docentepainel:'◫',institucional:'◫',inicio:'⌂',agenda:'▦',cronograma:'▦',cronogramaaluno:'▦',notas:'▤',analise:'◉',diagnostico:'◎',trilha:'↗',minhatrilha:'↗',vocacao:'✧',praticar:'✎',meudesempenho:'◉',boletim:'▤',preciso:'∑',questoes:'▣',provas:'▥',equipe:'♙',configuracoes:'⚙',auditoria:'☷',importar:'↓',perfil:'◌',projeto:'☷'};
// Itens e rótulos do HTML original; separados por área apenas para facilitar a leitura.
const menuGroups=()=>role()==='aluno'?[['Minha aprendizagem',[
 ['inicio','Início'],['cronogramaaluno','Meu cronograma'],...(state.me?.has_third_year?[['minhatrilha','Minha Trilha ENEM']]:[]),['vocacao','Vocação'],['praticar','Praticar'],['meudesempenho','Meu desempenho'],['boletim','Notas da escola']]],
 ['Conta',[['perfil','Minha conta'],['projeto','Projeto do sistema']]]]:role()==='prof'?[['Acompanhamento',[
 ['docentepainel','Painel'],['agenda','Minha semana'],['notas','Notas da turma'],['analise','Desempenho e diagnóstico'],...(state.me?.has_third_year?[['trilha','Trilha ENEM · 3ª série']]:[])]],
 ['Conteúdo e avaliações', [['questoes','Banco de questões'],['provas','Montar provas']]],
 ['Conta',[['escolas','Minhas escolas'],['perfil','Meu cadastro'],['projeto','Projeto do sistema']]]]:[
 ['Acompanhamento',[['institucional','Visão institucional'],['cronograma','Cronogramas'],['notas','Lançar notas'],['analise','Desempenho e diagnóstico'],...(state.me?.has_third_year?[['trilha','Trilha ENEM · 3ª série']]:[])]],
 ['Conteúdo e avaliações',[['questoes','Banco de questões'],['provas','Provas e avaliações']]],
 ['Administração',[['equipe','Professores e vínculos'],['configuracoes','Configurações'],['auditoria','Registro de acesso'],['importar','Importação ENEM']]],
 ['Conta',[['perfil','Meu cadastro'],['projeto','Projeto do sistema']]]];
const navs=()=>menuGroups().flatMap(([,items])=>items);
async function api(path,body,method){
  const method_ = method||(body===undefined?'GET':'POST');
  let res;
  try{res=await fetch('/api'+path,{method:method_,credentials:'same-origin',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});}
  catch{throw Error('Conexão com o Cognix interrompida. Mantenha a janela do servidor aberta e tente reconectar. Se a porta mudou, use o novo endereço exibido no inicializador.');}
  const data=await res.json().catch(()=>({detail:'Erro de comunicação com o servidor.'}));
  if(res.status===401 && !path.startsWith('/auth/')){state.me=null;drawAuth();throw Error('Sua sessão expirou. Faça login novamente.');}
  if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:'Não foi possível concluir a operação.');
  return data;
}
function alertUser(message,ok=true){document.querySelector('.alert-floating')?.remove();const div=document.createElement('div');div.className='alert-floating';div.textContent=message;root.appendChild(div);setTimeout(()=>div.remove(),4400)}
function authForm(){const sign=state.authMode==='register',individual=state.signupPlan==='individual';return `<div class="auth-layout">
 <section class="auth-art"><div class="auth-brand"><span class="mark">c</span> Cognix<span class="small" style="font-weight:500;color:#abb9d5">/ educação</span></div>
 <div><p class="eyebrow" style="color:#b5c2ff">Plataforma de aprendizagem</p><h1>Inteligência que transforma a sala de aula.</h1><p class="intro">Um só espaço para escolas, professores, estudantes e um acervo de questões conectado ao ENEM.</p>
 <div class="art-cards"><div><b>3 escolas</b><span>Ambientes independentes</span></div><div><b>ENEM</b><span>Integração por API</span></div></div></div>
 <small style="color:#b9c4d9">Cognix · Protótipo multi-instituição · 2026</small></section>
 <section class="auth-right"><div class="auth-box"><span class="eyebrow">Bem-vindo ao Cognix</span><h2>${sign?'Escolha como acessar':'Entre na sua conta'}</h2><p class="muted" style="font-size:14px">${sign?'O plano define quem cria a conta e como ocorre o acesso à instituição.':'Use seu e-mail e senha para continuar.'}</p>
 <div class="auth-tabs"><button type="button" data-action="mode-login" class="${!sign?'active':''}">Entrar</button><button type="button" data-action="mode-register" class="${sign?'active':''}">Criar conta</button></div>
 ${sign?`<div class="signup-plans" role="group" aria-label="Tipo de plano">
 <button class="signup-plan ${individual?'active':''}" type="button" data-action="plan-individual"><strong>Plano Individual</strong><span>O professor cria a própria conta.</span></button>
 <button class="signup-plan ${!individual?'active':''}" type="button" data-action="plan-school"><strong>Plano da Escola</strong><span>A coordenação cria as contas.</span></button></div>`:''}
 ${sign&&!individual?`<div class="hint school-registration-help" role="status"><b>Cadastro feito pela escola</b><p>Professores, alunos e coordenadores do plano escolar não se cadastram nesta tela. Peça o login e a senha inicial à coordenação da sua instituição.</p><button type="button" class="btn primary" data-action="mode-login">Já tenho um acesso · Entrar</button></div>`:
 `<form id="auth-form" class="stack">${sign?`${field('name','Nome completo','text','','required autocomplete="name"')}
 <input type="hidden" name="plan" value="individual">`:''}
 ${field('email','E-mail','email','','required autocomplete="email"')}${field('password','Senha','password','','required minlength="10" autocomplete="'+(sign?'new-password':'current-password')+'"')}
 <button class="btn primary" style="padding:14px" type="submit">${sign?'Criar conta individual':'Acessar Cognix'} →</button></form>`}
 ${state.authError?`<div class="error" role="alert">${e(state.authError)}</div>`:''}
 ${!sign?`<details class="auth-invite-box"><summary>Recebi um convite institucional</summary><p class="muted small">Confirme o código recebido por e-mail e a senha da sua conta existente ou defina uma senha inicial.</p><form id="accept-school-invite" class="stack">${field('token','Código do convite','text','','required')}${field('password','Senha da conta (mínimo 10 caracteres)','password','','required minlength="10"')}<button class="btn primary">Ativar vínculo escolar</button></form></details>`:''}
 <p class="auth-note">${sign?(individual?'Conta individual destinada a professores. Para ensinar em uma escola, solicite o vínculo e aguarde atribuição da coordenação.':'A escola controla quem recebe acesso e quais turmas cada pessoa pode visualizar.'):'Não existe troca de perfis sem autenticação. Cada usuário possui permissões próprias.'}</p>
 </div></section></div>`}
function drawAuth(){state.me=null;root.innerHTML=authForm()}
function drawOffline(message){root.innerHTML=`<div class="auth-right" style="min-height:100vh"><section class="card" style="width:min(540px,96%);text-align:center"><div class="mark" style="margin:0 auto 15px">c</div><h2>Não foi possível conectar ao Cognix</h2><p class="muted">${e(message)}</p><p class="small muted">Confirme que a janela de inicialização está aberta. O endereço é mostrado nela e pode não ser a porta 8000.</p><button class="btn primary" data-action="retry-connection">Tentar novamente</button></section></div>`;}
const resumableForms=new Set(['random-exam-form','exam-form','question-search','mine-generate','mine-filter','review-form']);
const draftKey=(page,school,id)=>[state.me?.user?.id||'',school,page,id].join('::');
function captureWorkspace(){
 const main=document.getElementById('main');if(!main?.dataset.renderedPage)return;
 const page=main.dataset.renderedPage,school=main.dataset.renderedSchool;
 if(page==='provas'&&state.examDraft){
   captureDraftFields();
   const prompt=main.querySelector('[id^="draft-prompt-"]');
   if(prompt)state.draftPromptInEdit={pos:Number(prompt.id.split('-').pop()),value:prompt.value};
 }
 for(const form of main.querySelectorAll('form')){
   if(!resumableForms.has(form.id))continue;
   state.formDrafts[draftKey(page,school,form.id)]=[...form.elements]
     .filter(x=>x.name&&!['password','file','hidden'].includes(x.type))
     .map(x=>({name:x.name,type:x.type,value:x.value,checked:x.checked}));
 }
}
function restoreWorkspace(page=state.page,school=state.school){
 const main=document.getElementById('main');if(!main)return;
 for(const form of main.querySelectorAll('form')){
   if(!resumableForms.has(form.id))continue;
   const saved=state.formDrafts[draftKey(page,school,form.id)];if(!saved)continue;
   const fields=[...form.elements].filter(x=>x.name&&!['password','file','hidden'].includes(x.type));
   for(const input of fields){
     const item=saved.find(x=>x.name===input.name&&x.value===input.value)
        ||saved.find(x=>x.name===input.name&&!['radio','checkbox'].includes(x.type));
     if(!item)continue;
     if(input.type==='radio'||input.type==='checkbox'){
       const same=saved.find(x=>x.name===input.name&&x.value===input.value);
       if(same)input.checked=Boolean(same.checked);
     }else if(input.tagName==='SELECT'){
       if([...input.options].some(x=>x.value===item.value))input.value=item.value;
     }else input.value=item.value;
   }
 }
}
function shell(){const u=state.me.user;const initials=u.name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();const schools=state.me.schools||[];
return `<div class="shell" id="shell"><aside class="sidebar"><div class="brand"><span class="mark">c</span> Cognix</div><div class="side-sub">Gestão inteligente da aprendizagem</div>
 <div class="navigation-wrap"><nav aria-label="Navegação principal">${menuGroups().map(([group,items])=>`<div class="nav-group"><div class="menu-title">${e(group)}</div>${items.map(([k,v])=>`<button type="button" data-action="nav" data-page="${k}" class="${state.page===k?'active':''}" ${state.page===k?'aria-current="page"':''}><span class="ico" aria-hidden="true">${e(icon[k]||'•')}</span><span>${e(v)}</span></button>`).join('')}</div>`).join('')}</nav></div>
 <div class="side-footer"><div class="footer-user"><span class="avatar">${e(initials)}</span><div style="min-width:0"><strong style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${e(u.name)}</strong><small>${{coord:'Coordenação',prof:'Professor(a)',aluno:'Aluno(a)'}[u.role]}</small></div></div>
 <button class="signout" data-action="logout">Sair da conta ↗</button></div></aside>
 <section class="workspace"><header class="topbar"><div class="row"><button class="btn mobile-menu" data-action="mobile-menu">☰</button><span class="breadcrumb">${e(pageGroup())} <span class="crumb-slash">/</span> <strong>${e(pageLabel())}</strong></span></div>
 <div class="top-actions">${schools.length>1?`<label>Escola <select id="school-filter"><option value="todas">Todas</option>${opts(schools.map(s=>[s.id,s.name]),state.school)}</select></label>`:schools.length?'':'<span class="muted small">Sem vínculo escolar</span>'}<span class="avatar">${e(initials)}</span></div></header>
 <main class="content" id="main"><div class="empty">Carregando…</div></main></section></div>`}
async function loadApp(){const me=await api('/me');if(state.draftOwner&&state.draftOwner!==me.user.id){state.formDrafts={};state.examDraft=null;state.examView=null;state.selected.clear();state.questionEditorId=null;state.questionPreviewId=null;state.minePreviewHTML='';}state.draftOwner=me.user.id;state.me=me;if(!navs().some(x=>x[0]===state.page))state.page=role()==='aluno'?'inicio':role()==='coord'?'institucional':'docentepainel';if(!state.me.schools.some(s=>s.id===state.school))state.school=state.me.schools[0]?.id||'todas';root.innerHTML=shell();await renderPage()}
function schoolQuery(){return state.school==='todas'?'':state.school}
async function renderPage(){const main=document.getElementById('main');if(!main)return;const pages={escolas,turmas,questoes,provas,equipe,importar,perfil,...pedagogy.pages};
 captureWorkspace();const page=state.page,school=state.school;
 try{const markup=await pages[page]();if(!main.isConnected||state.page!==page||state.school!==school)return;
  main.innerHTML=markup;main.dataset.renderedPage=page;main.dataset.renderedSchool=school;
  restoreWorkspace(page,school);
  if(page==='provas'){
    const preset=state.quickDiagnostic;
    if(preset){const f=document.getElementById('random-exam-form');
      const list=JSON.parse(document.getElementById('random-combos')?.textContent||'[]');
      const index=list.findIndex(x=>x.class_id===preset.class_id&&x.subject===preset.subject);
      if(f&&index>=0){f.elements.combo.value=String(index);f.elements.count.value='3';f.elements.title.value='Diagnóstico rápido · '+preset.topic;}
    }
    await randomOptions();restoreWorkspace(page,school);
    if(preset){const f=document.getElementById('random-exam-form');
      const list=JSON.parse(document.getElementById('random-combos')?.textContent||'[]');
      const index=list.findIndex(x=>x.class_id===preset.class_id&&x.subject===preset.subject);
      if(f&&index>=0){f.elements.combo.value=String(index);f.elements.count.value='3';f.elements.title.value='Diagnóstico rápido · '+preset.topic;
        const boxes=[...f.querySelectorAll('input[name=topics]')];
        if(boxes.some(x=>x.value===preset.topic))boxes.forEach(x=>x.checked=x.value===preset.topic);
        state.quickDiagnostic=null;
      }
    }
    if(state.examDraft&&(school==='todas'||state.examDraft.school_id===school))renderExamDraft();
    else if(state.examView){
      let config={};try{config=JSON.parse(state.examView.exam.configuration_json||'{}')}catch{}
      if(school==='todas'||!config.school_id||config.school_id===school)renderExamView();
    }
  }
  if(page==='questoes'){
    if(state.minePreviewHTML&&state.questionsTab==='mine'){
      const panel=document.getElementById('mine-preview');if(panel)panel.innerHTML=state.minePreviewHTML;
    }
    if(state.questionEditorId){await renderQEditor(state.questionEditorId);restoreWorkspace(page,school);}
    if(state.questionPreviewId&&document.getElementById('question-preview')){
      const q=await api('/questions/'+encodeURIComponent(state.questionPreviewId)+'?'+qstr({school:schoolQuery()}));
      const panel=document.getElementById('question-preview');if(panel)panel.innerHTML='<div class="row spread" style="margin-bottom:12px"><h2>Visualização da questão</h2><button class="btn sm" data-action="close-q">Fechar</button></div>'+questionCard(q,'preview');
    }
  }
  document.getElementById('shell')?.classList.remove('menu-open');
 }catch(err){if(main.isConnected)main.innerHTML=`<div class="error">${e(err.message)} <button class="btn sm" data-action="retry-page">Tentar novamente</button></div>`;}}
async function painel(){const [o,q]=await Promise.all([api('/overview?'+qstr({school:schoolQuery()})),api('/questions/stats?'+qstr({school:schoolQuery()}))]);const name=state.me.user.name.split(' ')[0];
const announcements=role()==='coord'?'Gerencie professores e turmas, autorize questões importadas e acompanhe as escolas.':role()==='prof'?'Consulte suas atribuições, encontre boas questões e prepare avaliações para cada turma.':'Pratique questões liberadas e acompanhe seu próprio desempenho.';
return head(`Olá, ${name}!`,'Veja o que está acontecendo no seu espaço de trabalho.')+
 `<section class="hero"><div><span class="eyebrow" style="color:#b5c3ff">Seu espaço de aprendizagem</span><h2>Conhecimento, prática e decisões em um só lugar.</h2><p>${e(announcements)}</p><button class="btn" data-action="nav" data-page="${role()==='aluno'?'praticar':'questoes'}">${role()==='aluno'?'Começar a praticar':'Explorar banco de questões'} →</button></div><span class="hero-art">✦</span></section>
 <div class="grid cols4" style="margin:20px 0"><div class="card kpi" style="--kc:#5368ca"><div class="label">Escolas acessíveis</div><div class="num">${o.schools}</div><small>Vínculos ativos</small></div>
 <div class="card kpi" style="--kc:#d7955f"><div class="label">Minhas turmas</div><div class="num">${o.classes}</div><small>${role()==='coord'?'Turmas cadastradas':'Turmas atribuídas'}</small></div>
 <div class="card kpi" style="--kc:#4e9c9b"><div class="label">Questões no acervo</div><div class="num">${q.total}</div><small>ENEM real: ${q.enem}</small></div>
 <div class="card kpi" style="--kc:#d47790"><div class="label">Provas preparadas</div><div class="num">${o.exams}</div><small>Registradas no sistema</small></div></div>
 <div class="grid cols2"><div class="card"><div class="row spread"><h2>${role()==='aluno'?'Acesso às atividades':'Atribuições recentes'}</h2>${pill(`${o.assignments.length} vínculos`,'blue')}</div>
 <div class="stack" style="margin-top:12px">${o.assignments.slice(0,6).map(x=>`<div class="listline"><span style="color:var(--accent)">▣</span><div><b>${e(x.subject)}</b> · ${e(x.class_name)}<div class="muted small">${e(x.school_name)}</div></div></div>`).join('')||empty('Nenhum vínculo ainda','A coordenação pode atribuir suas turmas e disciplinas.')}</div></div>
 <div class="card"><h2>Seu próximo passo</h2><p class="muted">${e(announcements)}</p><div class="quick-actions">
 <button class="btn subtle" data-action="nav" data-page="escolas">Visualizar escolas</button>
 ${role()==='coord'?`<button class="btn" data-action="nav" data-page="equipe">Gerenciar equipe</button><button class="btn" data-action="nav" data-page="importar">Sincronizar ENEM</button>`:
 role()==='prof'?`<button class="btn" data-action="nav" data-page="provas">Criar avaliação</button>`:`<button class="btn" data-action="nav" data-page="praticar">Praticar</button>`}</div>
 <div class="hint" style="margin-top:18px">O acervo ENEM é centralizado. Notas, matrículas e vínculos ficam separados por instituição e usuário.</div></div></div>`}
async function studio(){const schools=state.me.schools;
 const use=state.school==='todas'?schools[0]?.id:state.school;
 return head('Estúdio clássico do Cognix','Todas as funcionalidades do protótipo HTML, preservadas em um espaço protegido e isolado por escola.')+
 `<div class="card"><h2>Seu ambiente demonstrativo</h2><p class="muted">Os dados deste Estúdio são fictícios e as edições ficam em um rascunho individual por escola. O banco de questões é consultado no servidor.</p>
 ${schools.map(s=>`<div class="listline"><div class="flex"><b>${e(s.name)}</b><div class="muted small">${e((state.me.subjects_by_school||{})[s.id]?.join(', ')||'Sem disciplinas')}</div></div><a class="btn primary sm" href="/studio?school=${encodeURIComponent(s.id)}">Abrir Estúdio →</a></div>`).join('')}
 <div class="hint" style="margin-top:12px">A coordenação visualiza somente a escola administrada; cada professor acessa exclusivamente suas turmas e matérias.</div></div>`;}
async function ia(){if(role()==='aluno')return empty('Acesso exclusivo a educadores','Entre como professor ou coordenação.');
 const [status,classes]=await Promise.all([api('/ai/status'),api('/classes?'+qstr({school:schoolQuery()}))]);
 const combos=classes.flatMap(c=>c.subjects.map(s=>({school_id:c.school_id,class_id:c.id,subject:s,label:c.school_name+' · '+c.name+' · '+s})));
 return head('Assistente pedagógico com LLM','Gere questões e provas personalizadas por matéria, escola, série e tópicos.')+
 `<div class="banner" style="margin-bottom:17px"><b>${status.mode==='llm'?'Gemini API configurada':'Demonstração sem chave Gemini'}</b><p>${e(status.description)}</p></div>
 <div class="grid cols2"><section class="card"><h2>Questões com IA</h2><p class="muted small">Com LLM ativo, os itens são originais e entram em revisão. Sem chave, mostraremos apenas exemplos já existentes.</p>
 <form class="stack" id="llm-question-form">${fselect('combo','Turma e disciplina',combos.map((c,i)=>[i,c.label]),0)}
 ${field('topic','Tópico','text','Funções','required minlength="2"')}
 <div class="formgrid">${fselect('difficulty','Dificuldade',[['fácil','Fácil'],['média','Média'],['difícil','Difícil']],'média')}${field('count','Quantidade (1 a 8)','number','3','required min="1" max="8"')}</div>
 ${field('instructions','Orientações adicionais','text','Contextualizar para a vida cotidiana')}
 <button class="btn primary" ${!combos.length?'disabled':''}>Elaborar questões</button></form><div id="llm-output" style="margin-top:12px"></div></section>
 <section class="card"><h2>Prova personalizada</h2><p class="muted small">Seleciona questões validadas do banco. Com o LLM ativo, pode também criar itens inéditos para revisão docente.</p>
 <form id="llm-exam-form" class="stack">${fselect('combo','Turma e disciplina',combos.map((c,i)=>[i,c.label]),0)}
 ${field('title','Título','text','Avaliação personalizada','required')}${field('topics','Tópicos (separados por vírgula)','text','')}
 <div class="formgrid">${field('count','Quantidade','number','5','min="1" max="20"')}${fselect('difficulty','Nível',[['equilibrada','Equilibrada'],['fácil','Fácil'],['média','Média'],['difícil','Difícil']],'equilibrada')}</div>
 <label class="row small"><input type="checkbox" name="allow_new"> Criar novas questões com LLM quando faltar conteúdo</label>
 <button class="btn primary" ${!combos.length?'disabled':''}>Montar prova</button></form><div id="llm-exam-output" style="margin-top:12px"></div></section></div>
 <script id="llm-combos" type="application/json">${JSON.stringify(combos).replace(/</g,'\\u003c')}</script>`;}
async function escolas(){const schools=state.me.schools;const classes=await api('/classes');return head('Escolas','Selecione uma instituição para visualizar apenas seus dados.')+
 `<div class="grid cols3">${schools.map((s,i)=>{const n=classes.filter(c=>c.school_id===s.id).length;return `<article class="school-card" data-action="school" data-school="${e(s.id)}"><div class="school-top" style="--bg:${['#e7eafb','#fff0e1','#e0f1ed'][i%3]}"><div class="school-initial">${e(s.initials||'E')}</div></div>
 <div class="detail"><div class="row spread">${pill(s.name,['blue','amber','teal'][i%3])}<span class="muted small">${n} turmas</span></div><h3 style="margin-top:16px">${e(s.subtitle)}</h3><p>${e(s.city)}</p><button class="btn sm subtle" data-action="school" data-school="${e(s.id)}">Visualizar escola →</button></div></article>`}).join('')||empty('Sem escolas atribuídas','Solicite à coordenação seu vínculo institucional.')}</div>`}
async function turmas(){const classes=await api('/classes?'+qstr({school:schoolQuery()}));return head('Turmas e disciplinas','Turmas acessíveis segundo suas atribuições e matrículas.')+
 `<div class="grid cols3">${classes.map(c=>`<div class="card"><div class="row spread">${pill(c.school_name,'blue')}<span class="muted small">${e(c.grade)}</span></div><h2 style="margin-top:17px">${e(c.name)}</h2><p class="muted">${c.subjects.length?'Disciplinas: '+c.subjects.map(e).join(', '):'Turma cadastrada'}</p><div class="quick-actions"><button class="btn sm" data-action="show-class" data-class="${e(c.id)}">Ver detalhes</button></div></div>`).join('')||empty('Sem turmas','A coordenação deve atribuir uma turma a esta conta.')}</div><div id="detail-panel" style="margin-top:20px"></div>`}
const areaOpts=[['','Todas as matérias'],['Matemática','Matemática'],['Física','Física'],['Química','Química'],['Biologia','Biologia'],['Linguagens','Linguagens'],['Geografia','Geografia'],['História','História']];
function mySubjectOptions(){const bySchool=state.me?.subjects_by_school||{};
 const schools=schoolQuery()? [schoolQuery()]:Object.keys(bySchool);
 const subjects=[...new Set(schools.flatMap(s=>bySchool[s]||[]))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
 return [['','Todas as minhas matérias'],...subjects.map(x=>[x,x])];} 
const safeImage=u=>{const local=/^\/api\/bank\/attachments\/[a-f0-9]{24}$/.test(String(u))?String(u):'';const v=local||urlAllowed(u);return v?`<img src="${e(v)}" loading="lazy" alt="Figura da questão" referrerpolicy="no-referrer">`:''};
function questionCard(q,mode='bank'){
 const alternatives=(q.alternatives||[]).map(a=>`<div class="alternative"><b>${e(a.letter)}</b> <span>${e(a.text||'')}${a.file?safeImage(a.file):''}</span></div>`).join('');
 const files=(q.media||[]).map(safeImage).join('');
 const selectBtn=mode==='bank'&&role()!=='aluno'&&q.status==='published'&&['demo','authorized'].includes(q.rights_status)?`<button class="btn sm ${state.selected.has(q.id)?'primary':''}" data-action="select-q" data-qid="${e(q.id)}">${state.selected.has(q.id)?'✓ Selecionada':'+ Adicionar à prova'}</button>`:'';
 const reviewBtn=mode==='bank'&&role()==='coord'?`<button class="btn sm" data-action="edit-q" data-qid="${e(q.id)}">Revisar</button>`:'';
 const student=mode==='practice';
 return `<article class="q-card"><div class="q-meta">${pill(q.source,q.source==='ENEM API'?'blue':'amber')}${q.year?pill(q.year):''}${pill(q.display_discipline||q.discipline||q.area||'A classificar')}
 ${role()!=='aluno'?pill(q.status,q.status==='published'?'teal':'amber'):''}<span class="muted small">${e(q.id)}</span></div>
 <h3>${e(q.title)}</h3>${q.context?`<p class="q-context">${e(q.context)}</p>`:''}${files?`<div class="question-files">${files}</div>`:''}
 ${q.prompt?`<p style="font-size:13px;font-weight:700">${e(q.prompt)}</p>`:''}<div class="alternatives">${student?(q.alternatives||[]).map(a=>`<label class="alternative"><input type="radio" name="answer-${e(q.id)}" value="${e(a.letter)}"> <b>${e(a.letter)}</b> <span>${e(a.text)}${a.file?safeImage(a.file):''}</span></label>`).join(''):alternatives}</div>
 ${!student&&role()!=='aluno'?`<p class="small muted" style="margin-top:12px">Gabarito: <b>${e(q.correct_letter||'a revisar')}</b> · ${e(q.topic||'Tópico não classificado')}${q.source_url?` · <a href="${e(urlAllowed(q.source_url))}" target="_blank" rel="noopener noreferrer">Fonte</a>`:''}</p>`:''}
 <div class="row" style="margin-top:15px">${selectBtn}${reviewBtn}${student?`<button class="btn primary sm" data-action="answer" data-qid="${e(q.id)}">Responder</button><span id="answer-result-${e(q.id)}"></span>`:''}</div></article>`;
}
function questionTabs(){return `<div class="question-tabs" role="group" aria-label="Coleções de questões">
 ${role()==='prof'?`<button class="question-tab ${state.questionsTab==='all'?'active':''}" data-action="question-tab" data-tab="all">Geral</button>`:''}
 ${role()==='prof'?`<button class="question-tab ${state.questionsTab==='personal'?'active':''}" data-action="question-tab" data-tab="personal">Meu acervo</button>`:''}
 <button class="question-tab ${state.questionsTab==='school'?'active':''}" data-action="question-tab" data-tab="school">Acervo da escola</button>
 <button class="question-tab ${state.questionsTab==='general'?'active':''}" data-action="question-tab" data-tab="general">ENEM</button>
 ${role()==='prof'?`<button class="question-tab ${state.questionsTab==='mine'?'active':''}" data-action="question-tab" data-tab="mine">Criar com IA</button>`:''}</div>`}

async function generalBank(){
 const f=state.allSearch;
 const result=await api('/bank/general?'+qstr({...f,limit:18}));
 const pages=Math.max(1,Math.ceil(result.total/18));
 return head('Banco de questões · visão geral','Todas as questões que você pode consultar, reunidas em um único lugar.')+questionTabs()+
 `<section class="card" style="margin-bottom:18px"><div class="row spread bank-wrap"><div><h2>Geral</h2><p class="muted small">Seus acervos particulares, questões escolares autorizadas e catálogo central, incluindo ENEM. Itens privados de outros professores e escolas sem vínculo permanecem protegidos.</p></div>${pill(result.total+' questões','blue')}</div>
 <form id="bank-general-search" class="stack" style="margin-top:15px"><div class="bank-form-grid">${field('q','Pesquisar questão','text',f.q)}${field('discipline','Disciplina','text',f.discipline)}${field('topic','Tópico','text',f.topic)}${fselect('source','Origem',[['','Todas'],['ENEM API','ENEM'],['Cognix LLM','Geradas por IA'],['Importação docente','Importadas pelo professor']],f.source)}${fselect('status','Situação',[['','Todas'],['review','Em revisão'],['published','Publicadas'],['archived','Arquivadas']],f.status)}<div class="row bank-wrap" style="align-items:end"><button class="btn primary">Buscar</button><button class="btn sm" type="button" data-action="clear-bank-general">Limpar</button></div></div></form></section>
 <section class="card"><div class="row spread"><h2>Questões disponíveis</h2><span class="muted small">Página ${Math.min(f.page,pages)} de ${pages}</span></div>
 <div class="stack" style="margin-top:15px">${result.items.map(q=>`<details class="bank-general-row"><summary><span class="bank-general-summary"><strong>${e(q.title||q.prompt.slice(0,125)||'Questão sem título')}</strong><small>${e(q.discipline||q.area||'Sem disciplina')} · ${e(q.topic||'Sem tópico')} · ${e(q.scope_label)} · ${e(q.source)}</small></span>${pill(q.status,q.status==='published'?'teal':'amber')}</summary><div class="bank-general-detail">${questionCard(q,'preview')}${q.exam_eligible?`<button class="btn sm" data-action="select-q" data-qid="${e(q.id)}">${state.selected.has(q.id)?'✓ Na seleção':'+ Selecionar para prova'}</button>`:'<p class="muted small">Consulta disponível. Para usar em prova, é necessário vínculo com a disciplina, publicação e autorização dos direitos.</p>'}</div></details>`).join('')||empty('Nenhuma questão localizada','Confira os filtros ou importe questões para seu acervo.')}</div>
 <div class="row" style="justify-content:center;margin-top:20px"><button class="btn sm" data-action="general-prev" ${f.page<=1?'disabled':''}>← Anterior</button>${pill('Página '+Math.min(f.page,pages))}<button class="btn sm" data-action="general-next" ${f.page>=pages?'disabled':''}>Próxima →</button></div></section>`;
}

async function structuredBank(){
 const all=await api('/bank/collections');
 const kind=role()==='coord'||state.questionsTab==='school'?'school':'personal';
 const options=all.collections.filter(c=>c.kind===kind);
 if(!options.some(c=>c.id===state.bankCollection))state.bankCollection=options[0]?.id||'';
 if(!state.bankCollection)return head('Banco de questões','Importe, organize e reutilize itens com rastreabilidade.')+questionTabs()+empty('Nenhum acervo disponível','Solicite vínculo à escola ou ative um acervo pessoal.');
 const [found,batches,authorized]=await Promise.all([api('/bank/search?'+qstr({collection_id:state.bankCollection,q:state.bankQ,discipline:state.bankSubject,topic:state.bankTopic})),api('/bank/batches?'+qstr({collection_id:state.bankCollection})),kind==='personal'&&role()==='prof'?api('/accounts/personal/authorized-questions'):Promise.resolve([])]);
 const batch=state.bankBatch?await api('/bank/batches/'+encodeURIComponent(state.bankBatch)).catch(()=>null):null;
 const isTeacher=true;
 return head('Banco de questões','Importe suas questões, revise a classificação e encontre-as por tópico.')+questionTabs()+
 `<section class="card bank-toolbar"><div class="row spread bank-wrap"><label class="field">${kind==='personal'?'Meu acervo':'Instituição'}<select id="bank-collection">${opts(options.map(c=>[c.id,c.kind==='personal'?'Particular · meu acervo':state.me.schools.find(s=>s.id===c.school_id)?.name||c.school_id]),state.bankCollection)}</select></label>
  <span class="muted small">${e(kind==='personal'?'Questões particulares do seu acesso; nunca visíveis à coordenação.':'Somente usuários vinculados à escola e às disciplinas permitidas.')}</span></div></section>
 ${isTeacher?`<section class="card bank-import"><div class="row spread"><div><h2>Importar questões</h2><p class="muted small">Puxar → armazenar → categorizar → encontrar. O conteúdo é gravado como rascunho antes da sugestão de IA.</p></div>${pill('Rascunhos recuperáveis','teal')}</div>
  <div class="bank-form-grid"><form id="bank-import-text" class="stack"><label class="field"><b>Salvar em</b><select name="collection_id">${opts(all.collections.map(c=>[c.id,c.kind==='personal'?'Meu acervo':state.me.schools.find(s=>s.id===c.school_id)?.name||c.school_id]),state.bankCollection)}</select></label>
  <label class="field">Cole questões (numeradas, com alternativas A–E e gabarito explícito)<textarea name="text" rows="7" placeholder="1. Um corpo realiza movimento...\nA) 10 m/s\nB) 20 m/s\nGabarito: B" required></textarea></label><button class="btn primary" type="submit">Importar texto</button></form>
  <form id="bank-import-file" class="stack"><label class="field"><b>Salvar em</b><select name="collection_id">${opts(all.collections.map(c=>[c.id,c.kind==='personal'?'Meu acervo':state.me.schools.find(s=>s.id===c.school_id)?.name||c.school_id]),state.bankCollection)}</select></label>
  <label class="field">Documento (DOCX ou PDF com texto; até 10 MB)<input type="file" name="file" accept=".docx,.pdf" required></label><p class="small muted">Gabaritos ausentes são marcados como pendentes, nunca inferidos. PDFs digitalizados precisam de OCR prévio.</p><button class="btn" type="submit">Importar arquivo</button></form></div></section>`:''}
 <section class="grid cols2 bank-columns"><div class="card"><h2>Encontrar questões</h2><form id="bank-search" class="stack"><label class="field">Texto<input name="q" value="${e(state.bankQ)}" placeholder="Palavra do enunciado"></label><div class="formgrid"><label class="field">Disciplina<input name="discipline" value="${e(state.bankSubject)}" placeholder="Ex.: Física"></label><label class="field">Tópico<input name="topic" value="${e(state.bankTopic)}" placeholder="Ex.: Cinemática"></label></div><button class="btn primary">Buscar</button></form>
 <p class="small muted" style="margin-top:14px">${found.total} resultado(s). Dados classificados pelo professor são preservados em novas tentativas de IA.</p>
 <div class="stack">${found.items.map(q=>`<div class="listline"><div class="flex"><b>${e(q.discipline||'Sem disciplina')} · ${e(q.topic||'Sem tópico')}</b><p class="small muted">${e(q.prompt.slice(0,155))}</p>${pill(q.review_state,q.review_state==='published'?'teal':'amber')}</div><button class="btn sm" data-action="bank-preview" data-qid="${e(q.id)}">Detalhes</button>${q.status==='published'?`<button class="btn sm" data-action="select-q" data-qid="${e(q.id)}">${state.selected.has(q.id)?'✓ Na prova':'+ Prova'}</button>`:''}${role()==='coord'&&kind==='school'&&q.status==='published'?`<button class="btn sm" data-action="bank-authorize-preview" data-qid="${e(q.id)}">Autorizar reutilização</button>`:''}</div>`).join('')||empty('Nenhuma questão encontrada','Importe ou ajuste os filtros.')}</div><div id="bank-preview-panel"></div></div>
 <div class="card"><div class="row spread"><h2>Lotes de importação</h2>${pill(batches.length+' lote(s)')}</div><p class="small muted">Reabra um lote para corrigir campos, confirmar categorias e publicar as questões prontas.</p><div class="stack" style="margin-top:14px">${batches.map(b=>`<div class="listline"><div class="flex"><b>${e(b.filename)}</b><div class="muted small">${e(b.origin_format)} · ${e(b.status)}</div></div><button class="btn sm" data-action="bank-open-batch" data-batch="${e(b.id)}">Revisar</button>${['docx','pdf'].includes(b.origin_format)?`<a class="btn sm" href="/api/bank/batches/${e(b.id)}/original" download>Original</a>`:''}</div>`).join('')||empty('Sem lotes','Importe seu primeiro arquivo ou texto.')}</div></div></section>
 ${authorized.length?`<section class="card" style="margin-bottom:18px"><h2>Questões escolares autorizadas para reutilização</h2><p class="muted small">Somente a versão autorizada pela escola fica disponível, sem transferir a propriedade do item.</p>${authorized.map(x=>`<div class="listline"><div class="flex"><b>${e(x.content.discipline)} · ${e(x.content.topic)} · versão ${x.version}</b><p class="small muted">${e(x.content.prompt.slice(0,220))}</p></div>${pill('Autorizada','teal')}</div>`).join('')}</section>`:''}
 ${batch&&batch.batch.collection_id===state.bankCollection?`<section class="card bank-review"><div class="row spread"><div><h2>Revisão do lote · ${e(batch.batch.filename)}</h2><p class="muted small">Questões extraídas, campos ausentes e tópicos sugeridos. Revise antes de confirmar.</p></div><div class="row"><button class="btn sm" data-action="bank-recategorize" data-batch="${e(batch.batch.id)}">Atualizar sugestões da IA</button><button class="btn sm" data-action="bank-close-batch">Fechar</button></div></div>
 <form id="bank-review-form" class="stack" data-batch="${e(batch.batch.id)}">${batch.items.map(x=>`<div class="bank-review-row" data-qid="${e(x.id)}"><div class="row spread"><b>Questão ${x.position}</b>${pill(x.review_state,x.review_state==='draft'?'amber':'teal')}</div><p class="bank-question-text">${e(x.prompt)}</p><div class="small muted">${x.alternatives.map(a=>e(a.letter+') '+a.text)).join(' · ')} · Gabarito: ${e(x.correct_letter||'não encontrado')}</div><p class="small muted">Campos pendentes: ${e(x.missing.join(', ')||'nenhum')} · Sugestão (${e(x.suggestion.origin||'regras')}): ${e(x.suggestion.discipline||'—')} / ${e(x.suggestion.topic||'—')}</p>
 <label class="field">Corrigir enunciado<textarea name="prompt" rows="3">${e(x.prompt)}</textarea></label><div class="bank-alt-grid">${['A','B','C','D','E'].map(letter=>`<label class="field">Alternativa ${letter}<input name="alt-${letter}" value="${e(x.alternatives.find(a=>a.letter===letter)?.text||'')}"></label>`).join('')}</div>
 <div class="formgrid"><label class="field">Gabarito confirmado<select name="correct_letter">${opts([['','A revisar'],...['A','B','C','D','E'].map(l=>[l,l])],x.correct_letter)}</select></label><label class="field">Disciplina<input name="discipline" value="${e(x.discipline||x.suggestion.discipline||'')}" required></label><label class="field">Tópico<input name="topic" value="${e(x.topic||x.suggestion.topic||'')}" required></label></div><label class="small"><input name="rights_confirmed" type="checkbox" ${x.review_state==='published'?'checked':''}> Confirmo os direitos de reutilização e a revisão deste item</label></div>`).join('')||empty('Itens já transferidos ou ausentes','Somente itens pertencentes a este acervo são visíveis.')}
 <button class="btn primary" ${!batch.items.length?'disabled':''}>Confirmar revisão selecionada</button></form></section>`:''}`;
}
async function myQuestions(){
 const [collectionData,llmStatus]=await Promise.all([api('/bank/collections'),api('/ai/status')]);
 const collections=collectionData.collections;
 const personal=collections.find(c=>c.kind==='personal');
 const result=personal?await api('/bank/search?'+qstr({collection_id:personal.id,page:state.minePage,limit:12})):{total:0,items:[]};
 const schoolNames=Object.fromEntries((state.me.schools||[]).map(x=>[x.id,x.name]));
 return head('Banco de questões','Acervo central e coleção particular do professor.')+questionTabs()+
 `<div class="grid cols2 mine-layout">
 <section class="card"><div class="row spread"><h2>Rascunhos e questões particulares</h2>${pill(result.total+' itens','blue')}</div>
 <p class="muted small">Itens do seu acervo particular. Questões geradas para uma escola ficam no acervo daquela instituição. <button class="btn sm" data-action="question-tab" data-tab="personal">Abrir Meu acervo</button></p>
 <div class="stack" style="margin-top:16px">${result.items.map(x=>`<div class="listline"><div class="flex"><b>${e(x.topic||'Tópico pendente')}</b><div class="small muted">${e(x.discipline||'Sem disciplina')} · ${e(x.review_state||'Rascunho')}</div><div class="small muted">${e((x.prompt||'').slice(0,150))}</div></div>${pill(x.status==='published'?'Publicada':'Rascunho',x.status==='published'?'teal':'amber')}<button class="btn sm" data-action="mine-open" data-qid="${e(x.id)}">Abrir</button></div>`).join('')||empty('Seu acervo particular está vazio','Crie questões com IA ou importe um arquivo na aba Meu acervo.')}</div>
 <div class="row" style="justify-content:center;margin-top:15px"><button class="btn sm" data-action="mine-prev" ${state.minePage<=1?'disabled':''}>← Anterior</button><span class="muted small">Página ${state.minePage}</span><button class="btn sm" data-action="mine-next" ${state.minePage*12>=result.total?'disabled':''}>Próxima →</button></div>
 <div id="mine-preview"></div></section>
 <section class="card"><h2>Criar questão com LLM</h2><p class="muted small">Geração real com Gemini, quando configurada. Sem chave, mostramos exemplos locais identificados como simulação. Itens gerados ficam como rascunhos para revisão.</p>
 <div class="hint" style="margin-top:13px"><b>${llmStatus.mode==='llm'?'Chave configurada · conexão ainda não verificada':'IA não configurada'}</b><p class="small muted">${e(llmStatus.description)}</p>${llmStatus.mode==='llm'?`<button type="button" class="btn sm" data-action="probe-llm">Testar conexão com IA</button>`:''}<div id="llm-check" class="small"></div></div>
 <form id="mine-generate" class="stack" style="margin-top:15px">
 ${fselect('collection_id','Salvar em',collections.map(c=>[c.id,c.kind==='personal'?'Meu acervo (particular)':schoolNames[c.school_id]||c.school_id]),collections[0]?.id||'')}
 ${field('subject','Disciplina','text','Física','required maxlength="80"')}
 ${field('topic','Tópico','text','','required minlength="2"')}
 <div class="formgrid">${fselect('difficulty','Dificuldade',[['fácil','Fácil'],['média','Média'],['difícil','Difícil']],'média')}${field('count','Quantidade','number','2','min="1" max="8" required')}</div>
 <label class="field">Orientações específicas<textarea name="instructions" rows="3" placeholder="Contexto, habilidades e cuidados com o enunciado..."></textarea></label>
 <button class="btn primary" ${!collections.length?'disabled':''}>Criar rascunhos</button></form>
 <div id="mine-output"></div></section></div>`;
}
async function coordQuestionBank(){
 const f=state.q, school=schoolQuery();
 const [stats,data,team]=await Promise.all([
  api('/questions/stats?'+qstr({school})),
  api('/questions?'+qstr({q:f.text,year:f.year,area:f.area,subject:f.subject,topic:f.topic,
     difficulty:f.difficulty,source:f.source,status:f.status,rights_status:f.rights_status,
     creator_id:f.creator_id,scope:f.scope,school,page:f.page,limit:20})),
  api('/team')]);
 const origins=[['','Todas as origens'],...stats.by_source.map(x=>[x.source,x.source])];
 const subjects=[['','Todas as disciplinas'],...stats.by_subject.filter(x=>x.discipline).map(x=>[x.discipline,x.discipline])];
 const authors=[['','Todos os autores'],...team.teachers.map(x=>[x.id,x.name])];
 const schools=Object.fromEntries(state.me.schools.map(s=>[s.id,s.name]));
 const totalPages=Math.max(1,Math.ceil(data.total/20));
 return head('Banco de questões','Consulta administrativa do ENEM, das questões com IA e do acervo da sua instituição.')+
 `<section class="grid cols4" style="margin-bottom:18px">
  <div class="card kpi" style="--kc:#5368ca"><div class="label">Total visível</div><div class="num">${stats.total}</div><small>Acervo central e da escola</small></div>
  <div class="card kpi" style="--kc:#4c9690"><div class="label">Questões ENEM</div><div class="num">${stats.enem}</div><small>Questões oficiais importadas</small></div>
  <div class="card kpi" style="--kc:#8d70c6"><div class="label">IA e exemplos</div><div class="num">${stats.ai}</div><small>LLM real ou demonstração identificada</small></div>
  <div class="card kpi" style="--kc:#d39a56"><div class="label">Em revisão</div><div class="num">${stats.review}</div><small>Publicadas: ${stats.published}</small></div>
 </section>
 <section class="card admin-search-card"><div class="row spread"><div><h2>Filtros administrativos</h2><p class="muted small">Pesquise por origem, matéria, tópico, ano, professor e situação. Questões centrais são compartilhadas; as particulares pertencem à sua escola.</p></div><button type="button" class="btn sm" data-action="clear-q">Limpar filtros</button></div>
 <form id="question-search" class="admin-filters">
  <label class="field admin-query">Pesquisar<input name="text" value="${e(f.text)}" placeholder="Enunciado, contexto ou tópico"></label>
  ${fselect('source','Origem',origins,f.source)}
  ${fselect('subject','Disciplina',subjects,f.subject)}
  ${fselect('status','Status',[['','Todos'],['review','Em revisão'],['published','Publicada'],['archived','Arquivada']],f.status)}
  <div class="admin-filter-action"><button class="btn primary" type="submit">Buscar</button></div>
  <details class="admin-advanced" ${[f.topic,f.difficulty,f.year,f.rights_status,f.creator_id,f.scope].some(Boolean)?'open':''}><summary>Mais filtros · tópico, dificuldade, ano, direitos, autor e escopo</summary>
    <div class="admin-extra-grid">
      ${field('topic','Tópico','text',f.topic)}
      ${fselect('difficulty','Dificuldade',[['','Todas'],['fácil','Fácil'],['média','Média'],['difícil','Difícil']],f.difficulty)}
      ${fselect('year','Ano',[['','Todos os anos'],...Array.from({length:30},(_,i)=>[2026-i,2026-i])],f.year)}
      ${fselect('rights_status','Direitos',[['','Todos'],['pending','Pendentes'],['demo','Demonstrativos'],['authorized','Autorizados']],f.rights_status)}
      ${fselect('creator_id','Professor autor',authors,f.creator_id)}
      ${fselect('scope','Escopo',[['','Central e escolar'],['central','Acervo central'],['escola','Somente minha escola']],f.scope)}
    </div>
  </details> </form></section>
 <section class="card nopad admin-results"><div class="cardhead"><div><h2>Catálogo de questões</h2><p class="muted small">${data.total} resultado(s) · página ${Math.min(f.page,totalPages)} de ${totalPages}</p></div></div>
 <div class="tablewrap"><table><thead><tr><th>Questão</th><th>Origem</th><th>Disciplina / tópico</th><th>Dificuldade</th><th>Status</th><th>Responsável / escopo</th><th>Ações</th></tr></thead><tbody>
 ${data.items.map(q=>`<tr><td class="admin-question-name"><b>${e(q.title||q.prompt.slice(0,70)||'Questão sem título')}</b><span class="muted small">${e(q.year||'—')} · ${e(q.question_number||q.id)}</span></td>
 <td>${pill(q.source,q.source==='ENEM API'?'blue':q.source.includes('LLM')?'purple':'amber')}</td>
 <td>${e(q.display_discipline||q.discipline||'A classificar')}<span class="muted small admin-subline">${e(q.topic||'Tópico não classificado')}</span></td>
 <td>${e(q.difficulty||'—')}</td><td>${pill(q.status,q.status==='published'?'teal':'amber')}<span class="muted small admin-subline">${e(q.rights_status)}</span></td>
 <td>${e(q.creator_name||'Acervo institucional')}<span class="muted small admin-subline">${e(q.school_id?schools[q.school_id]||'Esta escola':'Central · todas as escolas')}</span></td>
 <td><div class="row admin-item-actions"><button class="btn sm" data-action="view-q" data-qid="${e(q.id)}">Visualizar</button>${q.school_id?`<button class="btn sm" data-action="edit-q" data-qid="${e(q.id)}">Revisar</button>`:q.source==='ENEM API'?`<button class="btn sm" data-action="edit-q" data-qid="${e(q.id)}">Classificar</button>`:''}</div></td></tr>`).join('')||'<tr><td colspan="7" class="muted">Nenhuma questão encontrada com esses filtros.</td></tr>'}
 </tbody></table></div>
 <div class="row admin-pagination"><button class="btn sm" data-action="prev-q" ${f.page<=1?'disabled':''}>← Anterior</button><span class="muted small">Página ${Math.min(f.page,totalPages)} de ${totalPages}</span><button class="btn sm" data-action="next-q" ${f.page>=totalPages?'disabled':''}>Próxima →</button></div></section>
 <div id="question-preview" style="margin-top:18px"></div><div id="question-editor" style="margin-top:18px"></div>
 <p class="muted small" style="margin-top:15px">A coordenação consulta as questões ENEM e IA, inclusive enunciados, alternativas e gabaritos. A curadoria global do acervo central não pode ser alterada por uma única escola. A publicação de questões escolares exige validação de direitos.</p>`;
}
async function questoes(){if(role()==='coord'&&['personal','all'].includes(state.questionsTab))state.questionsTab='school';if(role()==='prof'&&state.questionsTab==='all')return generalBank();if(['personal','school'].includes(state.questionsTab))return structuredBank();if(role()==='coord')return questionTabs()+await coordQuestionBank();if(role()==='prof'&&state.questionsTab==='mine')return myQuestions();const f=state.q;
 const mine=mySubjectOptions();if(f.area&&!mine.some(([v])=>v===f.area))f.area='';
 const data=await api('/questions?'+qstr({q:f.text,year:f.year,subject:f.area,source:'ENEM API',status:f.status,school:schoolQuery(),page:f.page,limit:12}));const stats=await api('/questions/stats?'+qstr({school:schoolQuery()}));
return head('Banco de questões','Catálogo ENEM para suas matérias, com classificação curricular autorizada por escola.',`<span class="pill blue">${data.total} questões ENEM</span>`)+questionTabs()+
 `<div class="card" style="margin-bottom:20px"><form id="question-search" class="row" style="align-items:end">
 <label class="field flex" style="min-width:160px">Palavra-chave<input name="text" placeholder="Buscar no enunciado..." value="${e(f.text)}"></label>
 ${fselect('year','Ano',[['','Todos os anos'],...Array.from({length:15},(_,i)=>[2023-i,2023-i])],f.year)}
 ${fselect('area','Disciplina atribuída',mine,f.area)}
 ${role()!=='aluno'?fselect('status','Situação',[['','Todas'],['review','Em revisão'],['published','Publicadas']],f.status):''}
 <button class="btn primary">Buscar</button></form></div>
 ${!stats.enem?`<div class="hint" style="margin-bottom:14px">Nenhuma questão ENEM foi importada e classificada para suas disciplinas nesta escola. A coordenação pode executar a importação em <b>Importação ENEM</b> e classificar os itens interdisciplinares no banco administrativo. Questões pendentes podem ser consultadas, mas não inseridas em provas até a autorização de uso.</div>`:''}
 ${data.items.length?`<div class="row spread" style="margin-bottom:13px"><span class="muted small">${data.total} resultados · página ${f.page}</span><span class="small muted">${state.selected.size} selecionada(s) para prova</span></div><div class="q-list">${data.items.map(q=>questionCard(q)).join('')}</div>
 <div class="row" style="justify-content:center;margin-top:24px"><button class="btn" data-action="prev-q" ${f.page<=1?'disabled':''}>← Anterior</button><span class="muted small">${f.page} / ${Math.ceil(data.total/12)}</span><button class="btn" data-action="next-q" ${f.page*12>=data.total?'disabled':''}>Próxima →</button></div>`:empty('Nenhuma questão encontrada','Ajuste seus filtros ou importe novas provas do ENEM pela coordenação.')}
 ${state.selected.size?`<div class="banner" style="margin-top:14px">${state.selected.size} questões prontas para compor uma prova. <button class="btn sm primary" data-action="nav" data-page="provas">Montar prova →</button></div>`:''}<div id="question-editor" style="margin-top:18px"></div>`}
async function provas(){
 const [exams,classes]=await Promise.all([api('/exams?'+qstr({school:schoolQuery()})),api('/classes?'+qstr({school:schoolQuery()}))]);
 const combos=classes.flatMap(c=>c.subjects.map(s=>({class_id:c.id,school:c.school_name,name:c.name,subject:s})));
 const comboOpts=combos.length?combos.map((c,i)=>[i,`${c.school} · ${c.name} · ${c.subject}`]):[['','Nenhuma atribuição']];
 return head('Provas e avaliações','Sorteie uma prévia, revise cada questão, altere a seleção e salve somente quando estiver satisfeito.')+
 `<div class="grid cols2 exam-columns">
 <section class="card"><div class="row spread"><h2>Prova aleatória personalizável</h2>${pill('Banco central','teal')}</div>
 <p class="muted small">Defina tópicos, tipos, dificuldade e pontuação. A seleção considera padrões das notas, questões respondidas, provas anteriores e cronograma da turma. Nada é salvo ao sortear.</p>
 <form id="random-exam-form" class="stack" style="margin-top:16px">
 ${fselect('combo','Escola · turma · disciplina',comboOpts,0)}
 ${field('title','Título da prova','text','Avaliação Bimestral','required minlength="3"')}
 <div id="random-options" class="exam-topic-picker"><span class="muted small">Carregando tópicos disponíveis…</span></div>
 <div class="formgrid">${field('count','Número de questões (2–20)','number','6','min="2" max="20" required')}${field('total_points','Valor total (pontos)','number','10','min="1" max="100" step="0.5" required')}</div>
 <div><div class="section-label">Distribuição de dificuldade</div><p class="muted small">Os percentuais são normalizados automaticamente, como no protótipo original.</p>
 <div class="formgrid exam-difficulty">${field('easy_percent','Fáceis (%)','number','40','min="0" max="100" required')}${field('medium_percent','Médias (%)','number','40','min="0" max="100" required')}${field('hard_percent','Difíceis (%)','number','20','min="0" max="100" required')}</div></div>
 <div><div class="section-label">Tipos de questão</div><div class="exam-types">
 <label><input type="checkbox" name="types" value="multipla" checked> Múltipla escolha</label>
 <label><input type="checkbox" name="types" value="vf" checked> Verdadeiro / falso</label>
 <label><input type="checkbox" name="types" value="discursiva" checked> Discursivas</label></div></div>
 <label class="exam-check"><input type="checkbox" name="focus_weak_topics" checked> Priorizar tópicos em que a turma está abaixo da média mínima</label>
 <label class="field">Instruções para o aluno<textarea name="instructions" rows="2">Leia com atenção e justifique quando solicitado.</textarea></label>
 <button class="btn primary" ${!combos.length?'disabled':''}>🎲 Sortear prévia para revisar</button>
 </form><div id="random-result" style="margin-top:15px"></div>
 <script type="application/json" id="random-combos">${JSON.stringify(combos).replace(/</g,'\\u003c')}</script>
 </section>
 <section class="card"><h2>Seleção manual e provas salvas</h2>
 <p class="muted small">Para montar sua própria seleção, marque questões publicadas no Banco de questões.</p>
 <form id="exam-form" class="stack" style="margin:18px 0">${field('title','Nome da avaliação','text','Avaliação diagnóstica','required')}
 ${fselect('combo','Turma · disciplina',comboOpts,0)}
 <p class="muted small">Questões selecionadas: <strong>${state.selected.size}</strong></p>
 <button class="btn" ${!combos.length||!state.selected.size?'disabled':''}>Salvar seleção</button></form>
 <div class="sep"></div><h3>Minhas provas</h3><div class="stack" style="margin-top:15px">${exams.map(x=>`<div class="listline"><span style="font-size:20px;color:var(--accent)">▤</span><div class="flex"><b>${e(x.title)}</b><div class="muted small">${e(x.class_name)} · ${e(x.subject)} · ${x.total} questões</div></div><button class="btn sm" data-action="open-exam" data-exam="${e(x.id)}">Abrir</button></div>`).join('')||empty('Nenhuma prova salva','Sorteie uma avaliação ou escolha questões do banco.')}</div>
 <script type="application/json" id="exam-combos">${JSON.stringify(combos).replace(/</g,'\\u003c')}</script>
 </section></div><div id="exam-view" style="margin-top:20px"></div>`;
}
async function randomOptions(){
 const form=document.getElementById('random-exam-form');const area=document.getElementById('random-options');
 if(!form||!area)return;
 const combos=JSON.parse(document.getElementById('random-combos').textContent||'[]');const c=combos[Number(form.querySelector('[name=combo]').value)];
 if(!c){area.innerHTML='<div class="hint warn">Você não possui turma ou matéria atribuída nesta escola.</div>';return;}
 area.innerHTML='<span class="muted small">Consultando tópicos da disciplina…</span>';
 try{
  const data=await api('/exam-builder/options?'+qstr({class_id:c.class_id,subject:c.subject}));
  if(!document.getElementById('random-options')||document.getElementById('random-options')!==area)return;
  const topics=data.topics.map(t=>`<label class="exam-topic"><input type="checkbox" name="topics" value="${e(t.topic)}" checked><span>${e(t.topic)}</span><small>${t.count}</small>${data.critical_topics.includes(t.topic)?'<b title="Conteúdo com nota média abaixo do mínimo">!</b>':''}</label>`).join('');
  const coverage=Object.entries(data.difficulties).map(([k,n])=>`${e(k)}: ${n}`).join(' · ');
  area.innerHTML=`<div class="row spread"><div class="section-label">Tópicos disponíveis (${data.total} questões)</div><button type="button" class="btn sm" data-action="toggle-all-topics">Marcar / desmarcar</button></div>
    <p class="muted small">${coverage} · <b>!</b> tópico crítico da turma</p>
    <div class="exam-topic-grid">${topics||'<p class="muted">Nenhuma questão validada para esta disciplina.</p>'}</div>`;
  form.querySelector('button.btn.primary').disabled=!data.total;
 }catch(ex){area.innerHTML=`<div class="error">${e(ex.message)}</div>`;}
}
async function showExam(id){
 const exam=await api('/exams/'+encodeURIComponent(id));const panel=document.getElementById('exam-view');if(!panel)return;
 state.examView=exam;state.examDraft=null;state.examEditing=null;state.examAnswers=false;
 renderExamView();panel.scrollIntoView({behavior:'smooth',block:'start'});
}
function examText(exam,withAnswers=false){
 const c=exam.exam;let out=`${c.title}\nTurma: ${c.class_id} | Disciplina: ${c.subject} | Valor: ${Number(c.total_points||10).toLocaleString('pt-BR')} pontos\n\n`;
 exam.items.forEach((q,i)=>{out+=`${i+1}. [${Number(q.points||0).toFixed(2)} pts] ${(q.context||'').trim()} ${(q.prompt||'').trim()}\n`;
 (q.alternatives||[]).forEach(a=>out+=`  ${a.letter}) ${a.text||''}\n`);
 if(withAnswers)out+=`Gabarito: ${q.correct_letter||'Em revisão'}\n`;
 out+='\n';});return out;
}
function renderExamView(){
 const exam=state.examView;if(!exam)return;
 const panel=document.getElementById('exam-view');if(!panel)return;
 const c=exam.exam;
 let config={};try{config=JSON.parse(c.configuration_json||'{}')}catch{}
 panel.innerHTML=`<section class="card exam-paper" id="prova-impressao">
 <div class="row spread exam-toolbar"><div><h2>${e(c.title)}</h2><p class="muted small">${e(c.subject)} · ${exam.items.length} questões · ${Number(c.total_points||10).toLocaleString('pt-BR')} pontos · ${c.applied_assessment?'Vinculada a '+e(c.applied_assessment):'Sem vínculo com avaliação aplicada'}</p></div>
 <div class="row">${c.creator_id===state.me.user.id?`<button class="btn" data-action="edit-saved-exam">Editar prova</button><button class="btn" data-action="link-exam">Vincular avaliação</button><button class="btn danger" data-action="delete-saved-exam">Descartar prova</button>`:''}<button class="btn" data-action="toggle-exam-answers">${state.examAnswers?'Ocultar gabarito':'Mostrar gabarito'}</button>
 <button class="btn" data-action="copy-exam">Copiar texto</button>
 <button class="btn" data-action="download-exam-word">Baixar Word</button>
 <button class="btn primary" data-action="print-exam">Imprimir</button></div></div><div id="exam-application-panel"></div>
 <div class="exam-cover"><h2>${e(c.title)}</h2><div class="exam-cover-grid">
 <span>Escola: ${e(state.me.schools.find(s=>s.id===config.school_id)?.name||'Instituição')}</span>
 <span>Turma: ${e(c.class_id)}</span><span>Disciplina: ${e(c.subject)}</span>
 <span>Valor: ${Number(c.total_points||10).toLocaleString('pt-BR')} pontos</span>
 <span>Aluno(a): __________________________________</span><span>Data: ____ / ____ / ______</span></div>
 <p>${e(config.instructions||'Leia com atenção.')}</p></div>
 ${exam.items.map((q,i)=>`<div class="exam-item"><div class="row spread"><strong>Questão ${i+1}</strong><span class="muted small">${Number(q.points||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})} ponto(s)</span></div>
 <p>${e((q.context||'')+(q.prompt?'\n'+q.prompt:''))}</p>
 <div class="exam-choices">${(q.alternatives||[]).map(a=>`<div><b>${e(a.letter)})</b> ${e(a.text||'')}</div>`).join('')}
 ${(q.media||[]).map(safeImage).join('')}</div>
 ${!(q.alternatives||[]).length&&!state.examAnswers?'<div class="answer-lines"></div><div class="answer-lines"></div><div class="answer-lines"></div>':''}
 ${state.examAnswers?`<div class="hint good"><b>Gabarito:</b> ${e(q.correct_letter||'Resposta discursiva a revisar')}</div>`:''}</div>`).join('')}</section>`;
}
function normalizeDraftPoints(){
 const draft=state.examDraft;if(!draft||!draft.items.length)return;
 const units=Math.round(Number(draft.total_points||10)*100),base=Math.floor(units/draft.items.length);
 draft.items.forEach((q,i)=>{q.points=(base+(i<units%draft.items.length?1:0))/100});
}
function captureDraftFields(){
 const d=state.examDraft;if(!d)return;
 const title=document.getElementById('draft-title'),points=document.getElementById('draft-points'),instructions=document.getElementById('draft-instructions');
 if(title)d.title=title.value;if(points)d.total_points=Number(points.value);if(instructions)d.instructions=instructions.value;
}
function showDraftPromptEditor(i,value){
 const d=state.examDraft,panel=document.getElementById('draft-replacement-'+i);
 if(!d||!d.items[i]||!panel)return;
 panel.innerHTML=`<div class="stack" style="margin-top:12px"><label class="field">Enunciado personalizado para esta prova<textarea id="draft-prompt-${i}" rows="5">${e(value??d.items[i].prompt??'')}</textarea></label><p class="muted small">A alteração vale apenas para esta prova; o banco central e o gabarito original não são alterados. Confira as alternativas.</p><button class="btn sm primary" data-action="draft-apply-prompt" data-pos="${i}">Aplicar alteração</button></div>`;
}
function renderExamDraft(){
 const draft=state.examDraft, panel=document.getElementById('exam-view');if(!panel||!draft)return;
 normalizeDraftPoints();
 panel.innerHTML=`<section class="card exam-editor"><div class="row spread"><div><span class="eyebrow">Prévia editável · ${draft.saved?'Salva':'não salva'}</span><h2>Revise antes de confirmar</h2><p class="muted small">${e(draft.personalization?.basis||'Questões do banco autorizadas para esta turma.')} ${draft.personalization?.critical_topics?.length?' · Prioridades: '+draft.personalization.critical_topics.map(e).join(', '):''}</p></div>${pill(draft.items.length+' questões','blue')}</div>
 <div class="formgrid" style="margin:17px 0"><label class="field">Nome da prova<input id="draft-title" value="${e(draft.title)}" maxlength="120"></label><label class="field">Valor total<input id="draft-points" type="number" step=".5" min="1" max="100" value="${Number(draft.total_points||10)}"></label></div>
 <label class="field">Instruções para a prova<textarea id="draft-instructions" rows="2">${e(draft.instructions||'Leia com atenção.')}</textarea></label>
 <div class="hint" style="margin:15px 0">É possível trocar, remover e reordenar questões. A prova só será armazenada ao clicar em <b>Confirmar e salvar</b>.</div>
 ${draft.items.map((q,i)=>`<article class="draft-question"><div class="row spread"><div><span class="pill blue">Questão ${i+1}</span> ${pill(q.topic||'Assunto')} <span class="muted small">${e(q.difficulty||'')}</span></div><strong>${Number(q.points||0).toLocaleString('pt-BR')} ponto(s)</strong></div>
 <h3>${e(q.title||'Questão do banco')}</h3><p class="small">${e((q.context||'')+' '+(q.prompt||'')).slice(0,800)}</p><div class="alternatives">${(q.alternatives||[]).map(a=>`<div class="alternative"><b>${e(a.letter)}</b>${e(a.text)}</div>`).join('')}</div>
 <div class="row draft-actions"><button class="btn sm" data-action="draft-edit-prompt" data-pos="${i}">Editar enunciado</button><button class="btn sm" data-action="draft-replace" data-pos="${i}">Substituir questão</button><button class="btn sm" data-action="draft-up" data-pos="${i}" ${i===0?'disabled':''}>↑ Subir</button><button class="btn sm" data-action="draft-down" data-pos="${i}" ${i===draft.items.length-1?'disabled':''}>↓ Descer</button><button class="btn sm danger" data-action="draft-remove" data-pos="${i}" ${draft.items.length<2?'disabled':''}>Remover</button></div><div class="draft-replacement" id="draft-replacement-${i}"></div></article>`).join('')}
 <div class="row exam-confirm"><button class="btn primary" data-action="save-draft" ${!draft.items.length?'disabled':''}>Confirmar e salvar prova</button><button class="btn" data-action="resort-draft" ${state.examEditing?'disabled':''}>Sortear outra prévia</button><button class="btn danger" data-action="discard-draft">Descartar prévia</button></div></section>`;
 if(state.draftPromptInEdit)showDraftPromptEditor(state.draftPromptInEdit.pos,state.draftPromptInEdit.value);
 panel.scrollIntoView({behavior:'smooth',block:'start'});
}
async function equipe(){if(role()!=='coord')return '';
const [team,classes,requests]=await Promise.all([api('/team'),api('/classes?'+qstr({school:schoolQuery()})),api('/team/join-requests')]);state.team=team;
const schoolOptions=state.me.schools.map(s=>[s.id,s.name]),selectedSchool=(schoolQuery()||schoolOptions[0]?.[0]||'');
return head('Pessoas e atribuições','A coordenação cria contas institucionais e administra apenas a própria escola.')+
 `<div class="grid cols3" style="margin-bottom:18px"><div class="card kpi"><span class="label">Professores</span><div class="num">${team.teachers.length}</div></div><div class="card kpi"><span class="label">Alunos</span><div class="num">${team.students.length}</div></div><div class="card kpi"><span class="label">Pedidos individuais</span><div class="num">${requests.length}</div></div></div>
 <section class="card" style="margin-bottom:18px"><h2>Convidar professor(a) pelo e-mail institucional</h2><p class="muted small">O convite não cria uma nova identidade automaticamente. Quem já tem conta confirma sua própria senha; o vínculo fica restrito à instituição escolhida.</p>
 <form id="school-teacher-invite" class="bank-form-grid" style="align-items:end">${fselect('school_id','Escola',schoolOptions,selectedSchool)}${field('name','Nome completo','text','','required minlength="3"')}${field('email','E-mail institucional','email','','required')}<button class="btn primary">Enviar convite</button></form><div id="teacher-invite-result"></div></section>
 <section class="card" style="margin-bottom:18px"><h2>Política de e-mail pessoal</h2><form id="school-personal-policy" class="row bank-wrap">${fselect('school_id','Escola',schoolOptions,selectedSchool)}<label class="field"><span>Permitir vínculo de e-mail pessoal verificado?</span><select name="allow_personal_email"><option value="false">Não</option><option value="true">Sim</option></select></label><button class="btn">Atualizar política</button></form></section>
 <section class="card" style="margin-bottom:18px"><div class="row spread"><div><h2>Criar conta do plano da escola</h2><p class="muted small">Somente a coordenação pode cadastrar professores, alunos ou outros coordenadores desta instituição.</p></div>${pill('Plano da Escola','blue')}</div>
 <form id="school-account-form" class="stack" style="margin-top:15px"><div class="formgrid">
 ${fselect('school_id','Instituição',schoolOptions,selectedSchool)}
 ${fselect('role','Tipo de conta',[['prof','Professor(a)'],['aluno','Aluno(a)'],['coord','Coordenação']],'prof')}
 ${field('name','Nome completo','text','','required minlength="3" maxlength="100" autocomplete="off"')}
 ${field('email','E-mail de acesso','email','','required autocomplete="off"')}
 ${field('password','Senha inicial (mínimo 10 caracteres)','password','','required minlength="10" autocomplete="new-password"')}</div>
 <p class="muted small">Informe a senha inicial por canal privado. O usuário poderá alterá-la em Meu cadastro. Nenhuma conta de outra escola será criada.</p>
 <button class="btn primary" type="submit">Criar conta escolar</button></form></section>
 ${requests.length?`<section class="card" style="margin-bottom:18px"><h2>Pedidos de vínculo de professores individuais</h2><p class="muted small">Aprovar o vínculo não concede acesso às turmas. Atribua a matéria e a turma após a aprovação.</p>
 ${requests.map(r=>`<div class="listline row spread"><div><b>${e(r.teacher_name)}</b><div class="muted small">${e(r.teacher_email)} · ${e(r.school_name)}</div></div><div class="row"><button type="button" class="btn sm" data-action="reject-affiliation" data-id="${e(r.id)}">Recusar</button><button type="button" class="btn sm primary" data-action="approve-affiliation" data-id="${e(r.id)}">Aprovar</button></div></div>`).join('')}</section>`:''}
 <div class="grid cols2"><section class="card"><h2>Atribuir professor(a)</h2><p class="muted small">Cada atribuição libera somente uma matéria na turma escolhida.</p>
 <form id="assign-form" class="stack">${fselect('teacher_id','Professor',team.teachers.length?team.teachers.map(x=>[x.id,x.name]):[['','Cadastre ou aprove um professor']], '')}
 ${fselect('class_id','Escola · turma',classes.map(c=>[c.id,`${c.school_name} · ${c.name}`]),'')}
 ${fselect('subject','Disciplina',[['Física','Física'],['Matemática','Matemática'],['Química','Química'],['Biologia','Biologia'],['História','História'],['Geografia','Geografia'],['Linguagens','Linguagens']],'Física')}
 <button class="btn primary" ${!team.teachers.length?'disabled':''}>Salvar atribuição</button></form></section>
 <section class="card"><h2>Matricular estudante</h2><p class="muted small">Selecione um aluno criado pela própria coordenação desta escola.</p>
 <form id="enroll-form" class="stack">${fselect('student_id','Estudante',team.students.length?team.students.map(x=>[x.id,x.name]):[['','Cadastre um aluno']], '')}
 ${fselect('class_id','Escola · turma',classes.map(c=>[c.id,`${c.school_name} · ${c.name}`]),'')}
 <button class="btn primary" ${!team.students.length?'disabled':''}>Matricular</button></form></section></div>
 <div class="card nopad" style="margin-top:18px"><div class="cardhead"><h2>Professores e vínculos ativos</h2></div><div class="tablewrap"><table><thead><tr><th>Professor</th><th>Escola</th><th>Turma</th><th>Disciplina</th><th></th></tr></thead><tbody>
 ${team.assignments.map(a=>`<tr><td>${e(a.teacher_name)}</td><td>${e(a.school_name)}</td><td>${e(a.class_name)}</td><td>${pill(a.subject,'blue')}</td><td><button class="btn sm danger" data-action="unassign" data-id="${e(a.id)}">Remover</button></td></tr>`).join('')||'<tr><td colspan="5">Nenhum vínculo definido.</td></tr>'}</tbody></table></div></div>
 <div class="grid cols2" style="margin-top:18px"><div class="card"><h2>Professores cadastrados</h2>${team.teachers.map(t=>{const schoolIds=(t.school_ids||'').split(',');const site=schoolIds.includes(selectedSchool)?selectedSchool:schoolIds[0];return `<div class="listline bank-wrap"><span class="avatar">${e(t.name[0])}</span><div class="flex"><b>${e(t.name)}</b><div class="muted small">${e(t.email)} · ${t.account_plan==='individual'?'Individual':'Da escola'} · ${e(state.me.schools.find(s=>s.id===site)?.name||site)}</div></div><button class="btn sm danger" data-action="end-school-link-preview" data-teacher="${e(t.id)}" data-school="${e(site)}">Encerrar vínculo com a escola</button></div>`}).join('')||empty('Nenhum professor','Convide um docente acima ou aprove um vínculo individual.')}<div id="school-link-impact"></div></div>
 <div class="card"><h2>Alunos cadastrados</h2>${team.students.map(t=>`<div class="listline"><span class="avatar">${e(t.name[0])}</span><div><b>${e(t.name)}</b><div class="muted small">${e(t.email)}</div></div></div>`).join('')||empty('Nenhum aluno','Crie a conta do aluno acima.')}</div></div>`}
async function importar(){if(role()!=='coord')return '';const [stats,jobs]=await Promise.all([api('/questions/stats?'+qstr({school:schoolQuery()})),api('/imports')]);const pending=jobs.some(j=>['running','pending'].includes(j.state));
return head('Importação ENEM','Sincronize provas reais para o banco central com controle de duplicidade e revisão.')+
 `<div class="grid cols3" style="margin-bottom:20px"><div class="card kpi"><div class="label">Questões da API ENEM</div><div class="num">${stats.enem}</div></div>
 <div class="card kpi" style="--kc:#d69863"><div class="label">Aguardando revisão</div><div class="num">${stats.review}</div></div><div class="card kpi" style="--kc:#4c9690"><div class="label">Questões publicadas</div><div class="num">${stats.published}</div></div></div>
 <div class="grid cols2"><div class="card"><h2>Sincronizar provas oficiais</h2><p class="muted small">A API externa deve estar acessível pelo servidor. Importação paginada, com retentativas em falhas temporárias.</p>
 <form id="import-form" class="stack">${fselect('year','Ano da prova',[['todos','Todos · 2009 a 2023'],...Array.from({length:15},(_,i)=>[2023-i,2023-i])],'2023')}
 <button class="btn primary" ${pending?'disabled':''}>↧ ${pending?'Importação em andamento':'Importar questões'}</button></form>
 <div class="hint warn" style="margin-top:17px">As questões importadas entram <b>em revisão</b>. Antes de publicar, valide enunciado, gabarito, imagens, disciplina e autorização de reprodução.</div></div>
 <div class="card"><h2>Histórico de importações</h2><div class="stack" style="margin-top:18px">${jobs.map(j=>`<div class="listline"><div class="flex"><b>ENEM ${e(j.year)}</b><div class="muted small">${j.imported} itens processados · ${e(j.created_at)}</div>${j.message?`<div class="small muted">${e(j.message)}</div>`:''}</div>${pill(j.state,j.state==='done'?'teal':j.state==='error'?'red':'amber')}</div>`).join('')||empty('Nenhuma sincronização realizada','Selecione um ano e inicie a importação.')}</div>
 <button class="btn sm" style="margin-top:15px" data-action="refresh-import">Atualizar situação</button></div></div>`}
async function praticarLegacy(){const [data,progress]=await Promise.all([api('/questions?'+qstr({source:'',page:state.q.page,limit:6,q:state.q.text})),api('/practice/progress')]);return head('Praticar questões','Responda questões liberadas pela coordenação e acompanhe seu progresso.')+
 `<div class="row" style="margin-bottom:18px"><div class="card kpi" style="--kc:#5368ca;min-width:190px"><div class="label">Questões respondidas</div><div class="num">${progress.n}</div></div><div class="card kpi" style="--kc:#4d988d;min-width:190px"><div class="label">Taxa de acerto</div><div class="num">${progress.accuracy}%</div></div></div><div class="q-list">${data.items.map(q=>questionCard(q,'practice')).join('')||empty('Ainda não há questões publicadas','A coordenação precisa revisar e liberar questões importadas. Veja também o acervo de demonstração.')}</div>
 <div class="row" style="justify-content:center;margin-top:20px"><button class="btn" data-action="prev-q" ${state.q.page<=1?'disabled':''}>Anterior</button>${pill('Página '+state.q.page)}<button class="btn" data-action="next-q" ${state.q.page*6>=data.total?'disabled':''}>Próxima</button></div>`}
async function desempenho(){const classes=await api('/classes');let blocks=await Promise.all(classes.map(async c=>({classInfo:c,grades:await api('/grades?'+qstr({class_id:c.id}))})));
return head('Meu desempenho','Seu histórico individual de avaliações e notas por escola e turma.')+
 `${blocks.map(({classInfo:c,grades:g})=>`<div class="card" style="margin-bottom:16px"><div class="row spread"><h2>${e(c.school_name)} · ${e(c.name)}</h2>${pill(c.grade)}</div>
 <div class="tablewrap" style="margin-top:16px"><table><thead><tr><th>Disciplina</th><th>Avaliação</th><th>Nota</th></tr></thead><tbody>${g.map(x=>`<tr><td>${e(x.subject)}</td><td>${e(x.assessment)}</td><td><b>${x.score.toFixed(1)}</b></td></tr>`).join('')||'<tr><td colspan="3">Sem notas lançadas.</td></tr>'}</tbody></table></div></div>`).join('')||empty('Ainda sem notas','Solicite à escola sua matrícula e aguarde o lançamento das avaliações.')}`}
async function perfil(){const user=state.me.user;const individual=role()==='prof'&&user.account_plan==='individual';
const [schools,affiliations]=individual?await Promise.all([api('/public/schools'),api('/affiliations')]):[[],{requests:[]}];
const personalData=role()==='prof'?await Promise.all([api('/accounts/personal-email'),api('/accounts/institutional/impact'),api('/accounts/personal/preferences')]):[[],null,null];
const studentOverview=role()==='aluno'&&state.me.schools?.length?await api('/student/dashboard?'+qstr({school:schoolQuery()||state.me.schools[0].id})):null;
const joined=new Set((state.me.schools||[]).map(x=>x.id));
return head('Meu cadastro','Dados de acesso, plano e vínculos do Cognix.')+
 (studentOverview?`<section class="card student-section" style="margin-bottom:18px"><h2>Meu retrato de aprendizagem</h2><p class="feature-teaser">Acompanhe as médias registradas por área e escolha um assunto para revisar. Seu cadastro é um ponto de partida, não um rótulo de capacidade.</p><div class="grid cols4 student-area-grid">${studentOverview.areas.map(a=>`<div class="student-plan-mini"><span class="eyebrow">${e(a.area)}</span><b style="font-size:23px">${a.average===null?'—':Number(a.average).toFixed(1)}</b><small>${a.subjects} disciplina(s) avaliadas</small></div>`).join('')}</div><div class="student-plan-mini" style="margin-top:14px"><b>Meu próximo foco</b><small>${studentOverview.topics.length?e(studentOverview.topics[0].subject+' · '+studentOverview.topics[0].topic+' — '+studentOverview.topics[0].reasons[0]):'Aguardando avaliações para indicar tópicos.'}</small><button class="btn sm" data-action="nav" data-page="meudesempenho">Ver desempenho e plano de estudo</button></div></section>`:'')+
 `<div class="grid cols2"><section class="card"><h2>Identificação</h2><form id="profile-form" class="stack" style="margin-top:18px">${field('name','Nome completo','text',user.name,'required')}
 ${field('email','E-mail cadastrado','email',user.email,'disabled')}
 <div>${pill(({prof:'Professor(a)',coord:'Coordenação',aluno:'Aluno(a)'})[user.role])}</div>
 <div class="hint">Plano: <b>${e(state.me.subscription)}</b>. A cobrança é simulada neste protótipo.</div>
 <button class="btn primary">Salvar perfil</button></form></section>
 <section class="card"><h2>Segurança da conta</h2><form id="password-form" class="stack" style="margin-top:18px">${field('current','Senha atual','password','','required')}${field('new','Nova senha (mínimo 10 caracteres)','password','','required minlength="10"')}<button class="btn">Alterar senha</button></form>
 <div class="hint warn" style="margin-top:20px">A alteração da senha encerra todas as sessões. O envio de e-mails exige SMTP configurado; a cobrança permanece simulada.</div></section></div>
 ${role()==='prof'?`<section class="card" style="margin-top:18px"><h2>Identidade e acesso pessoal</h2><p class="small muted">Seu e-mail de login e seus vínculos escolares são informações distintas. Confirme um endereço pessoal antes de vincular duas contas.</p><div class="row bank-wrap">${personalData[0].map(x=>pill(x.email,'teal')).join('')}</div>
 <form id="personal-email-request" class="row bank-wrap" style="margin-top:14px">${field('email','E-mail pessoal','email','','required')}<button class="btn">Enviar código de verificação</button></form>
 <form id="personal-email-confirm" class="row bank-wrap">${field('code','Código recebido','text','','required')}<button class="btn">Confirmar e-mail</button></form>
 <div id="personal-verify-notice"></div>
 ${user.account_plan==='school'?`<button class="btn" data-action="activate-individual-plan">Ativar plano individual com esta identidade</button><p class="muted small">Disponível somente com e-mail pessoal verificado e autorização das escolas vinculadas.</p>`:''}
 <h3 style="margin-top:22px">Preferências pessoais do acervo</h3><p class="muted small">Estas preferências pertencem ao seu cadastro, não à instituição, e podem acompanhar uma transferência autorizada.</p>
 <form id="teacher-personal-preferences" class="row bank-wrap">${field('preferred_subject','Disciplina preferida','text',personalData[2].preferred_subject||'')}${fselect('review_layout','Revisão do banco',[['detailed','Detalhada'],['compact','Compacta']],personalData[2].review_layout||'detailed')}<button class="btn">Salvar preferências</button></form>
 <h3 style="margin-top:22px">Vincular duas contas e transferir apenas itens particulares</h3><p class="small muted">Prove o acesso à segunda conta. Turmas, provas escolares, resultados e questões institucionais nunca serão transferidos.</p>
 <form id="personal-link-preview" class="row bank-wrap">${field('target_email','E-mail da conta individual verificada','email','','required')}${field('target_password','Senha da outra conta','password','','required')}<button class="btn">Ver itens elegíveis</button></form><div id="personal-link-impact"></div>
 ${user.account_plan==='individual'?`<hr><h3>Encerrar conta pessoal</h3><p class="muted small">Ação exclusiva do titular. Sua identidade e registros institucionais não são transferidos nem excluídos automaticamente.</p><button class="btn danger" data-action="personal-close-preview">Ver impacto do encerramento</button><div id="personal-close-impact"></div>`:''}
 ${user.account_plan==='school'?`<hr><h3>Encerrar acesso à conta institucional</h3><p class="small muted">Esta ação é independente do encerramento de vínculo e só pode ocorrer se a credencial for dedicada a, no máximo, uma escola, sem acervo pessoal pendente. E-mails pessoais associados a esta mesma credencial também perderiam o acesso.</p><p class="small muted">E-mails pessoais nesta credencial: ${personalData[1].verified_personal_emails_on_this_credential.map(x=>e(x.email)).join(', ')||'nenhum'}</p>${personalData[1].can_close_dedicated_credential?`<form id="institutional-account-close" class="row bank-wrap">${field('password','Confirme sua senha','password','','required')}<button class="btn danger">Encerrar acesso institucional</button></form>`:'<div class="hint warn">Encerramento indisponível nesta credencial. Confira vínculos, e-mails verificados e questões particulares pendentes.</div>'}`:''}</section>`:''}
 ${individual?`<section class="card" style="margin-top:18px"><h2>Vínculos com instituições</h2><p class="muted small">Seu cadastro é individual. Solicite acesso à escola em que leciona. A coordenação aprova o pedido e escolhe as turmas e matérias. Nenhuma matrícula é automática.</p>
 <form id="affiliation-form" class="row filter-row" style="margin-top:13px">${fselect('school_id','Solicitar vínculo escolar',schools.filter(x=>!joined.has(x.id)).map(x=>[x.id,x.name]).filter(x=>!affiliations.requests.some(r=>r.school_id===x[0]&&r.status==='pending')),'')}
 <button class="btn primary" ${!schools.some(x=>!joined.has(x.id)&&!affiliations.requests.some(r=>r.school_id===x.id&&r.status==='pending'))?'disabled':''}>Enviar pedido</button></form>
 ${(state.me.schools||[]).map(x=>`<div class="listline"><b>${e(x.name)}</b> ${pill('Vínculo ativo','teal')}</div>`).join('')}
 ${affiliations.requests.filter(x=>x.status!=='approved').map(r=>`<div class="listline"><b>${e(r.school_name)}</b> ${pill(r.status==='pending'?'Aguardando coordenação':'Pedido recusado',r.status==='pending'?'amber':'red')}</div>`).join('')}
 </section>`:''}`}
async function showClass(id){const panel=document.getElementById('detail-panel');if(!panel)return;const classes=await api('/classes');const c=classes.find(x=>x.id===id);if(!c)return;const subs=c.subjects;
if(role()==='aluno'){panel.innerHTML=`<div class="card"><h2>${e(c.name)} · ${e(c.school_name)}</h2><p class="muted">Veja seu boletim em Meu desempenho.</p></div>`;return}
const students=await api('/class/'+encodeURIComponent(id)+'/students');panel.innerHTML=`<div class="card"><div class="row spread"><h2>${e(c.name)} · ${e(c.school_name)}</h2>${pill(`${students.length} aluno(s)`)}</div>
 <p class="muted">${e(subs.join(', ')||'Sem disciplina atribuída')}</p><div class="grid cols2" style="margin-top:18px"><section><h3>Alunos matriculados</h3>${students.map(s=>`<div class="listline"><span class="avatar">${e(s.name[0])}</span>${e(s.name)}</div>`).join('')||empty('Sem alunos matriculados','A coordenação realiza as matrículas na aba Equipe.')}</section>
 <section>${role()==='coord'?`<h3>Lançar nota</h3><form id="grade-form" class="stack" style="margin-top:12px">${fselect('student_id','Aluno',students.map(s=>[s.id,s.name]),'')}
 ${fselect('subject','Disciplina',subs.map(s=>[s,s]),'')}${field('assessment','Avaliação','text','Prova 1','required')}${field('score','Nota de 0 a 10','number','7','required min="0" max="10" step="0.1"')}
 <input type="hidden" name="class_id" value="${e(id)}"><button class="btn primary" ${!students.length||!subs.length?'disabled':''}>Salvar nota</button></form>`:'<h3>Notas da turma</h3><p class="muted small">A coordenação é responsável pelo lançamento e pela correção de notas. Use a aba Notas da turma para consultar os resultados.</p>'}</section></div></div>`}
async function renderQEditor(id){
 const requestedSchool=schoolQuery() || state.me.schools[0]?.id || '';
 const q=await api('/questions/'+encodeURIComponent(id)+'/metadata?'+qstr({school:requestedSchool}));
 const el=document.getElementById('question-editor');if(!el)return;
 if(q.school_id===null){
   if(q.source!=='ENEM API'){
      el.innerHTML='<div class="hint">Acervo central somente para consulta. Esta coordenação não altera a curadoria global.</div>';return;
   }
   const eligible={'Ciências da Natureza':['Física','Química','Biologia'],
      'Matemática':['Matemática'],'Linguagens':['Linguagens','Português'],
      'Ciências Humanas':['Geografia','História']}[q.area]||[];
   const existing=q.school_classifications?.find(x=>x.school_id===requestedSchool);
   const subjects=eligible.map(x=>[x,x]);
   el.innerHTML=`<div class="card"><div class="row spread"><h2>Classificar questão ENEM para esta escola</h2>${pill(q.area||'ENEM')}</div>
   <p class="muted small">Esta classificação curricular é local à escola. Ela libera a <b>consulta</b> ao professor da matéria, sem alterar a questão central nem autorizar sua reprodução em provas.</p>
   <form id="enem-school-classification" class="stack"><input type="hidden" name="id" value="${e(q.id)}">
   ${fselect('school_id','Escola',[[requestedSchool,state.me.schools.find(x=>x.id===requestedSchool)?.name||requestedSchool]],requestedSchool)}
   ${fselect('discipline','Matéria', [['','Selecione uma matéria'],...subjects],existing?.discipline||q.discipline||'')}
   ${field('topic','Tópico curricular','text',existing?.topic||q.topic||'')}
   ${fselect('difficulty','Dificuldade pedagógica',[['','Não definida'],['fácil','Fácil'],['média','Média'],['difícil','Difícil']],existing?.difficulty||q.difficulty||'')}
   <button class="btn primary" ${!subjects.length?'disabled':''}>Salvar classificação da escola</button></form></div>`;
   el.scrollIntoView({behavior:'smooth',block:'center'});return;
 }
 el.innerHTML=`<div class="card"><div class="row spread"><h2>Revisar e classificar questão da escola</h2>${pill(q.id)}</div>
 <form id="review-form" class="stack" style="margin-top:15px"><input type="hidden" name="id" value="${e(q.id)}">
 <div class="formgrid">${fselect('status','Situação',[['review','Em revisão'],['published','Publicada'],['archived','Arquivada']],q.status)}
 ${fselect('rights_status','Direitos de reprodução',[['pending','Pendente'],['authorized','Autorização verificada'],['demo','Conteúdo original fictício']],q.rights_status)}
 ${fselect('discipline','Disciplina',[['','A classificar'],...areaOpts.slice(1)],q.discipline)}
 ${field('topic','Tópico','text',q.topic)}${fselect('difficulty','Dificuldade',[['','Não definida'],['fácil','Fácil'],['média','Média'],['difícil','Difícil']],q.difficulty)}</div>
 <label class="row small"><input type="checkbox" name="confirm" required> Conferi o gabarito, os arquivos e os direitos de uso desta questão.</label>
 <button class="btn primary">Salvar revisão</button></form></div>`;
 el.scrollIntoView({behavior:'smooth',block:'center'});
}
function formData(form){return Object.fromEntries(new FormData(form).entries())}
function bind(){root.addEventListener('change',ev=>{if(ev.target.id==='school-filter'){state.school=ev.target.value;state.selected.clear();state.minePage=1;state.mineSubject='';state.questionEditorId=null;state.questionPreviewId=null;state.minePreviewHTML='';drawApp().catch(console.error)}if(ev.target.id==='bank-collection'){state.bankCollection=ev.target.value;state.bankBatch='';renderPage().catch(console.error)}if(ev.target.closest('#random-exam-form')&&ev.target.name==='combo')randomOptions().catch(console.error)});
 root.addEventListener('submit',async ev=>{const f=ev.target;if(!f.id)return;ev.preventDefault();let data=formData(f);
 try{
  if(f.id==='bank-general-search'){
    state.allSearch={q:data.q,discipline:data.discipline,topic:data.topic,source:data.source,status:data.status,page:1};
    await renderPage();return;
  }
  if(f.id==='bank-import-text'){
    const output=await api('/bank/import/text',{collection_id:data.collection_id,text:data.text});
    state.questionsTab=data.collection_id.startsWith('personal-')?'personal':'school';state.bankCollection=data.collection_id;state.bankBatch=output.batch_id;
    alertUser(output.resumed?'Lote existente retomado, sem duplicar questões.':'Questões salvas como rascunhos. Revise o lote.');await renderPage();return;
  }
  if(f.id==='bank-import-file'){
    const file=f.querySelector('input[type="file"]')?.files?.[0];if(!file)throw Error('Selecione um DOCX ou PDF.');
    if(file.size>10*1024*1024)throw Error('Arquivo maior que 10 MB.');
    const url='/api/bank/import/file?'+qstr({collection_id:data.collection_id,filename:file.name});
    const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream'},body:file});
    const output=await response.json().catch(()=>({detail:'Falha ao importar arquivo.'}));
    if(!response.ok)throw Error(output.detail||'Não foi possível importar.');
    state.questionsTab=data.collection_id.startsWith('personal-')?'personal':'school';state.bankCollection=data.collection_id;state.bankBatch=output.batch_id;
    alertUser(output.resumed?'Lote retomado.':'Arquivo importado e questões salvas como rascunhos.');await renderPage();return;
  }
  if(f.id==='bank-search'){state.bankQ=data.q;state.bankSubject=data.discipline;state.bankTopic=data.topic;await renderPage();return}
  if(f.id==='bank-authorize-form'){
    await api('/accounts/school/questions/'+encodeURIComponent(data.qid)+'/authorize',{
      school_id:data.school_id,recipient_id:data.recipient_id,confirm:data.confirm==='on'});
    alertUser('Somente a versão autorizada foi disponibilizada.');await renderPage();return;
  }
  if(f.id==='bank-review-form'){
    const items=[...f.querySelectorAll('.bank-review-row')].map(row=>({question_id:row.dataset.qid,
      discipline:row.querySelector('[name="discipline"]').value,topic:row.querySelector('[name="topic"]').value,
      prompt:row.querySelector('[name="prompt"]').value,correct_letter:row.querySelector('[name="correct_letter"]').value,
      alternatives:['A','B','C','D','E'].map(letter=>({letter,text:row.querySelector('[name="alt-'+letter+'"]').value.trim()})).filter(a=>a.text),
      rights_confirmed:row.querySelector('[name="rights_confirmed"]').checked}));
    await api('/bank/review',{batch_id:f.dataset.batch,items});alertUser('Revisão e categorias salvas.');await renderPage();return;
  }
  if(f.id==='school-teacher-invite'){
    const out=await api('/accounts/school/invite',data);
    document.getElementById('teacher-invite-result').innerHTML=`<div class="hint" style="margin-top:12px">${out.delivery==='smtp'?'Convite enviado para o e-mail institucional.':'Modo de desenvolvimento: SMTP não configurado. Compartilhe este código de convite por canal seguro: <code>'+e(out.development_token)+'</code>'}</div>`;
    alertUser(out.delivery==='smtp'?'Convite enviado.':'Convite criado em modo de desenvolvimento.');return;
  }
  if(f.id==='school-personal-policy'){await api('/accounts/school/policy',{school_id:data.school_id,allow_personal_email:data.allow_personal_email==='true'});alertUser('Política escolar atualizada.');return}
  if(f.id==='personal-email-request'){
    const r=await api('/accounts/personal-email/challenge',{email:data.email});
    document.getElementById('personal-verify-notice').innerHTML=`<div class="hint">${r.delivery==='smtp'?'Código enviado.':'Código de desenvolvimento: <code>'+e(r.development_code)+'</code>'}</div>`;return;
  }
  if(f.id==='personal-email-confirm'){await api('/accounts/personal-email/verify',{code:data.code});alertUser('E-mail verificado.');await renderPage();return}
  if(f.id==='teacher-personal-preferences'){await api('/accounts/personal/preferences',{preferred_subject:data.preferred_subject,review_layout:data.review_layout},'PUT');alertUser('Preferências pessoais salvas.');return}
  if(f.id==='personal-link-preview'){
    const r=await api('/accounts/link/preview',data);
    const panel=document.getElementById('personal-link-impact');
    panel.innerHTML=`<div class="hint" style="margin-top:15px"><h3>Prévia da transferência</h3><p>Destino: ${e(r.target.email)}. ${r.ambiguous_legacy_count} item(ns) antigo(s) exigem revisão de propriedade; nada institucional será transferido.</p>
      ${r.eligible.map(q=>`<label class="bank-transfer-item"><input class="bank-transfer-question" type="checkbox" value="${e(q.id)}" checked><span>${e(q.discipline||'Sem disciplina')} · ${e(q.topic||q.prompt.slice(0,80))}</span></label>`).join('')||'<p>Nenhuma questão particular elegível.</p>'}
      ${r.personal_preferences?`<label class="bank-transfer-item"><input id="bank-transfer-preferences" type="checkbox" checked><span>Incluir minhas preferências pessoais (${e(r.personal_preferences.preferred_subject||'sem disciplina preferida')}). Preferências já definidas no destino serão preservadas.</span></label>`:''}
      <button class="btn primary" type="button" data-action="confirm-personal-transfer" data-challenge="${e(r.challenge)}">Confirmar itens selecionados</button></div>`;return;
  }
  if(f.id==='institutional-account-close'){
    if(!window.confirm('Encerrar acesso à credencial institucional? Sessões serão invalidadas. Registros da escola serão preservados.'))return;
    await api('/accounts/institutional/close?'+qstr({password:data.password,confirm:true}),{});state.me=null;drawAuth();alertUser('Acesso institucional encerrado.');return;
  }
  if(f.id==='personal-close-form'){
    if(!window.confirm('Encerrar sua conta individual e todas as sessões? Seus dados privados ficarão indisponíveis até recuperação administrativa.'))return;
    await api('/accounts/personal/close',{password:data.password,confirm:true});state.me=null;drawAuth();alertUser('Conta pessoal encerrada.');return;
  }
  if(f.id==='random-exam-form'){
    const combos=JSON.parse(document.getElementById('random-combos').textContent);const c=combos[Number(data.combo)];
    if(!c)throw Error('Selecione uma turma e disciplina.');
    const fd=new FormData(f);const topics=fd.getAll('topics'),types=fd.getAll('types');
    if(!topics.length)throw Error('Marque ao menos um tópico.');
    if(!types.length)throw Error('Marque ao menos um tipo de questão.');
    const payload={class_id:c.class_id,subject:c.subject,title:data.title,topics,types,
       count:Number(data.count),total_points:Number(data.total_points),
       easy_percent:Number(data.easy_percent),medium_percent:Number(data.medium_percent),hard_percent:Number(data.hard_percent),
       focus_weak_topics:fd.has('focus_weak_topics'),instructions:data.instructions};
    const out=await api('/exam-builder/preview',payload);
    state.examDraft={...out,question_edits:{}};state.examEditing=null;state.draftPromptInEdit=null;renderExamDraft();
    alertUser('Prévia pronta. Você pode editar, descartar ou confirmar para salvar.');return;
  }
  if(f.id==='llm-question-form'){
    const combos=JSON.parse(document.getElementById('llm-combos').textContent);const c=combos[Number(data.combo)];if(!c)throw Error('Selecione uma turma.');
    const out=await api('/ai/questions',{school_id:c.school_id,subject:c.subject,grade:'Ensino médio',topic:data.topic,
      difficulty:data.difficulty,count:Number(data.count),instructions:data.instructions,kind:'multipla'});
    document.getElementById('llm-output').innerHTML=`<div class="hint"><b>${e(out.message)}</b></div>`+out.questions.map(x=>`<div class="listline"><div><b>${e(x.topic||'Questão')}</b><p class="muted small">${e((x.prompt||x.context||'').slice(0,300))}</p></div></div>`).join('');return;
  }
  if(f.id==='llm-exam-form'){
    const combos=JSON.parse(document.getElementById('llm-combos').textContent);const c=combos[Number(data.combo)];if(!c)throw Error('Selecione uma turma.');
    const out=await api('/ai/exam',{school_id:c.school_id,class_id:c.class_id,subject:c.subject,title:data.title,
      topics:data.topics.split(',').map(x=>x.trim()).filter(Boolean),count:Number(data.count),difficulty:data.difficulty,
      allow_new:data.allow_new==='on'});
    document.getElementById('llm-exam-output').innerHTML=`<div class="hint"><b>${e(out.message)}</b><p>${out.count} questão(ões) · ${out.draft_questions} item(ns) a revisar</p></div>`;
    return;
  }
  if(f.id==='auth-form'){state.authError='';const path=state.authMode==='register'?'/auth/register':'/auth/login';await api(path,data);await loadApp();return}
  if(f.id==='accept-school-invite'){
    await api('/accounts/school/accept',data);state.authMode='login';drawAuth();alertUser('Vínculo ativado. Entre com seu e-mail e senha.');return;
  }
  if(f.id==='mine-filter'){state.mineSubject=data.subject;state.minePage=1;await renderPage();return}
  if(f.id==='mine-generate'){
    if(!data.collection_id)throw Error('Selecione o acervo em Salvar em.');
    const out=await api('/ai/questions',{collection_id:data.collection_id,subject:data.subject,grade:'Ensino médio',
      topic:data.topic,difficulty:data.difficulty,count:Number(data.count),instructions:data.instructions,kind:'multipla'});
    if(out.generated){state.questionsTab=data.collection_id.startsWith('personal-')?'personal':'school';state.bankCollection=data.collection_id;state.bankBatch=out.batch_id;alertUser(out.message);await renderPage()}
    else document.getElementById('mine-output').innerHTML=`<div class="hint" style="margin-top:16px">${e(out.message)}<br>Exemplos selecionados: ${out.questions.length}. Para gerar novos rascunhos, configure GEMINI_API_KEY no servidor.</div>`;
    return;
  }
  if(f.id==='question-search'){state.q={...state.q,...data,page:1};await renderPage();return}
  if(f.id==='school-account-form'){
    const created=await api('/team/accounts',data);
    alertUser(`Conta escolar criada para ${created.name}. Compartilhe a senha inicial em privado.`);
    await renderPage();return;
  }
  if(f.id==='affiliation-form'){
    if(!data.school_id)throw Error('Selecione uma escola.');
    const out=await api('/affiliations/request',data);alertUser(out.message);await renderPage();return;
  }
  if(f.id==='assign-form'){await api('/team/assign',data);alertUser('Vínculo salvo com sucesso.');await renderPage();return}
  if(f.id==='enroll-form'){await api('/team/enroll',data);alertUser('Matrícula realizada.');await renderPage();return}
  if(f.id==='exam-form'){const c=JSON.parse(document.getElementById('exam-combos').textContent)[+data.combo];if(!c)throw Error('Selecione uma turma e disciplina.');await api('/exams',{title:data.title,class_id:c.class_id,subject:c.subject,question_ids:[...state.selected]});state.selected.clear();alertUser('Prova salva.');await renderPage();return}
  if(f.id==='import-form'){await api('/imports/enem?'+qstr({year:data.year}),{});alertUser('Solicitação registrada. Atualize para acompanhar.');await renderPage();return}
  if(f.id==='enem-school-classification'){
    if(!data.discipline)throw Error('Selecione a disciplina para classificar a questão.');
    const out=await api('/questions/'+encodeURIComponent(data.id)+'/school-classification',
      {school_id:data.school_id,discipline:data.discipline,topic:data.topic,difficulty:data.difficulty});
    alertUser(out.message);await renderPage();return;
  }
  if(f.id==='review-form'){if(data.confirm!=='on')throw Error('Confirme a revisão editorial.');await api('/questions/'+encodeURIComponent(data.id),{status:data.status,rights_status:data.rights_status,discipline:data.discipline,topic:data.topic,difficulty:data.difficulty},'PATCH');state.questionEditorId=null;delete state.formDrafts[draftKey('questoes',state.school,'review-form')];alertUser('Questão revisada e salva.');await renderPage();return}
  if(f.id==='profile-form'){await api('/me',{name:data.name},'PATCH');alertUser('Cadastro atualizado.');await loadApp();return}
  if(f.id==='password-form'){await api('/me/password',data);alertUser('Senha alterada. Faça login novamente.');state.me=null;drawAuth();return}
  if(f.id==='grade-form'){data.score=Number(data.score);await api('/grades',data);alertUser('Nota registrada com sucesso.');await showClass(data.class_id);return}
 }catch(err){if(f.id==='auth-form'){state.authError=err.message;drawAuth()}else alertUser(err.message,false)}
 });
 root.addEventListener('click',async ev=>{const btn=ev.target.closest('[data-action]');if(!btn)return;const action=btn.dataset.action;try{
 if(action==='end-school-link-preview'){
    const r=await api('/accounts/school/'+encodeURIComponent(btn.dataset.school)+'/members/'+encodeURIComponent(btn.dataset.teacher)+'/impact');
    const panel=document.getElementById('school-link-impact');
    panel.innerHTML=`<div class="hint warn"><h3>${e(r.professor.name)} · impacto do desligamento</h3><p>${e(r.impact)}</p><p>Outros vínculos: ${r.other_school_links.length}. Conta individual separada e verificada: ${r.verified_personal_access?'sim':'não'}. E-mail pessoal na própria credencial institucional: ${r.personal_alias_on_this_credential?'sim':'não'}. Questões particulares ainda nesta credencial: ${r.personal_questions_remaining}.</p><div class="row bank-wrap"><button class="btn danger" data-action="confirm-end-school-link" data-school="${e(btn.dataset.school)}" data-teacher="${e(btn.dataset.teacher)}">Confirmar encerramento do vínculo</button>${r.may_close_dedicated_account?`<button class="btn danger" data-action="close-dedicated-account" data-school="${e(btn.dataset.school)}" data-teacher="${e(btn.dataset.teacher)}">Encerrar acesso à conta institucional</button>`:''}</div></div>`;return;
 }
 if(action==='confirm-end-school-link'){
    await api('/accounts/school/'+encodeURIComponent(btn.dataset.school)+'/members/'+encodeURIComponent(btn.dataset.teacher)+'/end',{confirm:true});alertUser('Vínculo encerrado. Registros preservados.');await renderPage();return;
 }
 if(action==='close-dedicated-account'){
    if(!window.confirm('Essa credencial escolar dedicada será desativada, e suas sessões encerradas. Provas e resultados permanecerão na escola. Confirmar?'))return;
    await api('/accounts/school/'+encodeURIComponent(btn.dataset.school)+'/members/'+encodeURIComponent(btn.dataset.teacher)+'/close-institutional-access',{confirm:true});
    alertUser('Conta institucional dedicada encerrada; registros preservados.');await renderPage();return;
 }
 if(action==='confirm-personal-transfer'){
    const ids=[...document.querySelectorAll('#personal-link-impact .bank-transfer-question:checked')].map(x=>x.value);
    const r=await api('/accounts/link/confirm',{challenge:btn.dataset.challenge,question_ids:ids,
      include_personal_preferences:!!document.getElementById('bank-transfer-preferences')?.checked,confirm:true});
    alertUser(`${r.transferred} item(ns) particular(es) transferidos com registro de auditoria.`);await renderPage();return;
 }
 if(action==='activate-individual-plan'){await api('/accounts/personal/activate',{});alertUser('Plano individual ativado, preservando sua identidade.');await loadApp();return}
 if(action==='personal-close-preview'){
    const impact=await api('/accounts/personal/close-impact');
    document.getElementById('personal-close-impact').innerHTML=`<div class="hint warn"><p>${e(impact.warning)}</p><p>Questões particulares: ${impact.personal_questions}. Vínculos escolares ativos: ${impact.active_school_links.length}.</p><form id="personal-close-form" class="row bank-wrap">${field('password','Confirme sua senha','password','','required')}<button class="btn danger">Confirmar encerramento pessoal</button></form></div>`;return;
 }
 if(action==='bank-open-batch'){state.bankBatch=btn.dataset.batch;await renderPage();return}
 if(action==='bank-close-batch'){state.bankBatch='';await renderPage();return}
 if(action==='bank-recategorize'){const r=await api('/bank/batches/'+encodeURIComponent(btn.dataset.batch)+'/categorize',{});alertUser('Sugestões atualizadas ('+r.origin+'). Revisões confirmadas preservadas.');await renderPage();return}
 if(action==='bank-preview'){
    const q=await api('/questions/'+encodeURIComponent(btn.dataset.qid));
    const el=document.getElementById('bank-preview-panel');if(el){el.innerHTML='<div class="card" style="margin-top:12px"><div class="row spread"><h3>Questão completa</h3><button class="btn sm" data-action="bank-close-preview">Fechar</button></div>'+questionCard(q,'preview')+'</div>';el.scrollIntoView({block:'nearest'})}
    return;
 }
 if(action==='bank-close-preview'){document.getElementById('bank-preview-panel').innerHTML='';return}
 if(action==='bank-authorize-preview'){
    const school=state.bankCollection.replace(/^school-/,'');
    const recipients=await api('/accounts/school/'+encodeURIComponent(school)+'/external-recipients');
    const el=document.getElementById('bank-preview-panel');
    el.innerHTML=`<div class="hint"><h3>Reutilização externa · versão autorizada</h3><p>O item e suas avaliações permanecem na escola. A conta destinatária recebe só uma referência congelada.</p><form id="bank-authorize-form" class="stack"><input type="hidden" name="school_id" value="${e(school)}"><input type="hidden" name="qid" value="${e(btn.dataset.qid)}">${fselect('recipient_id','Professor com conta individual verificada',recipients.map(x=>[x.id,x.name+' · '+x.email]),'')}<label class="small"><input type="checkbox" name="confirm" required> Confirmo autorização específica desta questão</label><button class="btn primary" ${!recipients.length?'disabled':''}>Conceder autorização</button></form></div>`;return;
 }
 if(action==='mode-login'||action==='mode-register'){state.authMode=action==='mode-login'?'login':'register';state.authError='';drawAuth();return}
 if(action==='retry-connection'){try{await loadApp()}catch(err){drawOffline(err.message)}return}
 if(action==='retry-page'){await renderPage();return}
 if(action==='plan-individual'||action==='plan-school'){
    state.signupPlan=action==='plan-individual'?'individual':'school';state.authError='';drawAuth();return;
 }
 if(action==='approve-affiliation'||action==='reject-affiliation'){
    const decision=action==='approve-affiliation'?'approved':'rejected';
    const answer=await api('/team/join-requests/'+encodeURIComponent(btn.dataset.id),{decision});
    alertUser(answer.message);await renderPage();return;
 }
 if(action==='mobile-menu'){document.getElementById('shell')?.classList.toggle('menu-open');return}
 if(action==='nav'){
   if(!navs().some(x=>x[0]===btn.dataset.page)&&!['escolas','turmas'].includes(btn.dataset.page))throw Error('Área não disponível para este perfil.');
   state.page=btn.dataset.page;state.q.page=1;await drawApp();return}
 if(action==='logout'){await api('/auth/logout',{});state.me=null;state.draftOwner=null;state.formDrafts={};state.examDraft=null;state.examView=null;state.draftPromptInEdit=null;state.selected.clear();state.questionEditorId=null;state.questionPreviewId=null;state.minePreviewHTML='';drawAuth();return}
 if(action==='school'){state.school=btn.dataset.school;state.page='turmas';await drawApp();return}
 if(action==='show-class'){await showClass(btn.dataset.class);return}
 if(action==='refresh-import'){await renderPage();return}
 if(action==='clear-q'){state.q={text:'',year:'',area:'',subject:'',topic:'',difficulty:'',source:'',status:'',rights_status:'',creator_id:'',scope:'',page:1};delete state.formDrafts[draftKey('questoes',state.school,'question-search')];await renderPage();return}
 if(action==='clear-bank-general'){state.allSearch={q:'',discipline:'',topic:'',source:'',status:'',page:1};await renderPage();return}
 if(action==='probe-llm'){
   const target=document.getElementById('llm-check');if(target)target.textContent='Verificando conexão real com o modelo...';
   try{const res=await api('/ai/probe',{});if(target)target.textContent=res.message+' Modelo: '+res.model;alertUser(res.message)}
   catch(err){if(target)target.textContent='Falha no teste: '+err.message;alertUser('Conexão com IA não validada: '+err.message)}return;
 }
 if(action==='general-prev'||action==='general-next'){
   state.allSearch.page=Math.max(1,state.allSearch.page+(action==='general-next'?1:-1));await renderPage();return;
 }
 if(action==='view-q'){const q=await api('/questions/'+encodeURIComponent(btn.dataset.qid)+'?'+qstr({school:schoolQuery()}));const el=document.getElementById('question-preview');if(el){state.questionPreviewId=btn.dataset.qid;el.innerHTML='<div class="row spread" style="margin-bottom:12px"><h2>Visualização da questão</h2><button class="btn sm" data-action="close-q">Fechar</button></div>'+questionCard(q,'preview');el.scrollIntoView({behavior:'smooth',block:'start'})}return}
 if(action==='close-q'){state.questionPreviewId=null;document.getElementById('question-preview')?.replaceChildren();return}
 if(action==='question-tab'){state.questionsTab=btn.dataset.tab;state.minePage=1;await renderPage();return}
 if(action==='mine-prev'||action==='mine-next'){state.minePage=Math.max(1,state.minePage+(action==='mine-next'?1:-1));await renderPage();return}
 if(action==='mine-open'){
   const q=await api('/questions/'+encodeURIComponent(btn.dataset.qid)+'?'+qstr({school:schoolQuery()}));
   const panel=document.getElementById('mine-preview');if(!panel)return;
   panel.innerHTML=`<div class="card" style="margin-top:18px"><h3>${e(q.title)}</h3>${q.context?`<p>${e(q.context)}</p>`:''}<p>${e(q.prompt)}</p><div class="alternatives">${(q.alternatives||[]).map(a=>`<div class="alternative"><b>${e(a.letter)}</b>${e(a.text)}</div>`).join('')}</div><p class="muted small">Gabarito: ${e(q.correct_letter||'não informado')} · ${e(q.source)}</p></div>`;state.minePreviewHTML=panel.innerHTML;
   panel.scrollIntoView({behavior:'smooth',block:'nearest'});return;
 }
 if(action==='prev-q'||action==='next-q'){state.q.page=Math.max(1,state.q.page+(action==='next-q'?1:-1));await renderPage();return}
 if(action==='select-q'){state.selected.has(btn.dataset.qid)?state.selected.delete(btn.dataset.qid):state.selected.add(btn.dataset.qid);await renderPage();return}
 if(action==='edit-q'){state.questionEditorId=btn.dataset.qid;await renderQEditor(btn.dataset.qid);return}
 if(action==='unassign'){if(!confirm('Remover este vínculo docente?'))return;await api('/team/assign/'+encodeURIComponent(btn.dataset.id),{},'DELETE');alertUser('Vínculo removido.');await renderPage();return}
 if(action==='toggle-all-topics'){
   const boxes=[...document.querySelectorAll('#random-options input[name=topics]')];
   const checked=boxes.every(x=>x.checked);boxes.forEach(x=>x.checked=!checked);return;
 }
 if(action==='save-draft'){
   const d=state.examDraft;if(!d)throw Error('Nenhuma prévia para salvar.');
   captureDraftFields();d.title=d.title.trim();
   if(d.title.length<3||!d.total_points||d.total_points>100)throw Error('Informe título e pontuação válidos.');
   const payload={class_id:d.class_id,subject:d.subject,title:d.title,question_ids:d.items.map(x=>x.id),
     total_points:d.total_points,instructions:d.instructions,question_edits:d.question_edits||{}};
   const out=state.examEditing?await api('/exams/'+encodeURIComponent(state.examEditing),payload,'PATCH'):await api('/exams',payload);
   state.examDraft=null;state.examEditing=null;state.draftPromptInEdit=null;
   alertUser('Prova confirmada e salva.');await renderPage();await showExam(out.id);return;
 }
 if(action==='discard-draft'){
   state.examDraft=null;state.examEditing=null;state.draftPromptInEdit=null;
   document.getElementById('exam-view')?.replaceChildren();
   alertUser('Prévia descartada. Nenhuma alteração foi salva.');return;
 }
 if(action==='resort-draft'){
   document.getElementById('random-exam-form')?.requestSubmit();return;
 }
 if(action==='draft-up'||action==='draft-down'||action==='draft-remove'){
   const d=state.examDraft;if(!d)return;
   captureDraftFields();
   const i=Number(btn.dataset.pos),direction=action==='draft-up'?-1:1;
   if(action==='draft-remove'){const removed=d.items.splice(i,1)[0];delete d.question_edits[removed.id]}
   else if(d.items[i+direction]){[d.items[i],d.items[i+direction]]=[d.items[i+direction],d.items[i]]}
   state.draftPromptInEdit=null;
   renderExamDraft();return;
 }
 if(action==='draft-edit-prompt'){
   const d=state.examDraft;if(!d)return;
   const i=Number(btn.dataset.pos);
   state.draftPromptInEdit={pos:i,value:d.items[i].prompt||''};showDraftPromptEditor(i);return;
 }
 if(action==='draft-apply-prompt'){
   const d=state.examDraft;if(!d)return;
   captureDraftFields();
   const i=Number(btn.dataset.pos),prompt=document.getElementById('draft-prompt-'+i)?.value.trim()||'';
   if(prompt.length<15)throw Error('O enunciado precisa ter pelo menos 15 caracteres.');
   const q=d.items[i];q.prompt=prompt;d.question_edits[q.id]=prompt;state.draftPromptInEdit=null;renderExamDraft();return;
 }
 if(action==='draft-replace'){
   const d=state.examDraft;if(!d)return;
   captureDraftFields();
   const i=Number(btn.dataset.pos),panel=document.getElementById('draft-replacement-'+i);
   const available=await api('/exam-builder/candidates?'+qstr({class_id:d.class_id,subject:d.subject,current_id:d.items[i].id}));
   const taken=new Set(d.items.map(x=>x.id));
   const candidates=available.items.filter(x=>!taken.has(x.id));
   panel.innerHTML=candidates.length?`<div class="row" style="margin-top:10px"><label class="field flex">Questão substituta<select id="draft-candidate-${i}">${opts(candidates.map(x=>[x.id,(x.topic||'Geral')+' · '+(x.title||x.id)]),'')}</select></label><button class="btn sm primary" data-action="draft-use-replacement" data-pos="${i}">Usar esta questão</button></div>`:'<p class="muted small">Não há outra questão autorizada nesta matéria.</p>';
   return;
 }
 if(action==='draft-use-replacement'){
   const d=state.examDraft;if(!d)return;
   captureDraftFields();
   const i=Number(btn.dataset.pos),id=document.getElementById('draft-candidate-'+i)?.value;
   if(!id)throw Error('Escolha uma questão substituta.');
   const replacement=await api('/questions/'+encodeURIComponent(id)+'?'+qstr({school:d.school_id}));
   delete d.question_edits[d.items[i].id];
   d.items[i]={...replacement,points:d.items[i].points};state.draftPromptInEdit=null;renderExamDraft();return;
 }
 if(action==='open-exam'){await showExam(btn.dataset.exam);return}
 if(action==='edit-saved-exam'){
   const view=state.examView;if(!view||view.exam.creator_id!==state.me.user.id)return;
   let config={};try{config=JSON.parse(view.exam.configuration_json||'{}')}catch{}
   state.examEditing=view.exam.id;state.draftPromptInEdit=null;
   state.examDraft={saved:true,title:view.exam.title,class_id:view.exam.class_id,subject:view.exam.subject,
      total_points:view.exam.total_points||10,school_id:config.school_id||schoolQuery()||state.me.schools[0]?.id,
      instructions:config.instructions||'Leia com atenção.',question_edits:config.question_edits||{},
      items:view.items.map(x=>({...x}))};
   renderExamDraft();return;
 }
 if(action==='link-exam'){
   const view=state.examView;if(!view||view.exam.creator_id!==state.me.user.id)return;
   const rows=await api('/pedagogy/assessments?'+qstr({class_id:view.exam.class_id,subject:view.exam.subject}));
   const panel=document.getElementById('exam-application-panel');if(!panel)return;
   panel.innerHTML=rows.length?`<div class="hint" style="margin:14px 0"><b>Vincular prova à avaliação registrada</b><p class="muted small">A coordenação cadastra as avaliações e lança notas. Quando houver notas, o desempenho desta prova poderá alimentar o diagnóstico.</p><div class="row"><label class="field flex">Avaliação<select id="exam-link-assessment">${opts(rows.map(x=>[x.name,x.name]),view.exam.applied_assessment||'')}</select></label><button class="btn primary" data-action="confirm-link-exam">Vincular</button></div></div>`:'<div class="hint warn">Não há avaliações cadastradas nesta turma e disciplina. Peça à coordenação para criar a avaliação em Lançar notas.</div>';
   return;
 }
 if(action==='confirm-link-exam'){
   const id=state.examView?.exam?.id,assessment=document.getElementById('exam-link-assessment')?.value;
   if(!id||!assessment)throw Error('Escolha uma avaliação.');
   await api('/exams/'+encodeURIComponent(id)+'/link-assessment',{assessment});
   alertUser('Prova vinculada. As notas dessa avaliação serão consideradas nos diagnósticos.');
   await showExam(id);return;
 }
 if(action==='delete-saved-exam'){
   const view=state.examView;if(!view||view.exam.creator_id!==state.me.user.id)return;
   if(!confirm('Excluir definitivamente esta prova salva? Essa ação não altera as notas dos alunos.'))return;
   await api('/exams/'+encodeURIComponent(view.exam.id),{},'DELETE');
   state.examView=null;state.examDraft=null;state.examEditing=null;
   alertUser('Prova excluída.');await renderPage();return;
 }
 if(action==='toggle-exam-answers'){state.examAnswers=!state.examAnswers;renderExamView();return}
 if(action==='copy-exam'){if(state.examView){await navigator.clipboard.writeText(examText(state.examView,state.examAnswers));alertUser('Texto copiado.')}return}
 if(action==='download-exam-word'){
   if(!state.examView)return;
   const id=encodeURIComponent(state.examView.exam.id);
   const r=await fetch('/api/exams/'+id+'/docx?answers='+(state.examAnswers?'1':'0'),{credentials:'same-origin'});
   if(!r.ok){let er=await r.json().catch(()=>({detail:'Falha ao gerar Word'}));throw Error(er.detail)}
   const blob=await r.blob();const u=URL.createObjectURL(blob);const a=document.createElement('a');
   a.href=u;a.download='Cognix-Prova-'+id.slice(0,8)+'.docx';document.body.appendChild(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(u),2000);return;
 }
 if(action==='print-exam'){window.print();return}
 if(action==='answer'){const id=btn.dataset.qid;const chosen=document.querySelector(`input[name="answer-${CSS.escape(id)}"]:checked`);if(!chosen){alertUser('Selecione uma alternativa.');return}const ans=await api('/practice/answer',{question_id:id,letter:chosen.value});const output=document.getElementById('answer-result-'+id);if(output)output.innerHTML=ans.correct?pill('Resposta correta!','teal'):pill('Gabarito: '+ans.correct_letter,'red');btn.disabled=true;return}
 }catch(err){alertUser(err.message,false)}})
}
async function drawApp(){captureWorkspace();root.innerHTML=shell();await renderPage()}
const pedagogy=createPedagogy({state,api,e,head,pill,empty,role,alertUser,drawApp,renderPage});
async function start(){bind();pedagogy.bind(root);try{await loadApp()}catch(err){if(err.message.startsWith('Conexão'))drawOffline(err.message);else drawAuth()}}
start();
