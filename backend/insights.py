"""Observacoes pedagogicas a partir de notas, avaliacoes e questoes.

Nenhum dado de outro vinculo e consultado pelo chamador; a verificacao de
permissao acontece antes de chamar as funcoes deste modulo.
"""
from collections import defaultdict
from .db import rows
from .pedagogy import performance


def class_observations(class_id: str, subject: str, teacher_id: str = '') -> dict:
    data = performance(class_id, subject)
    weak=[]
    for t in data['topics']:
        avg=t['stats']['mean']
        falling=t['trend'] is not None and t['trend']<=-1.5 and len(t['series'])>=2
        if avg is None or not (avg<data['school_threshold'] or falling):
            continue
        weak.append(dict(topic=t['topic'],mean=avg,below=t['below'],
            pct_below=t['pct_below'],trend=t['trend'],
            reason=('Média abaixo do critério de atenção' if avg<data['school_threshold']
                    else 'Queda entre avaliações do mesmo tópico')))
    by_student = {}
    for f in data['falls']:
        by_student.setdefault(f['student_id'],f)
    risk = []
    for student in data['students']:
        latest = by_student.get(student['id'])
        if student['average'] is None and not latest:
            continue
        if student['average'] is None or student['average'] >= data['school_threshold']:
            if not latest:
                continue
        risk.append(dict(
            student_id=student['id'], student_name=student['name'],
            average=student['average'], drop=latest['drop'] if latest else 0,
            previous=latest['previous'] if latest else None,
            current=latest['current'] if latest else None,
            assessment=latest['assessment'] if latest else None,
            reason='Queda recente' if latest else f"Média abaixo de {data['school_threshold']:.1f}"))
    risk.sort(key=lambda x:(0 if x['drop'] >= 2.5 else 1,
                             -(x['drop'] or 0),x['average'] if x['average'] is not None else 99))
    exams_sql='''SELECT q.topic,COUNT(*) quantity FROM exam_sets ex
        JOIN exam_items ei ON ei.exam_id=ex.id JOIN questions q ON q.id=ei.question_id
        WHERE ex.class_id=? AND ex.subject=?'''
    args=[class_id,subject]
    if teacher_id:
        exams_sql+=' AND ex.creator_id=?'
        args.append(teacher_id)
    exams=rows(exams_sql+' GROUP BY q.topic ORDER BY quantity DESC',args)
    applied_sql='''SELECT ex.applied_assessment assessment,
       AVG(g.score) grade_mean,COUNT(DISTINCT g.student_id) students
       FROM exam_sets ex JOIN grades g ON g.class_id=ex.class_id
        AND g.subject=ex.subject AND g.assessment=ex.applied_assessment
       WHERE ex.class_id=? AND ex.subject=? AND ex.applied_assessment!='' '''
    applied_args=[class_id,subject]
    if teacher_id:
        applied_sql+=' AND ex.creator_id=?'
        applied_args.append(teacher_id)
    applied=rows(applied_sql+' GROUP BY ex.applied_assessment',applied_args)
    practice=rows('''SELECT q.topic,COUNT(*) total,
       SUM(CASE WHEN a.correct=0 THEN 1 ELSE 0 END) misses
       FROM attempts a JOIN questions q ON q.id=a.question_id
       JOIN enrollments e ON e.user_id=a.user_id
       JOIN classes c ON c.id=e.class_id
       WHERE e.class_id=? AND a.school_id=c.school_id AND q.discipline=?
         AND (q.school_id IS NULL OR q.school_id='' OR q.school_id=c.school_id)
       GROUP BY q.topic''',(class_id,subject))
    known={x['topic'] for x in weak}
    topics_by_name={x['topic']:x for x in data['topics']}
    for p in practice:
        if p['topic'] in known or p['total']<5 or p['misses']/p['total']<.7:
            continue
        sample=topics_by_name.get(p['topic'])
        weak.append(dict(topic=p['topic'],mean=sample['stats']['mean'] if sample else None,
            below=sample['below'] if sample else 0,
            pct_below=sample['pct_below'] if sample else 0,
            trend=sample['trend'] if sample else None,
            reason=f"{p['misses']} erros em {p['total']} questões de prática"))
    lessons_sql='''SELECT l.id,l.weekday,l.slot,l.topic,l.plan,l.status,l.notes
       FROM lesson_schedule l WHERE l.class_id=? AND l.subject=?'''
    lesson_args=[class_id,subject]
    if teacher_id:
        lessons_sql+=' AND l.teacher_id=?'
        lesson_args.append(teacher_id)
    lessons=rows(lessons_sql+' ORDER BY l.weekday,l.slot',lesson_args)
    practice_by_topic={p['topic']:p for p in practice}
    topic_scores=defaultdict(float)
    for t in weak:
        threshold=data['school_threshold']
        topic_scores[t['topic']]+=3+max(0,(threshold-(t['mean'] if t['mean'] is not None else threshold))/2)
    for p in practice:
        if p['total']>=2:
            topic_scores[p['topic']]+=2*p['misses']/p['total']
    for a in lessons:
        if a['status']=='planejada':
            topic_scores[a['topic']]+=1
    priorities=sorted(topic_scores,key=lambda t:(-topic_scores[t],t))
    plan=[]
    for lesson in lessons:
        if lesson['status']!='planejada':
            continue
        topic=lesson['topic']
        focus=topic if topic in topic_scores else (priorities[0] if priorities else topic)
        detail=practice_by_topic.get(focus)
        reason=('Tópico com desempenho abaixo do mínimo' if focus in {x['topic'] for x in weak}
                else 'Erros recorrentes na prática' if detail and detail['misses'] >= 2
                else 'Conexão com a aula programada')
        plan.append(dict(lesson_id=lesson['id'],weekday=lesson['weekday'],
                         slot=lesson['slot'],scheduled_topic=topic,focus_topic=focus,
                         reason=reason,minutes=15 if focus in {x['topic'] for x in weak} else 10,
                         activity='Diagnóstico rápido, exemplos comentados e exercícios em níveis',
                         existing_plan=lesson['plan'],teacher_notes=lesson['notes']))
    return dict(class_id=class_id,subject=subject,student_count=len(data['students']),
                school_threshold=data['school_threshold'],
                class_mean=data['stats']['mean'],weak_topics=weak,
                falling_students=data['falls'],students_to_follow=risk,
                practice=practice,previous_exam_topics=exams,
                applied_exams=applied,
                priorities=priorities,weekly_plan=plan)


def teacher_attention(assignments: list[dict],teacher_id: str = '') -> dict:
    topics,students,summary=[],[],[]
    for assignment in assignments:
        obs=class_observations(assignment['class_id'],assignment['subject'],teacher_id)
        for item in obs['weak_topics']:
            topics.append({**item,**assignment,'threshold':obs['school_threshold']})
        for item in obs['students_to_follow']:
            students.append({**item,**assignment})
        summary.append({**assignment,'students':obs['student_count'],
                        'critical_topics':len(obs['weak_topics']),
                        'students_to_follow':len(obs['students_to_follow']),
                        'mean':obs['class_mean'],'threshold':obs['school_threshold']})
    topics.sort(key=lambda x:(0 if x['mean'] is not None and x['mean']<x['threshold'] else 1,
                              x['mean'] if x['mean'] is not None else 99,
                              -x['pct_below']))
    students.sort(key=lambda x:(0 if x['drop']>=2.5 else 1,
                                -(x['drop'] or 0), x['average'] if x['average'] is not None else 99))
    return dict(critical_topics=topics,students_to_follow=students,
                classes=summary,critical_count=len(topics),
                unique_students_to_follow=len({(x.get('school_id',x['class_id']),x['student_id'])
                                               for x in students}),
                falling_count=len({(x['class_id'],x['subject'],x['student_id'])
                                   for x in students if x['drop']>=2.5}))
