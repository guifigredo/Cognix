"""Restrições de tenant e disciplina aplicadas nas consultas, nunca só no browser."""
from fastapi import HTTPException
from .db import rows,one


def allowed_schools(user):
    if user['role']=='coord':
        sql='''SELECT school_id id FROM coordinator_schools WHERE user_id=?'''
    elif user['role']=='prof':
        sql='''SELECT school_id id FROM school_memberships
               WHERE user_id=? AND status='active' ORDER BY school_id'''
    else:
        sql='''SELECT DISTINCT id FROM (
          SELECT c.school_id id FROM enrollments a JOIN classes c ON c.id=a.class_id WHERE a.user_id=?
          UNION SELECT school_id id FROM school_memberships WHERE user_id=?
        ) ORDER BY id'''
    args=(user['id'],) if user['role'] in ('coord','prof') else (user['id'],user['id'])
    return [x['id'] for x in rows(sql,args)]


def assert_school(user,school):
    if school not in allowed_schools(user):
        raise HTTPException(403,'Você não possui acesso a esta escola.')


def assert_class(user,class_id):
    cls=one('SELECT school_id FROM classes WHERE id=?',(class_id,))
    if not cls: raise HTTPException(404,'Turma não encontrada.')
    if user['role']=='coord': assert_school(user,cls['school_id'])
    elif user['role']=='prof':
        assert_school(user,cls['school_id'])
        if not one('SELECT 1 FROM teaching_assignments WHERE teacher_id=? AND class_id=?',(user['id'],class_id)):
            raise HTTPException(403,'Turma não atribuída ao professor.')
    elif not one('SELECT 1 FROM enrollments WHERE user_id=? AND class_id=?',(user['id'],class_id)):
        raise HTTPException(403,'Aluno não matriculado nesta turma.')
    return cls


def subjects_for(user, school=None):
    if school: assert_school(user,school)
    if user['role']=='prof':
        statement='''SELECT DISTINCT a.subject FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
                   JOIN school_memberships m ON m.user_id=a.teacher_id AND m.school_id=c.school_id AND m.status='active'
                   WHERE a.teacher_id=? AND (? IS NULL OR c.school_id=?)'''
    elif user['role']=='coord':
        statement='''SELECT DISTINCT a.subject FROM teaching_assignments a JOIN classes c ON c.id=a.class_id
                   JOIN coordinator_schools z ON z.school_id=c.school_id
                   WHERE z.user_id=? AND (? IS NULL OR c.school_id=?)'''
    else:
        statement='''SELECT DISTINCT a.subject FROM teaching_assignments a JOIN enrollments e ON e.class_id=a.class_id
                   JOIN classes c ON c.id=e.class_id WHERE e.user_id=? AND (? IS NULL OR c.school_id=?)'''
    return sorted({r['subject'] for r in rows(statement,(user['id'],school,school))})


def assert_subject(user, subject,school=None):
    if subject not in subjects_for(user,school):
        raise HTTPException(403,'Disciplina fora das atribuições desta escola.')


def scoped_question_sql(user,school=None):
    allowed=subjects_for(user,school)
    if not allowed:return '1=0',[]
    return 'discipline IN ('+','.join('?' for _ in allowed)+')',allowed
