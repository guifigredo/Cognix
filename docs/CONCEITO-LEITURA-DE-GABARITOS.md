# Cognix — Concepção da integração de leitura de gabaritos

**Estado:** estudo de viabilidade; nenhuma funcionalidade de reconhecimento de imagem foi implementada na v9.9.

## Por que integrar

Hoje o Cognix dispõe de banco de questões, provas montadas e respostas dadas na plataforma, mas não recebe automaticamente as alternativas assinaladas numa prova impressa. Uma futura integração permitiria consolidar as respostas por questão, associadas a aluno, turma e avaliação, com uma cadeia de evidências verificável para o professor.

**Benefícios desejados:**

1. Saber quais questões tiveram mais erros, em quantas respostas e entre quantos alunos diferentes.
2. Identificar alternativas escolhidas com maior frequência, sem afirmar automaticamente *por que* foram escolhidas.
3. Relacionar questões a tópicos, competências e avaliações — quando essa relação estiver efetivamente cadastrada e validada.
4. Apoiar revisões individuais e diagnósticos do professor com evidências adicionais, sem transformar uma única nota em rótulo de capacidade.

## Como seria a jornada futura

1. **Preparação:** professor escolhe uma prova existente ou importa o seu gabarito, define identificação da aplicação, turma e versão. O Cognix gera um modelo de folha padronizada com identificadores apropriados.
2. **Aplicação em papel:** a folha marca um identificador de prova/versão e um identificador de estudante. É necessário um procedimento para folhas sem identificação válida.
3. **Captura:** scanner de mesa ou câmera de celular. A imagem é endireitada, a região de respostas é detectada, e a qualidade do arquivo é aferida antes da leitura.
4. **Interpretação provisória:** o leitor óptico propõe A–E, branco, dupla marcação ou ilegível por item, registrando uma medida de confiança. O reconhecimento não altera notas oficiais.
5. **Conferência humana:** marcações ambíguas e associações de estudante/prova são apresentadas ao professor. Ele pode revisar a imagem, corrigir a interpretação ou rejeitar uma folha, com trilha de auditoria.
6. **Confirmação e publicação:** após aprovação, respostas validadas alimentam o desempenho por questão e assunto; a nota global pode ser calculada pelas regras explícitas daquela avaliação. A publicação de notas segue a permissão da coordenação já adotada no Cognix.

## Modelo conceitual de dados — futuro

| Entidade futura | Informação essencial | Regra de integridade |
| --- | --- | --- |
| Aplicação da prova | Prova, versão de gabarito, turma, disciplina, data | Uma aplicação usa um gabarito versionado e identificável |
| Folha recebida | Aplicação, aluno, estado da captura, referência da imagem | Identidade deve pertencer à turma; folhas duplicadas geram revisão |
| Marcação lida | Folha, posição da questão, alternativa candidata, confiança | Diferenciar branco, múltiplas marcas e ilegível |
| Resposta validada | Questão original do banco, alternativa final, acerto, revisor | É a evidência usada nas estatísticas; conserva revisão/auditoria |
| Relacionamento pedagógico | Questão, tópico, competência, peso | Tópicos precisam ser cadastrados; não distribuir nota composta por suposição |

As respostas validadas devem ser ligadas a `exam_sets`/`exam_items` e aos identificadores de `questions` já existentes. Para cada aplicação, preservar **duas medidas distintas**: *taxa de acerto por tentativa* e *percentual de alunos distintos que acertaram*. Não agregar ambas com o mesmo denominador. Questões repetidas em outras provas precisam manter contexto de aplicação e versão.

## Questões de viabilidade a testar

| Dimensão | Pergunta de validação | Tratamento sugerido |
| --- | --- | --- |
| Marcação | Lápis claro, rasura, duas bolhas e marca fora do círculo são legíveis? | Classificar como ambígua e exigir conferência |
| Captura | Fotos inclinadas, sombra, dobra e iluminação fraca prejudicam a leitura? | Rejeição por baixa qualidade e orientação para refazer |
| Identidade | Como evitar troca de aluno ou versão da prova? | IDs conferidos com matrícula, lista de aplicação e checagem de duplicidade |
| Mapeamento | Como relacionar a posição impressa à questão e ao tópico corretos? | Versão imutável do caderno e conferência de ordem/gabarito |
| Privacidade | Quem pode ver imagem, respostas e notas identificáveis? | Escopo por escola/turma/papel, retenção definida e auditoria |
| Experiência | Quanto tempo o professor gasta conferindo exceções? | Medir tempo manual antes/depois e frequência de revisões |

## Opções técnicas para uma fase posterior

- **Mais viável para o piloto:** folha rígida padronizada e leitura por visão computacional convencional (detecção de marcadores, correção de perspectiva, localização de bolhas e classificação com limites de confiança). Não exige LLM para identificar letras marcadas.
- **Captura híbrida:** aceitar PDF de scanner e foto de celular, mas validar os dois fluxos separadamente porque há condições óticas diferentes.
- **IA como apoio pedagógico, não leitora autoritativa:** depois da validação humana, padrões de alternativas, acertos por questão e mudanças entre aplicações podem enriquecer as análises já existentes. O professor decide como agir.

## Piloto de decisão

Selecionar uma turma e uma prova curta com gabarito conhecido. Separar folhas de diferentes condições (nítidas, marcas fracas, rasuras, múltiplas marcas, baixa qualidade), guardar uma transcrição humana de referência e medir:

1. **Exatidão por marcação:** proporção de alternativas lidas corretamente contra a referência humana.
2. **Taxa de exceções:** fração de folhas/itens que exigem revisão.
3. **Taxa de associações corretas:** folha ↔ aluno ↔ versão da prova sem erros.
4. **Tempo de operação:** captura, conferência e correção, comparados com o processo atual.
5. **Integridade pedagógica:** consistência entre os resultados validados e o painel por questão/tópico.

Os critérios numéricos de aceitação devem ser definidos antes do piloto com professores e coordenação, e não presumidos sem observações. A integração só deve avançar quando ambiguidades forem **visíveis e corrigíveis** e nenhum reconhecimento incerto for publicado silenciosamente como nota.

## Fora do escopo atual

- Reconhecimento óptico, upload de imagens e emissão de folhas para leitura automática.
- Alterações em notas de alunos a partir de fotografias.
- Inferência automática de causas cognitivas a partir da alternativa errada.
- Formação de grupos temporários de revisão.
