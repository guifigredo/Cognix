# Fontes e uso dos conteúdos — Cognix

## O que é código, o que é dado

O repositório `yunger7/enem-api` publica seu **código-fonte** sob a GPL-2.0. O Cognix v7 não copia esse código: solicita respostas JSON por HTTP à API publicada. A licença da aplicação externa **não é uma confirmação automática** de licença comercial para cada enunciado, alternativa, imagem, texto base ou recurso de prova.

A API ENEM afirma ter obtido dados de fontes públicas. Essa declaração deve ser estudada junto ao material oficial do INEP e aos direitos de terceiros incorporados a provas. Uma aplicação comercial deve documentar autorização e procedência de cada item antes de republicá-lo.

## Política do protótipo

- Itens vindos da API ENEM são persistidos na tabela `questions` com `rights_status=pending` e `status=review`, com campos originais preservados quando disponíveis.
- O revisor pedagógico da coordenação seleciona disciplina, tema e dificuldade, verifica gabarito e mídias, e registra `rights_status=authorized` antes de publicá-los.
- Itens com `status=review` **não** estão disponíveis para prática do aluno nem criação de provas.
- Questões originais da base fictícia são marcadas como `source=Cognix Demo`; não as apresente como ENEM nem como questões verificadas pelo INEP.
- URLs de imagens apontam para recursos originais. A aplicação deve verificar as condições de redistribuição antes de fazer cópias ou CDN próprio.

## Próximas melhorias sugeridas

Adicionar uma tabela `source_licenses` com documento de licença, data de verificação, atribuições obrigatórias, proprietário do conteúdo e controle de distribuição; registrar revisão e auditoria por questão; manter versões históricas dos enunciados e gabaritos; digitalizar figuras autorizadas; detectar quase duplicatas textuais e visuais; separar a informação curricular BNCC dos metadados originais do ENEM.
