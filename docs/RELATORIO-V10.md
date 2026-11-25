# Cognix v10.0 · Relatório técnico das duas frentes

**Base auditada:** Cognix v9.9, incluindo `backend/db.py`, migrações, `access.py`, `auth.py`, `main.py`, rotas pedagógicas, exportação de provas, interface JavaScript e estilos. Mudanças incrementais e aditivas; banco demonstrativo e estrutura anterior preservados.

## 1. Erros confirmados no código anterior

| Área | Evidência encontrada | Correção na v10.0 |
|---|---|---|
| Revogação escolar | `allowed_schools` aceitava escola encontrada em `teaching_assignments`, ainda que a associação escolar fosse removida; `/api/classes` e `/api/pedagogy/attention` também consultavam atribuições diretamente. | `school_memberships.status` e filtro de vínculo ativo em `access.py`, listagens, cronograma, acompanhamento, provas e equipe. As atribuições históricas permanecem. |
| Identidade | `users.email` concentrava login e identidade; a administração podia criar um login novo por e-mail, sem convite com comprovação. | `teacher_identities`, `account_identities`, `verified_emails`, convites e políticas por escola. Convite para e-mail existente exige autenticação da conta preexistente. |
| Acervo e propriedade | Questões tinham `creator_id`/`school_id`, mas nenhuma classificação explícita de acervo, origem e revisão por lote; possuir acesso de leitura poderia ser confundido com ser titular. | Coleções pessoais ou escolares, registro explícito por questão, lote e posição, rascunho, categoria confirmada e trilha de transferência. Legado não classificado permanece ambíguo e intransferível. |
| Provas | `exam_detail` e exportação DOCX liam diretamente o enunciado da questão, que poderia ser alterado depois da aplicação. | `exam_item_snapshots` congelam o conteúdo na criação e atualização. |
| Importação docente | Não existia fluxo de importação DOCX/PDF/texto estruturado, recuperação por lote e confirmação de categorias para itens particulares. | Endpoints `/api/bank/*` e interface de importação e revisão em lote. |
| Consultas pessoais | A rota antiga `questions/mine` restringia-se ao contexto escolar e disciplina atribuída; um docente individual sem escola não conseguia aproveitar ali seu próprio acervo. | Novo Meu acervo independe da presença de turma ou escola, com separação de propriedade. |

## 2. Frente P0 — banco de questões

**Novo fluxo:** texto ou arquivo até 10 MB → extração local → registro transacional de lote → rascunhos com posições → sugestão por regras ou IA configurada → revisão humana → categorias normalizadas por acervo → busca e prova. Importações de conteúdo idêntico, mesmo autor e acervo retornam o lote existente. Gravações de importação usam transação `BEGIN IMMEDIATE` para serializar concorrência local.

**Extração:** parágrafos DOCX, PDFs com camada de texto e texto UTF-8; enunciados, alternativas A–E, gabaritos *explicitamente encontrados*, imagens incorporadas associadas ao trecho, com aviso para revisão de associação. O arquivo DOCX/PDF original pertence ao **lote**; imagens individuais pertencem à **questão**. Não é executado OCR. Alguns formatos ricos, tabelas DOCX e diagramas complexos ainda podem exigir correção manual.

**Catálogo:** `question_collections` (pessoal ou escolar), `question_records` (procedência, estado, versão), `question_categories` (normalização sem diferenças de acentuação), `question_batches`, `question_import_items`, `question_attachments`, `question_batch_files`. As categorias confirmadas são mantidas em novas chamadas de IA. A origem da sugestão é identificada; sem `OPENAI_API_KEY`, uma regra determinística substitui a sugestão, sem simular inteligência externa ou inferir gabaritos.

**Correção adicional de integridade:** o mesmo arquivo de imagem pode aparecer em várias questões. `storage_key` deixou de ser único na associação `question_attachments`: cada questão recebe um registro de permissão distinto, compartilhando somente os bytes físicos por hash. A migração reconstrói essa tabela em bancos que chegaram a usar a restrição anterior, sem descartar anexos.

**Acesso:** leitura, busca, revisão, original do lote e download de mídia verificam a coleção no servidor. Acervo escolar exige vínculo ativo e disciplina atribuída para professores; coordenação acessa apenas suas escolas. As rotas de IA recebem itens do lote autorizado. Exportação de provas e consulta de exame verificam turma e vínculo ativo.

**Provas:** snapshots imutáveis por `(prova, questão)`, com versão. A mesma questão pode aparecer em diferentes provas autorizadas sem cópia de seu registro original. Questões anteriores à v10 recebem snapshot inicial no upgrade; não é possível reconstruir exatamente o conteúdo de uma prova antiga se ele já foi alterado antes da migração.

**Infraestrutura:** SQLite existente mantido por ora, com WAL, `foreign_keys`, transações, `UNIQUE` e índices. Para uso local/uma instância e dezenas de milhares de itens, é uma escolha proporcional. Para múltiplos processos/servidores, grande volume de uploads ou alta concorrência de escrita, planejar PostgreSQL e armazenamento de objetos (S3/compatível) com backups consistentes. O protótipo atual usa arquivos locais protegidos por rotas autenticadas. Eles **não devem ser publicados diretamente como diretório estático**.

**Índices avaliados:** `idx_records_collection_state`, `idx_questions_topic`, índice composto da chave primária de `question_import_items`, `idx_batches_collection`, `idx_records_category` e unicidade do lote `(collection_id,uploader_id,content_sha256)`. Na medição sintética com 5.000 questões em dez acervos, o SQLite usou os índices na listagem por acervo e busca por tópico e a chave para localização por lote. Resultados pontuais obtidos no ambiente de testes: cerca de 0,010 ms, 0,675 ms e 0,001 ms de mediana por consulta, respectivamente. **Esses valores não são garantias de desempenho em produção.** `LIKE '%palavra%'` ainda não utiliza índice de busca textual; FTS5 deve ser avaliado com corpus real e consultas frequentes.

**Recuperação:** `scripts/backup_restore_v10.py` usa backup online do SQLite, inclui originais e mídias, hashes e manifesto; `restore` exige destino inexistente, verifica todos os arquivos e `PRAGMA foreign_key_check`. A rotina foi exercitada em diretório isolado. Agendamento automático e armazenamento remoto de backups não estão implantados.

## 3. Frente 1 — contas, transferência e encerramento

**Convite e controle:** escola convida docente por e-mail; não é criada nova conta na emissão. A aceitação exige código recebido e, para um login já existente, sua senha. Conta escolar, identidade de pessoa, e-mail verificado e vínculo são conceitos separados. O e-mail institucional continua sendo login possível; e-mails pessoais adicionais passam a funcionar como alias somente após confirmação.

**Duas opções de continuidade:** uma mesma conta pode ativar plano individual com e-mail pessoal verificado, se todas as escolas vinculadas autorizarem. Caso contrário, a vinculação de uma conta institucional a uma conta individual **separada** exige sessão autenticada da primeira, senha da segunda e verificação pessoal prévia. Há prévia dos itens elegíveis antes da confirmação. Categorias e rascunhos selecionados são realocados para o acervo pessoal de destino, sem clonar questões; lote próprio de transferência mantém rascunhos editáveis. `personal_transfers` e `account_events` documentam a operação, com repetição sem duplicação.

**Preferências pessoais:** `teacher_personal_preferences` guarda disciplina preferida e modo de revisão, separados de preferências ou rascunhos escolares. O docente pode marcar sua transferência na prévia; os campos já escolhidos na conta pessoal de destino prevalecem em conflitos. A seleção da confirmação fica registrada no desafio para impedir que uma repetição altere os itens transferidos.

**Regra de elegibilidade:** apenas itens em coleção `personal` com proprietário e registrante específicos da conta de origem. Itens escolares, provas, respostas, notas, alunos e quaisquer itens legados sem propriedade classificada não são transferidos. Uma autorização explícita da escola para determinada questão pode conceder uma **referência à versão autorizada**, sem copiar ou transferir a propriedade do acervo inteiro.

**Revogação:** `Encerrar vínculo com a escola` altera somente a associação escolar para `revoked`; mesmo cookies antigos deixam imediatamente de autorizar aquela escola. Atribuições e resultados persistem para auditoria e continuidade da escola. `Encerrar acesso à conta institucional` desativa uma credencial dedicada e suas sessões, com bloqueio quando ainda há questões particulares não transferidas ou outros vínculos ativos. `Encerrar conta pessoal` é ação independente com senha do próprio titular e prévia de impacto.

## 4. Testes realizados

Comando: `python -m unittest discover -s tests -p 'test_*.py' -q` com banco QA isolado. Foram aprovados **36 testes** no conjunto atual, incluindo **14 cenários novos** em `tests/test_v100_domains.py`:

1. Importar texto, retomar sem duplicar, recategorizar e preservar o tópico confirmado.
2. Buscar Cinemática e impedir acesso de outro professor e da coordenação a acervo pessoal.
3. Importar DOCX, manter original no lote e recuperar o banco e os arquivos em restauração isolada.
4. Extrair imagem DOCX e negar download a outro usuário.
5. Importar PDF com camada de texto, rejeitar conteúdo sem texto extraível.
6. Salvar prova e preservar enunciado após editar a questão original.
7. Vincular duas contas, pré-visualizar, transferir somente o acervo pessoal do professor específico e preservar o da escola e de outro docente; repetir confirmação sem duplicação; revogar acesso na sessão aberta; reiniciar e confirmar que a revogação persiste.
8. Enviar e aceitar convite para conta já existente sem criar outro login; exigir política escolar, verificar e-mail pessoal e autenticar pelo alias; encerrar conta escolar dedicada e suas sessões.
9. Submeter simultaneamente o mesmo lote por duas sessões e verificar unicidade transacional.
10. Transferir uma questão de um DOCX com duas questões: o original completo permanece vinculado ao lote de origem e inacessível ao destino.
11. Impedir encerramento da credencial institucional usada em duas escolas, ou que ainda possui e-mail pessoal verificado na própria credencial; diferenciar esse alias de uma conta individual independente.
12. Importar duas questões com a mesma imagem, guardando duas associações autorizadas e uma única cópia de bytes, sem violar `UNIQUE`.
13. Registrar preferências pessoais, incluir sua migração na seleção confirmada, preservar a preferência do destino e impedir mudança da seleção ao repetir o pedido.
14. Migrar uma tabela de anexos criada por uma versão v10 inicial com a restrição indevida `UNIQUE(storage_key)`, sem perda de dados.

`node --check` validou a sintaxe do JavaScript. `python -m compileall` validou os módulos. `scripts/check_query_plans_v10.py` gerou massa sintética e exibiu planos sem escrever no banco operacional.

**Teste de interface pendente:** o Chromium headless não iniciou neste ambiente (`socket() failed: Operation not permitted`), por isso não existe homologação visual de desktop/mobile por navegador real. CSS responsivo e estrutura HTML foram inspecionados estaticamente; realizar teste humano no Windows antes de publicar.

## 5. Riscos e pontos para produção

- **E-mail:** envio SMTP real depende de configuração e credenciais de servidor. Apenas modo de desenvolvimento revela códigos para cópia manual. Esse modo deve permanecer desligado em produção. Falta uma esteira operacional de entrega/reenvio e monitoramento.
- **Autenticação:** há proteção por senha com scrypt e cookie HttpOnly, mas faltam MFA, rotacionamento avançado de sessões e confirmação via domínio institucional para implantação comercial. A vinculação não é uma migração de credenciais; prova controle dos dois logins.
- **Legado:** itens antigos mantêm acesso histórico, mas não têm propriedade certificada para transferência; precisam de fluxo editorial de reclassificação para ampliar elegibilidade. Não migrar tudo automaticamente.
- **Documentos ricos:** parser cobre casos comuns; questões inseridas em tabelas, fórmulas matemáticas avançadas, PDFs multicoluna e imagens deslocadas requerem ensaios com documentos de escolas reais. Nunca tratar gabarito adivinhado como extraído.
- **Carga e busca:** benchmark sintético não substitui testes de concorrência, retenção e planos reais em produção. FTS5 e banco central distribuído permanecem decisões futuras.
- **Armazenamento:** arquivo local é compatível com implantação em um único host com cópia conjunta. Para produção em mais de uma instância, migrar anexos para armazenamento de objetos com controle de acesso, versionamento e restauração validada.
- **Proteção de dados:** para alunos, escolas e professores reais, realizar avaliação de LGPD, política de retenção/exclusão, consentimento, backups criptografados e trilhas de auditoria; encerramento de conta pessoal **desativa** acesso e retém dados para recuperação, não faz exclusão física ou anonimização.
- **OMR/leitura óptica:** permanece **idealização**, sem importador de folhas de respostas nem reconhecimento por máquina, conforme escopo anterior.
