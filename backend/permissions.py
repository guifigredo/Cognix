"""Matriz operacional derivada do HTML original → Projeto do sistema.

A autorização efetiva deve acontecer nas rotas e queries; esta matriz descreve e
orienta a interface, nunca substitui verificações de escopo no servidor.
"""
MATRIX = [
    {'resource':'Próprias notas e quanto falta','student':'Próprias','teacher':'—','coordinator':'—'},
    {'resource':'Resumo da turma','student':'Simplificado','teacher':'Suas turmas','coordinator':'Sua escola'},
    {'resource':'Notas individuais dos colegas','student':'—','teacher':'Suas turmas','coordinator':'Sua escola'},
    {'resource':'Lançar e corrigir notas','student':'—','teacher':'Somente leitura','coordinator':'Sua escola'},
    {'resource':'Cadastro de usuários','student':'Criado pela escola','teacher':'Individual: cria o próprio; escolar: criado pela escola','coordinator':'Cria contas somente da própria escola'},
    {'resource':'Solicitar vínculo com escola','student':'—','teacher':'Plano individual: solicita à coordenação','coordinator':'Aprova e atribui turmas da sua escola'},
    {'resource':'Cronogramas de aulas e avaliações','student':'Visualiza','teacher':'Planeja suas aulas','coordinator':'Edita na sua escola'},
    {'resource':'Configurações da escola','student':'—','teacher':'—','coordinator':'Sua escola'},
    {'resource':'Diagnóstico e alertas','student':'—','teacher':'Suas turmas','coordinator':'Sua escola'},
    {'resource':'Desempenho por série e área','student':'—','teacher':'—','coordinator':'Sua escola'},
    {'resource':'Trilha ENEM e vocação','student':'Própria','teacher':'Tópicos de suas turmas','coordinator':'Trilhas da sua escola'},
    {'resource':'Conteúdo das questões','student':'Só na prática','teacher':'Disciplinas atribuídas','coordinator':'ENEM, IA e banco escolar (consulta administrativa)'},
    {'resource':'Unir tópicos duplicados','student':'—','teacher':'Sua disciplina','coordinator':'Sua escola'},
    {'resource':'Registro de acesso','student':'—','teacher':'—','coordinator':'Sua escola'},
]
CAPABILITIES={
    'aluno': ['dashboard','own_grades','own_needed','own_trail','vocational','practice','class_summary_limited'],
    'prof': ['dashboard','schedule_plan','read_grades','class_summary','class_analytics','diagnostic',
             'trail_assigned_topics','request_school_affiliation','questions_assigned','own_questions','create_exams','topics_own_subject'],
    'coord': ['institution_overview','schedule_manage','read_grades','edit_grades','class_analytics',
              'diagnostic','trails_school','enrollments','assignments','create_school_accounts','approve_individual_affiliations','school_settings',
              'question_metadata','view_enem_questions','view_ai_questions','question_admin_filters','review_ai_questions','review_imports','topics_school','school_audit']
}

def for_user(role):
    return {'role':role,'capabilities':CAPABILITIES.get(role,[]),'matrix':MATRIX,
            'scope': 'Escolas atribuídas à conta; coordenação restrita a sua instituição.'}

def is_ai_generated(q):
    source=q.get('source','') if hasattr(q,'get') else q['source']
    return source in ('Cognix LLM','Cognix IA')
