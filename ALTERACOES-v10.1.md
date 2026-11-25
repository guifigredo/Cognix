# Cognix v10.1 — Banco Geral e LLM

## Alterações

1. **Aba Geral para professores:** agregação paginada e pesquisável do catálogo central público, dos itens particulares do usuário e das questões institucionais liberadas pelo vínculo e disciplina. Questões de outros professores e escolas não vinculadas continuam fora da consulta. O catálogo público pode ser consultado independentemente da matéria lecionada; a seleção para prova exige permissões adicionais.
2. **LLM configurável:** o servidor lê `OPENAI_API_KEY` e `COGNIX_LLM_MODEL` de variáveis do processo ou do arquivo `.env` na raiz, sem divulgar credenciais na API. A configuração é relida a cada solicitação. Nova ação **Testar conexão com IA** executa uma chamada real ao provedor e informa se foi validada.
3. **Geração vinculada a acervo:** professor seleciona **Salvar em** (particular ou institucional) antes de gerar. A saída validada vira um lote `llm`, com questões em revisão, sugestão de classificação e vínculo explícito a `question_records`. É possível abrir o lote e revisar as questões antes de publicar.
4. **Validação de gabarito:** um gabarito ausente na resposta do modelo é rejeitado, não recebe mais a letra A como padrão.
5. **Inicialização Windows:** o inicializador verifica também `pypdf` e `python-dotenv` para instalar novas dependências quando necessário.

## Alterações de esquema e dados

- Nenhuma migração de tabelas foi necessária: o modelo v10 existente já contém os campos de propriedade, lotes, categorias e revisão.
- As questões geradas na v10.1 preenchem agora as tabelas existentes `question_batches`, `question_import_items` e `question_records`; a versão anterior gravava apenas em `questions`.
- Rascunhos legados sem vínculo de coleção **não são reclassificados automaticamente**. Requerem revisão de propriedade antes de eventual migração.

## Verificação

Execute `python -m unittest discover -s tests -p 'test_*.py' -q`, `python -m compileall -q backend scripts` e `node --check frontend/js/app.js`.

Os testes incluem: consulta ao catálogo público; bloqueio de itens privados entre professores; revogação após desligamento; criação, revisão e isolamento de lote com LLM simulado em teste; rejeição de gabarito incompleto; teste de configuração e de resposta do endpoint de conexão. A chamada real ao provedor necessita de chave própria válida e de acesso à rede; não é feita durante os testes automatizados.
