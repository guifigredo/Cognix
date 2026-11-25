# Cognix no Streamlit Community Cloud

O ponto de entrada `streamlit_app.py` disponibiliza **Diagnóstico** e **Criar questões** para professores e coordenação. Ele usa as rotas FastAPI do Cognix no mesmo processo, com autenticação, escopo por escola e gravação de rascunhos no acervo selecionado. A interface web completa continua disponível com o servidor FastAPI.

## Publicar

1. Envie o conteúdo da pasta do projeto a um repositório GitHub. Mantenha as dependências no `requirements.txt` da raiz.
2. Para testar com turmas e diagnósticos, inclua somente um SQLite de demonstração com dados fictícios. O pacote traz `data/cognix.sqlite3` e o acesso de demonstração está no arquivo local `data/ACESSOS-DEMO-LOCAL.txt`. O SQLite é ignorado pelo Git por padrão. Em um repositório privado de demonstração, inclua deliberadamente apenas o SQLite fictício com `git add -f data/cognix.sqlite3`. Mantenha o arquivo de acessos e qualquer banco com dados reais fora do repositório. Sem um banco previamente provisionado, a aplicação inicializa um banco vazio.
3. Em [Streamlit Community Cloud](https://share.streamlit.io/), crie um app, selecione repositório e branch e informe `streamlit_app.py` como arquivo principal. Em **Advanced settings**, selecione Python 3.12 e cole os valores abaixo em **Secrets**.
4. Publique e entre com uma conta docente ou de coordenação do banco fictício. Para preservar os limites da cota Gemini, compartilhe a demonstração somente com os testadores.

```toml
GEMINI_API_KEY = "COLE_A_CHAVE_DO_GOOGLE_AI_STUDIO"
COGNIX_GEMINI_MODEL = "gemini-3.5-flash"
COGNIX_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"
COGNIX_SECURE_COOKIES = "1"
```

Os identificadores dos modelos são configuráveis. O fallback usa o mesmo projeto da API. Se os dois modelos estiverem indisponíveis ou sem cota, a interface informa a falha. Sem chave, o diagnóstico segue por regras locais e a criação mostra exemplos de demonstração identificados.

O SQLite e as mídias gravados no disco da instância servem para demonstração. Persista dados e anexos fora desse disco para um piloto que precise conservar alterações após reinicializações ou redeploy.

## Testar localmente

Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` ou use `.env` na raiz. Instale as dependências e rode:

```sh
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Para abrir a interface web completa, use `python -m uvicorn backend.main:app`. No Windows, o iniciador existente continua disponível.
