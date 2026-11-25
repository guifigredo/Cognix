"""Interface Streamlit para o diagnóstico e a geração de questões do Cognix."""
import asyncio
import os

import httpx
import streamlit as st

SETTINGS = (
    'GEMINI_API_KEY', 'COGNIX_GEMINI_MODEL', 'COGNIX_GEMINI_FALLBACK_MODEL',
    'COGNIX_DB', 'COGNIX_SECURE_COOKIES',
)
for name in SETTINGS:
    try:
        value = st.secrets.get(name)
    except FileNotFoundError:
        break
    if isinstance(value, str):
        os.environ.setdefault(name, value)

from backend.auth import COOKIE
from backend.main import app, initialize


@st.cache_resource
def start_backend():
    initialize()
    return app


def request(path, method='GET', payload=None, params=None):
    async def send():
        token = st.session_state.get('cognix_token')
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=start_backend()),
            base_url='https://cognix.internal',
            cookies={COOKIE: token} if token else None,
        ) as client:
            return await client.request(method, '/api' + path, json=payload, params=params)
    return asyncio.run(send())


def data(response):
    if response.is_success:
        return response.json()
    if response.status_code == 401 and st.session_state.get('cognix_token'):
        st.session_state.pop('cognix_token', None)
        st.rerun()
    detail = response.json().get('detail', 'A solicitação falhou.')
    st.error(detail if isinstance(detail, str) else 'Verifique os campos preenchidos.')
    return None


def diagnose(me):
    schools = {item['id']: item['name'] for item in me['schools']}
    if not schools:
        st.info('Vincule a conta a uma escola para consultar evidências de aprendizagem.')
        return
    school = st.selectbox('Escola', list(schools), format_func=schools.get)
    classes = data(request('/classes', params={'school': school}))
    if classes is None:
        return
    names = {'': 'Todas as turmas autorizadas', **{row['id']: row['name'] for row in classes}}
    classroom = st.selectbox('Turma', list(names), format_func=names.get)
    periods = {'avaliacao': 'Avaliação', 'semana': 'Semana', 'quinzena': 'Quinzena',
               'mes': 'Mês', 'bimestre': 'Bimestre', 'semestre': 'Semestre'}
    period = st.selectbox('Agrupar por', list(periods), format_func=periods.get)
    topic = st.text_input('Tópico (opcional)')
    if st.button('Executar diagnóstico', type='primary'):
        with st.spinner('Analisando as evidências…'):
            result = data(request('/ai/diagnose-evidence', 'POST', {
                'school_id': school, 'class_id': classroom, 'period': period, 'topic': topic.strip(),
            }))
        if not result:
            return
        st.caption(result['message'])
        st.write(result['summary'])
        for pattern in result['patterns']:
            st.write('• ' + (pattern if isinstance(pattern, str) else str(pattern)))
        if result['weekly_plan']:
            st.subheader('Sugestões de revisão')
            st.dataframe(result['weekly_plan'], hide_index=True)


def generate(me):
    catalog = data(request('/bank/collections'))
    if not catalog or not catalog['collections']:
        st.info('Nenhum acervo disponível para esta conta.')
        return
    schools = {row['id']: row['name'] for row in me['schools']}
    choices = {row['id']: row for row in catalog['collections']}
    names = {
        key: 'Meu acervo' if row['kind'] == 'personal' else schools.get(row['school_id'], row['name'])
        for key, row in choices.items()
    }
    destination = st.selectbox('Salvar em', list(choices), format_func=names.get)
    collection = choices[destination]
    with st.form('question_form'):
        if collection['kind'] == 'personal':
            subject = st.text_input('Disciplina')
        else:
            subjects = me['subjects_by_school'].get(collection['school_id'], [])
            subject = st.selectbox('Disciplina', subjects)
        topic = st.text_input('Tópico', max_chars=100)
        grade = st.text_input('Série', value='3ª série EM')
        difficulty = st.selectbox('Dificuldade', ['fácil', 'média', 'difícil'], index=1)
        count = st.number_input('Quantidade', min_value=1, max_value=8)
        instructions = st.text_area('Orientações (opcional)', max_chars=600)
        submit = st.form_submit_button('Gerar questões', type='primary')
    if submit:
        if not subject or len(topic.strip()) < 2:
            st.error('Informe a disciplina e um tópico com pelo menos dois caracteres.')
            return
        with st.spinner('Preparando as questões…'):
            result = data(request('/ai/questions', 'POST', {
                'collection_id': destination, 'subject': subject.strip(), 'topic': topic.strip(),
                'grade': grade.strip(), 'difficulty': difficulty, 'count': int(count),
                'instructions': instructions,
            }))
        if not result:
            return
        st.info(result['message'])
        if result.get('batch_id'):
            st.caption(f"Lote de rascunhos {result['batch_id']}")
        for index, question in enumerate(result['questions'], 1):
            with st.expander(f'Questão {index}', expanded=True):
                st.text(question['prompt'])
                for option in question['alternatives']:
                    st.text(f"{option['letter']}) {option['text']}")
                st.text(f"Gabarito: {question['correct_letter']}")
                if question.get('explanation'):
                    st.text(question['explanation'])


def main():
    st.set_page_config(page_title='Cognix', page_icon='📘', layout='wide')
    st.title('Cognix')
    if not st.session_state.get('cognix_token'):
        with st.form('login'):
            email = st.text_input('E-mail')
            password = st.text_input('Senha', type='password')
            submit = st.form_submit_button('Entrar', type='primary')
        if submit:
            response = request('/auth/login', 'POST', {'email': email, 'password': password})
            if data(response):
                st.session_state['cognix_token'] = response.cookies[COOKIE]
                st.rerun()
        return
    me = data(request('/me'))
    if not me:
        return
    st.sidebar.write(me['user']['name'])
    if st.sidebar.button('Sair'):
        request('/auth/logout', 'POST')
        st.session_state.pop('cognix_token', None)
        st.rerun()
    if me['user']['role'] not in ('prof', 'coord'):
        st.info('Este ambiente é destinado a professores e à coordenação.')
        return
    status = data(request('/ai/status'))
    if status:
        st.sidebar.caption(status['description'])
    section = st.sidebar.radio('Função', ['Diagnóstico', 'Criar questões'])
    if section == 'Diagnóstico':
        diagnose(me)
    else:
        generate(me)


if __name__ == '__main__':
    main()
