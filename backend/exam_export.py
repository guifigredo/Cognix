"""Exportação em Word da prova montada no banco central, com ou sem gabarito."""
import io
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from docx import Document
from docx.shared import Cm, Pt
from .auth import require
from .access import assert_class, assert_subject
from .db import one, rows

router = APIRouter(prefix='/api/exams', tags=['Exportação de provas'])


@router.get('/{exam_id}/docx')
def download_docx(exam_id: str, answers: bool = False, user=Depends(require('coord', 'prof'))):
    exam = one('''SELECT e.*,c.name class_name,s.name school_name
      FROM exam_sets e JOIN classes c ON c.id=e.class_id
      JOIN schools s ON s.id=c.school_id WHERE e.id=?''', (exam_id,))
    if not exam:
        raise HTTPException(404, 'Prova não encontrada.')
    if user['role'] == 'coord':
        assert_class(user, exam['class_id'])
    else:
        assert_class(user,exam['class_id'])
        if exam['creator_id'] != user['id']:
            raise HTTPException(404,'Prova não encontrada.')
        assert_subject(user,exam['subject'],exam['class_id'] and one('SELECT school_id FROM classes WHERE id=?',(exam['class_id'],))['school_id'])
    items = rows('''SELECT q.id,q.context,q.prompt,q.alternatives_json,q.correct_letter,q.media_json,i.points,s.snapshot_json
      FROM exam_items i JOIN questions q ON q.id=i.question_id
      LEFT JOIN exam_item_snapshots s ON s.exam_id=i.exam_id AND s.question_id=i.question_id
      WHERE i.exam_id=? ORDER BY i.position''', (exam_id,))
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(1.8)
    sec.left_margin = sec.right_margin = Cm(2.1)
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)
    doc.add_heading(exam['title'], level=1)
    doc.add_paragraph(f"Escola: {exam['school_name']}     Turma: {exam['class_name']}")
    doc.add_paragraph(f"Disciplina: {exam['subject']}     Valor: {exam['total_points']:.2f} pontos".replace('.', ','))
    doc.add_paragraph('Aluno(a): ______________________________________________   Data: ____/____/______')
    try:
        config = json.loads(exam['configuration_json'] or '{}')
    except ValueError:
        config = {}
    edits=config.get('question_edits') or {}
    doc.add_paragraph(config.get('instructions') or 'Leia com atenção e assinale a alternativa correta.')
    for n, item in enumerate(items, 1):
        item.update(json.loads(item.pop('snapshot_json') or '{}'))
        heading=doc.add_heading(f"Questão {n} ({item['points']:.2f} ponto(s))".replace('.', ','), level=2)
        heading.paragraph_format.keep_with_next=True
        text = '\n'.join(x for x in (item['context'], edits.get(item['id'],item['prompt'])) if x).strip()
        p=doc.add_paragraph(text)
        p.paragraph_format.keep_with_next=True
        try:
            alts = json.loads(item['alternatives_json'] or '[]')
        except ValueError:
            alts = []
        if alts:
            for j,alt in enumerate(alts):
                ap=doc.add_paragraph(f"{alt.get('letter', '?')}) {alt.get('text', '')}")
                ap.paragraph_format.keep_with_next = j < len(alts)-1
                if alt.get('file'):
                    doc.add_paragraph('Imagem da alternativa: ' + alt['file'][:300])
        else:
            for _ in range(3):
                doc.add_paragraph('____________________________________________________________________________')
        try:
            media = json.loads(item['media_json'] or '[]')
        except ValueError:
            media = []
        for image in media:
            if isinstance(image, str) and image:
                doc.add_paragraph('Figura de referência: ' + image[:300])
        if answers:
            doc.add_paragraph('Gabarito: ' + (item['correct_letter'] or 'Revisão docente necessária'))
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename="Cognix-Prova-{exam_id[:8]}.docx"'})
