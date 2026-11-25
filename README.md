# Cognix v10.0 — Banco de questões recuperável e vínculos docentes seguros

**Protótipo local de desenvolvimento.** Esta versão continua o Cognix v9.9 e mantém o HTML original em `docs/legado/`, para comparação. As migrações do v10.0 são aditivas e preservam os dados anteriores. **Leia `docs/RELATORIO-V10.md` antes de colocar em produção.**

## Início rápido (Windows)

1. Faça uma **cópia de segurança** de `data/cognix.sqlite3` se alterou informações em uma versão anterior.
2. Extraia **todo** o ZIP para `Documentos`, abra a pasta `Cognix-v10.0` e dê dois cliques em **`iniciar-cognix.bat`**.
3. O script procura Python 3.11+, cria o ambiente virtual, instala dependências se necessário e abre o navegador na primeira porta disponível entre **8000 e 8100**. O endereço escolhido aparece na janela preta.
4. **Não feche a janela preta** enquanto estiver utilizando o Cognix.
5. Logins e senhas *somente para testes* estão em `data/ACESSOS-DEMO-LOCAL.txt` (não publicar).

Alternativa no terminal PowerShell, dentro da pasta do projeto:

```powershell
py -m pip install -r requirements.txt
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Ao atualizar:** se já cadastrou dados, faça backup e **copie o seu banco `data/cognix.sqlite3` da pasta anterior para a pasta da v10.0 ANTES de executar o programa**. Se utilizou o armazenamento de anexos na v10, copie também `data/question_uploads/`. Não substitua seu banco real pelo banco demonstrativo incluído no pacote.

## Novidades da v10.0 (prioridade P0)

- **Banco de questões:** uma tela com Meu acervo, Acervo da escola e ENEM. Importe texto colado, DOCX e PDF com camada de texto, com um campo explícito **Salvar em**. Cada lote e posição ficam registrados para retomada idempotente.
- **Revisão:** rascunhos, conteúdo extraído, campos pendentes, imagens identificadas, sugestão heurística ou de IA identificada, correção de enunciado/alternativas/gabarito, confirmação de tópicos estáveis e direitos. IA indisponível não apaga rascunhos nem altera categorias confirmadas.
- **Provas:** cada questão salva em uma prova recebe um instantâneo do conteúdo e uma versão. Os exames anteriores à migração recebem instantâneo do **estado existente no momento da migração**, pois revisões históricas já perdidas não podem ser recriadas.
- **Contas:** convites institucionais, e-mail pessoal verificado, identidade desvinculada da credencial, vinculação de contas mediante prova de ambas, prévia e transferência apenas dos itens particulares selecionados, preservação de categorias e preferências pessoais confirmadas, trilha de auditoria e ações separadas para revogar vínculo, encerrar acesso escolar dedicado e encerrar conta pessoal.
- **Segurança:** o acervo particular não é acessível à coordenação da escola; itens escolares só são publicados com confirmação de direitos. O DOCX/PDF original é propriedade do lote e **nunca acompanha a transferência isolada de uma questão**.
- **Recuperação:** `scripts/backup_restore_v10.py` inclui SQLite e os arquivos originais/imagens e valida restauração isolada (integridade de hashes e chaves estrangeiras).

### Configuração de convites por e-mail

Para envio real de convites e códigos, configure `COGNIX_SMTP_HOST`, `COGNIX_SMTP_FROM`, `COGNIX_SMTP_PORT` (padrão 587) e, se necessário, `COGNIX_SMTP_USER`/`COGNIX_SMTP_PASSWORD`. Sem SMTP, o endpoint recusa envios em implantação normal. **Apenas em testes locais**, `COGNIX_DEV_INVITES=1` permite copiar códigos manualmente na interface, com indicação explícita de que o e-mail não foi enviado. Nunca utilize esse modo em servidor público.

### Cópia e restauração testável

```powershell
py scripts/backup_restore_v10.py backup --output .\backup-cognix-v10.zip
py scripts/backup_restore_v10.py restore --archive .\backup-cognix-v10.zip --to .\restauracao-isolada
```

O destino deve ser novo, para impedir substituição acidental. Backup e restauração devem ser agendados e testados regularmente pelo responsável pela implantação; o protótipo não agenda tarefas automaticamente.

### Histórico da v9.9

## O que mudou na v9.9

- **Assistente da próxima aula:** no painel docente, o botão **Preparar revisão** utiliza o horário já cadastrado, os tópicos efetivamente observados e o banco autorizado para oferecer uma sequência de atividades individuais. Não forma grupos de revisão. O plano é **editável** e só altera **Minha semana** depois de o professor confirmar **Salvar**.
- **Diagnóstico rápido ligado à aula:** o botão **Preparar diagnóstico rápido (3 questões)** abre o montador de provas com a turma, disciplina e o tópico de atenção pré-selecionados. Continua sendo um rascunho: o professor decide quais questões aproveitar, editar ou descartar.
- **Caderno de erros por alternativa:** no painel unificado de desempenho, quando há turma e tópico selecionados, o professor pode ver questões efetivamente respondidas no Cognix, taxas por tentativa e alternativas incorretas mais escolhidas. Pode registrar uma **hipótese pedagógica**, identificada como interpretação humana. Não há inferência automática da causa do erro, nem leitura de gabarito físico.
- **Devolutiva individual revisável:** em **Estudantes para acompanhamento**, o botão **Preparar devolutiva** cria um rascunho respeitoso a partir dos tópicos observados. O texto pode ser editado e copiado; o sistema **não envia mensagens automaticamente**.
- **Relatório pedagógico CSV:** exportação autorizada por turma e disciplina, com tópicos, médias e estudantes para acompanhamento, preparada para evitar fórmulas interpretadas a partir de nomes digitados na planilha.
- **Lógica e isolamento revisados:** médias de atenção e de aprovação respeitam a configuração da escola, sem limiar fixo de 6,0. Não se atribui artificialmente a nota de uma prova com múltiplos tópicos a cada tópico: agora a coordenação pode informar resultados específicos por assunto. As análises descartam registros fora da matrícula ou sem avaliação correspondente, e o caderno de erros filtra somente as respostas da turma, disciplina, escola e tópico selecionados. Médias ausentes não contam como zero na visão institucional.
- **Layout:** ajustes de margens, espaçamento interno, responsividade dos formulários e cartões pedagógicos no fundo escuro.

**Importante — leitura de gabaritos por máquina:** nesta versão ela foi **somente idealizada**, não implementada. O estudo de viabilidade, fluxo proposto, modelo futuro de dados, controles de erro e plano piloto estão em `docs/CONCEITO-LEITURA-DE-GABARITOS.md`. Não há rota de upload, reconhecimento óptico ou correção de folha física no sistema.

**Verificação:** testes automatizados de API e regras de autorização, persistência de planejamento, lançamento de notas por tópico, critérios institucionais e filtragem do caderno de erros; checagem sintática dos módulos JavaScript. Os testes não substituem a verificação visual no Windows e um piloto com educadores.

**Correção de inicialização da v9.5.1:** a versão anterior interpretava qualquer falha na verificação TCP como porta ocupada. Agora o processo verifica diretamente a possibilidade de vincular a porta (`bind`), procura outra até a 8100 quando necessário e mostra o erro real no console. Entradas `TIME_WAIT` no `netstat` com PID 0 não representam, por si só, um servidor ativo. A execução no Windows deve ser validada no computador do usuário.

## O que mudou na v9.8

- **Trilha ENEM pessoal:** o aluno da 3ª série escolhe objetivo, horas por semana, **dias disponíveis**, modalidade de estudo (**teoria e questões, questões ou revisão guiada**) e até **três conteúdos para priorizar**. Pode mudar as metas semanais por tópico. As escolhas são gravadas no banco e consideradas na ordenação de prioridades e na distribuição de blocos de 50 minutos. Na visão do professor/coordenação, a trilha continua geral da turma por padrão e permite selecionar um aluno.
- **Vocação à maneira do HTML:** interesses são apresentados como opções agrupadas e legíveis, incluindo disciplinas favoritas, curiosidades, valores e ambientes de trabalho. Permite explicar um problema que deseja resolver, ajustar a importância relativa das notas, explorar **nove famílias de cursos**, entender os motivos de cada sugestão, marcar/desmarcar interesse e relacionar carreiras com tópicos de revisão. **As notas não são usadas para rotular aptidão.** Essas sugestões não substituem orientação profissional.
- **Notas da escola com projeção:** o item independente **Quanto preciso tirar** deixou o menu; agora cada disciplina inclui a opção **Projetar nota final**, com campos de simulação das avaliações pendentes e cálculo ponderado imediato, sem gravar valores fictícios. As notas registradas continuam intactas.
- **Cadastro e início do aluno baseados na aprendizagem:** resumos com médias observadas por **Exatas, Natureza, Humanas e Linguagens**, assuntos para acompanhamento, razões dessas prioridades, passos práticos e plano de estudos. Uma área sem avaliação é exibida como **sem dados**, não como baixa capacidade.
- **Explicações a um clique:** títulos acompanhados de um texto breve, seguidos de **Saiba mais** com evidências, interpretação e limites. O layout escuro passou a usar cartões consistentes, campos amplos, chips de interesse e grades adaptáveis para celular.
- **Mapa de prioridades docente:** além das quantidades de prioridade alta/média/baixa, cada tópico mostra **por que** foi destacado (histórico, queda e notas), **quem** precisa de acompanhamento na turma (nomes e médias somente no acesso autorizado), uma **sugestão pedagógica concreta** e botão de abrir o diagnóstico detalhado. A tabela longitudinal completa fica recolhida em **Saiba mais** para evitar redundância.

**Verificação:** incluímos testes para preferências persistidas, marcação de carreiras, agrupamento de áreas, motivos dos tópicos e restrições de acesso. A inspeção visual automatizada do Chromium foi tentada, mas o navegador não inicia neste ambiente por bloqueio do processo local; o visual no Windows ainda precisa de conferência.

## O que mudou na v9.7

- **Desempenho e diagnóstico por tópico unificados:** a antiga aba separada de diagnóstico foi incorporada a **Desempenho e diagnóstico**. As informações essenciais estão visíveis diretamente: evolução, estatísticas e distribuição, tópicos com dificuldades ou avanços, erros de prática, registros qualitativos, mapas de calor, estudantes para acompanhamento e intervenções. Cada conjunto tem **Ver evidências / Ver detalhes** para aprofundar, sem uma aba global de “Análise avançada”. **Notas da turma** continua separada como livro de notas por aluno e avaliação.
- **Seleção institucional minimalista:** em coordenação, dois filtros independentes, **Turma** (inclusive “Geral”) e **Tópico** (inclusive “Geral”). Há opções de agrupar **por avaliação, semana, quinzena, mês, bimestre ou semestre**, usando somente registros que existem; períodos não observados não são inventados.
- **Novas evidências além da nota:** o educador registra compreensão conceitual, aplicação, autonomia, transferência e dificuldades observadas, vinculadas ao aluno e tópico. Pode registrar uma revisão realizada; o sistema compara avaliações anteriores e posteriores apenas quando existem, **sem atribuir causalidade**. A média escolar é evidência, não rótulo de capacidade ou vocação.
- **Diagnóstico com IA ao final da página:** depois de ler os gráficos, o usuário escolhe **Executar diagnóstico**. Com `GEMINI_API_KEY`, o modelo recebe somente dados agregados e padrões e redige uma interpretação. Sem a chave, o Cognix identifica claramente uma **leitura descritiva por regras**. As sugestões de revisão são relacionadas a **dias e horários de aulas reais cadastradas**, nunca a um cronograma imaginário.
- **Cronograma que salva de verdade:** corrigida a importação ausente da conexão usada ao alterar aulas. O professor pode tanto **editar** quanto **criar uma nova atividade** em “Minha semana”, com tópico, plano, situação e horário. O sistema confirma a gravação no banco. O aluno encontra o mesmo quadro semanal e o plano público da atividade em **Meu cronograma**; observações privadas do professor não aparecem para alunos.
- **Não perder o trabalho ao trocar de aba:** formulários do banco de questões e do montador de provas, editores abertos e prévias não salvas permanecem em memória durante a navegação. O sorteio de uma prova **nunca a salva automaticamente**; é possível substituir, editar, reordenar, remover, descartar e só então confirmar. Esses rascunhos de interface ainda **não sobrevivem a fechar/recarregar a página**; salve a prova quando terminá-la.
- **Trilha ENEM exclusiva da 3ª série:** a opção só aparece para perfis vinculados à 3ª série, e a API recusa consultas sobre outras séries. Na visão do professor, permanece **Geral da sala** por padrão, com escolha individual opcional. O início do aluno de outras séries aponta para o desempenho geral, sem botão da trilha.
- **Navegação escura corrigida:** fundo preto/grafite preservado e barra lateral com rolagem própria, evitando que “Projeto do sistema” fique sobreposto ao usuário e ao botão de sair.

Os testes automatizados cobrem os três perfis, filtros de tempo e de tópico, isolamento por escola, evidências qualitativas, intervenção, diagnóstico agregado, sequência real da semana, salvamento e leitura pelo aluno, acesso restrito à trilha e edição/descarte de provas. **Não foi possível validar visualmente o navegador Windows a partir desta máquina**; confira a aparência no seu computador.

## Recursos herdados da v9.6

- **Painel do professor:** “Precisa da sua atenção” aparece antes das estatísticas e mostra tópicos críticos e alunos em queda ou com média abaixo do mínimo. Clique em um alerta para abrir os detalhes daquela turma no Diagnóstico. O total de alunos em atenção não duplica quem tem várias disciplinas.
- **Menos informações redundantes:** em uma conta institucional com apenas uma escola, o seletor e rótulos repetitivos da escola não aparecem no painel e cronograma.
- **Notas da turma separadas das análises:** o livro de notas apresenta registros por estudante e avaliação; na v9.7, Desempenho e Diagnóstico estão na mesma página.
- **Diagnóstico acionável:** o botão **Executar análise com IA** cruza médias, evolução, prática, tópicos de provas anteriores e cronograma. Com uma chave Gemini ativa, consulta de fato o modelo sobre dados agregados e sem identificação; sem chave, entrega apenas regras estatísticas **claramente identificadas como não sendo IA**.
- **Planejamento semanal de revisão:** sugestões de atividades curtas são vinculadas aos dias/aulas efetivamente registrados no cronograma da turma.
- **Montar provas:** agora o sorteio cria uma **prévia não salva**. É possível editar o enunciado só naquela prova, substituir/remover/reordenar questões, mudar título/valor/instruções, descartar, sortear outra prévia e **salvar somente após confirmação**. Provas salvas podem ser reeditadas ou excluídas; também podem ser vinculadas a avaliações reais cadastradas pela coordenação.
- **Personalização por professor:** ao sortear, a seleção prioriza assuntos com dificuldade nas notas e na prática, considera o cronograma e evita repetir questões já usadas por aquele professor. O sistema observa padrões dos registros; **isso não é treinamento automático de um modelo de IA**.
- **Trilha ENEM do professor:** abre em visão **geral da sala**; um filtro compacto permite escolher individualmente o aluno. Os dados longitudinais vêm do histórico preservado.
- **Acompanhamento de alunos:** alunos com médias persistentemente baixas também aparecem, mesmo que não tenham tido uma queda brusca entre duas avaliações.
- **Acesso de alunos e coordenação:** menus do HTML restaurados como páginas autenticadas do projeto, incluindo **Meu cronograma** para alunos, visão institucional, equipe, lançamento de notas, avaliações e configurações da coordenação. A conta escolar só pode ser criada pela coordenação.
- **Tema escuro:** interface em preto/grafite, preservando fundo claro para a impressão das provas.
- **Conectividade:** mensagens de erro distinguem falha de conexão e sessão expirada, com opção de tentar novamente quando a página já foi carregada. O inicializador mantém a busca automática da porta livre.

O protótipo mantém o HTML anterior em `docs/legado/` para referência. **Não constitui ainda garantia de equivalência funcional integral do HTML nem de implantação em produção.** É necessário validar fluxos e dados específicos na máquina da escola antes de utilizar com dados reais.

## Dados fictícios preservados

- 3 escolas X, Y, Z, com coordenações institucionais independentes;
- 7 professores com logins próprios, incluindo o Prof. Rafael Monteiro (assinatura individual de demonstração);
- 216 matrículas fictícias, 73 aulas e 26 atribuições de turma-disciplina provenientes do HTML, com notas, avaliações e histórico escolar fictício;
- 57 questões didáticas fictícias originais + 22 exemplos de questões particulares de professores;
- **Nenhuma questão ENEM real pré-importada no ZIP**. O importador continua disponível.

A conta do Rafael demonstra **X → Matemática, Y → Física e Z → Matemática e Física**. O professor só visualiza questões dessas disciplinas na escola selecionada. A coordenação de X não cadastra alunos nem vê questões particulares de Y.

## ENEM: procedimento completo

O projeto consulta a [API ENEM](https://github.com/yunger7/enem-api) (2009–2023), por integração HTTP; não é preciso rodar `pnpm dev` da API na mesma máquina, a menos que você opte por hospedá-la.

1. Entre como **coordenação**.
2. Abra **Importação ENEM**, selecione o ano e inicie a sincronização. A sincronização exige Internet e depende da disponibilidade do serviço. Também é possível executar:

   ```powershell
   py -m backend.import_enem --year 2023
   # ou para o intervalo completo da API:
   py -m backend.import_enem --all-years
   ```

3. Na aba **Banco de questões**, a coordenação filtra por origem **ENEM API**, visualiza o enunciado completo e classifica as questões de *Ciências da Natureza* usando **Classificar**. A classificação tem efeito **somente na sua escola** (por exemplo Física na Escola Y), sem modificar a classificação global de outras instituições.
4. O professor entra em **Banco de questões → Acervo geral**, escolhe sua escola no topo e filtra pela disciplina. Questões classificadas aparecem na sua matéria, mesmo enquanto aguardam revisão.
5. **Atenção:** importar e classificar não autoriza automaticamente distribuir questões em provas. As questões do ENEM entram em `review` e com direitos `pending`. A liberação comercial deve ser tratada pela curadoria global após revisão de enunciados, imagens, respostas e direitos de reprodução. A coordenação escolar não altera a curadoria global. O gerador de provas continuará usando apenas questões `published` com direitos `demo` ou `authorized`.

Uma questão matemática fica automaticamente na disciplina **Matemática**. Questões de Natureza não são rotuladas automaticamente como Física, Química ou Biologia, pois a divisão oficial da API é por **área**, não por componente curricular. A classificação local é necessária para garantir o filtro que você solicitou.

**Se a API ENEM não sincronizar:** entre em `Importação ENEM` para ver o registro e a mensagem da falha; ou execute o comando no terminal, que mostra o erro de conexão. A aplicação continua funcionando com os dados fictícios quando estiver offline.

## Contas e permissões

- **Plano Individual:** o professor faz autocadastro; para lecionar numa escola, solicita vínculo, a coordenação aprova e depois atribui turmas e matérias.
- **Plano Escolar:** somente a coordenação da instituição cria contas de professores, alunos e coordenadores.
- **Notas:** lançadas e corrigidas exclusivamente pela coordenação da escola. Professores consultam suas turmas; estudantes consultam apenas as próprias notas.
- **Banco de questões · Geral (v10.1):** o professor consulta, em uma única lista pesquisável, as questões públicas publicadas do catálogo central (inclusive ENEM de outras áreas), seu acervo pessoal e o acervo escolar das disciplinas atribuídas. Consultar não concede automaticamente a permissão de aplicar em uma prova. Questões privadas de terceiros e de escolas não vinculadas não aparecem.
- **Questões próprias:** privadas ao autor e à sua escola, salvo regra adicional de publicação aprovada; professores de escolas diferentes não recebem conteúdos particulares uns dos outros.
- **Provas preparadas:** apenas o autor edita e exclui sua prova; a coordenação tem permissão de consulta em suas escolas. O vínculo entre uma prova salva e avaliação exige uma avaliação previamente cadastrada.

Para conferir os três acessos demonstrativos, abra `data/ACESSOS-DEMO-LOCAL.txt` na pasta extraída. Faça login separadamente como **professor**, **coordenação** e **aluno**, usando o e-mail e a senha indicados no arquivo. Não publique essas credenciais e substitua-as em um ambiente real.

## Verificar o funcionamento

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
```

Os testes da v9.8 acrescentam preferências de estudo, exploração vocacional e isolamento de perfis às regressões da v9.7, incluindo permanência do planejamento, evidências qualitativas, filtros temporais, escopo institucional e revisão vinculada ao cronograma. **A aparência e a inicialização no seu Windows ainda exigem validação local**; os testes automáticos de API não garantem a experiência de um navegador Windows.

## Streamlit Community Cloud

A entrada `streamlit_app.py` oferece diagnóstico e criação de questões. Consulte [DEPLOY-STREAMLIT.md](DEPLOY-STREAMLIT.md) para configurar a publicação.

## IA opcional (Gemini): diagnóstico e geração reais

**Opção recomendada no Windows:** copie `.env.example` para um novo arquivo chamado `.env` na pasta principal do Cognix e preencha:

```dotenv
GEMINI_API_KEY=SUA_CHAVE_API
COGNIX_GEMINI_MODEL=gemini-3.5-flash
COGNIX_GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
```

O iniciador `iniciar-cognix.bat` instala a dependência de leitura do `.env`. A chave permanece exclusivamente no servidor, sem aparecer na interface ou ser incorporada ao pacote ZIP. Em **Banco de questões → Criar com IA**, confira o indicador de configuração, clique em **Testar conexão com IA** (faz uma chamada real à API e pode consumir tokens) e escolha **Salvar em**: seu acervo privado ou uma escola vinculada. A geração produz um lote de rascunhos recuperável em **Meu acervo** ou **Acervo da escola**, onde se confirmam gabarito, disciplina, tópico e direitos antes da publicação.

Se a chave, a conexão ou os créditos da API falharem, o Cognix retorna um erro claro. O modo de demonstração sem chave seleciona exemplos locais e não os descreve como questões geradas.

Também é possível configurar a chave somente para a sessão do PowerShell, sem criar `.env`:

No PowerShell, antes de iniciar o Cognix:

```powershell
$env:GEMINI_API_KEY="SUA_CHAVE_API"
$env:COGNIX_GEMINI_MODEL="gemini-3.5-flash"
py -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Sem chave, os exemplos fictícios continuam utilizáveis, mas **não são apresentados como resultados de uma geração real por LLM**. Questões geradas de fato são tratadas como rascunhos para revisão docente.

Para usar IA de verdade, configure sua própria chave na sessão PowerShell **antes** de iniciar o servidor com o comando acima. A execução normal por duplo clique no `.bat` não solicita nem fornece chave. Caso configure uma chave, o diagnóstico envia **estatísticas agregadas sem nomes de estudantes**, mas dados de aulas e turmas ainda podem ser sensíveis: verifique sua política de privacidade e as exigências legais antes de utilizar registros reais. O professor permanece responsável por revisar as recomendações e provas.

### Se aparecer “Failed to fetch” ou a página não abrir

1. Feche abas antigas do Cognix e abra a pasta da **v9.9 totalmente extraída**, não o arquivo HTML isolado.
2. Execute `iniciar-cognix.bat` e **mantenha a janela preta aberta**. Espere aparecer `Endereco do Cognix: http://127.0.0.1:PORTA/`.
3. Copie **o endereço exato exibido** para o navegador (pode ser outra porta, como `8001`). Se o servidor foi fechado, nenhum botão da aplicação conseguirá conectar até ele ser reaberto.
4. Se houver erro de Python, instalação ou porta, copie o texto ou tire uma foto da janela preta e envie para diagnóstico. Não é necessário apagar os dados para tentar novamente.

## Organização do projeto

- `frontend/index.html`, `frontend/css/app.css`: estrutura e estilo;
- `frontend/js/app.js`: login, navegação, banco, provas, equipe e filtros;
- `frontend/js/pages/pedagogy.js`: páginas pedagógicas do HTML, integradas aos endpoints;
- `frontend/js/pages/learning_insights.js`: página unificada de evidências e diagnóstico;
- `frontend/js/pages/analytics.js`: gráficos SVG, estatística visual e mapa de calor;
- `backend/main.py`: API autenticada, contas e permissões;
- `backend/db.py`, `backend/access.py`: schema/migrações e isolamento;
- `backend/import_enem.py`: importador idempotente, paginação e normalização;
- `backend/random_exam.py`: seleção aleatória, regras e autorização;
- `backend/pedagogy.py`, `backend/learning.py`: indicadores, aprendizagem e histórico;
- `backend/evidence.py`: filtros temporais, tópicos, registros qualitativos e intervenções persistidas;
- `backend/insights.py`: observações e prioridades baseadas em evidências de notas, questões, tentativas e aulas;
- `backend/llm/`: integração configurável de LLM;
- `data/`: SQLite e dados fictícios;
- `docs/legado/`: HTML anterior preservado;
- `tests/`: testes de regressão.

**Importante:** não utilizar este protótipo com dados reais de crianças e adolescentes sem auditoria de segurança, proteção de dados conforme LGPD, gestão de consentimento, backups, controles de infraestrutura e testes de produção.
