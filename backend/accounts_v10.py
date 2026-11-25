"""Identidades, convites, transferência explícita e encerramento de vínculos."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import EMAIL, current_user, password_hash, password_verify, require
from .db import one, rows, session
from .access import assert_school, allowed_schools

router=APIRouter(prefix='/api/accounts',tags=['Vínculos docentes'])


def expiry(hours=24):
    return (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=hours)).isoformat()


def now():return dt.datetime.now(dt.timezone.utc).isoformat()


def audit(db,actor,subject,school,event,details=None):
    db.execute('''INSERT INTO account_events(id,actor_id,subject_id,school_id,event,details_json)
                  VALUES(?,?,?,?,?,?)''',(secrets.token_hex(12),actor,subject,school,event,json.dumps(details or {},ensure_ascii=False)))


def _ensure_identity(db,uid):
    row=db.execute('SELECT identity_id FROM account_identities WHERE user_id=?',(uid,)).fetchone()
    if row:return row['identity_id']
    identity=secrets.token_hex(12)
    db.execute('INSERT INTO teacher_identities(id) VALUES(?)',(identity,))
    db.execute('INSERT INTO account_identities(user_id,identity_id) VALUES(?,?)',(uid,identity))
    return identity


def send_email(to,subject,text):
    host=os.getenv('COGNIX_SMTP_HOST','').strip()
    sender=os.getenv('COGNIX_SMTP_FROM','').strip()
    if not host or not sender:
        if os.getenv('COGNIX_DEV_INVITES')=='1':return False
        raise HTTPException(503,'Configure COGNIX_SMTP_HOST e COGNIX_SMTP_FROM para enviar convites.')
    msg=EmailMessage()
    msg['From']=sender;msg['To']=to;msg['Subject']=subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(host,int(os.getenv('COGNIX_SMTP_PORT','587')),timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.getenv('COGNIX_SMTP_USER'):
                smtp.login(os.getenv('COGNIX_SMTP_USER'),os.getenv('COGNIX_SMTP_PASSWORD',''))
            smtp.send_message(msg)
    except Exception as exc:
        raise HTTPException(502,'Falha no envio por SMTP; nenhum convite foi ativado.') from exc
    return True


class InviteTeacher(BaseModel):
    school_id:str
    name:str=Field(min_length=3,max_length=100)
    email:str=Field(max_length=180)


@router.post('/school/invite')
def invite_teacher(body:InviteTeacher,user=Depends(require('coord'))):
    assert_school(user,body.school_id)
    email=body.email.strip().lower()
    if not EMAIL.fullmatch(email):raise HTTPException(422,'E-mail inválido.')
    token=secrets.token_urlsafe(32)
    invitation=secrets.token_hex(12)
    # Não cria usuário nem identidade sem prova de controle do e-mail.
    delivered=send_email(email,'Convite para o Cognix',
        f'Você foi convidado(a) para o Cognix na escola {body.school_id}. '
        f'No aplicativo, use o código de convite: {token} (válido por 48 horas).')
    with session() as db:
        db.execute('''INSERT INTO school_teacher_invites(id,school_id,email,name,token_hash,invited_by,expires_at)
                     VALUES(?,?,?,?,?,?,?)''',(invitation,body.school_id,email,body.name,
                     hashlib.sha256(token.encode()).hexdigest(),user['id'],expiry(48)))
        audit(db,user['id'],None,body.school_id,'teacher_invited',{'email':email,'delivery':'smtp' if delivered else 'manual-dev'})
    result={'ok':True,'delivery':'smtp' if delivered else 'manual-dev','invite_id':invitation}
    if not delivered:result['development_token']=token
    return result


class AcceptInvite(BaseModel):
    token:str
    password:str=Field(min_length=10,max_length=256)
    # Se usuário já existe, a senha deve autenticar a conta original.


@router.post('/school/accept')
def accept_invite(body:AcceptInvite):
    digest=hashlib.sha256(body.token.encode()).hexdigest()
    with session() as db:
        inv=db.execute('SELECT * FROM school_teacher_invites WHERE token_hash=?',(digest,)).fetchone()
        if not inv or inv['accepted_by'] or inv['expires_at']<=now():
            raise HTTPException(409,'Convite inexistente, expirado ou já utilizado.')
        existing=db.execute('SELECT * FROM users WHERE email=?',(inv['email'],)).fetchone()
        if not existing:
            existing=db.execute('''SELECT u.* FROM users u JOIN verified_emails v ON v.user_id=u.id
                                   WHERE v.email=?''',(inv['email'],)).fetchone()
        if existing:
            if existing['role']!='prof' or not existing['active'] or not password_verify(body.password,existing['password_hash']):
                raise HTTPException(403,'Comprove a senha da conta docente existente.')
            uid=existing['id']
        else:
            uid=secrets.token_hex(12)
            db.execute('''INSERT INTO users(id,name,email,password_hash,role,account_plan)
                        VALUES(?,?,?,?,'prof','school')''',(uid,inv['name'],inv['email'],password_hash(body.password)))
        _ensure_identity(db,uid)
        db.execute('''INSERT OR IGNORE INTO school_memberships(user_id,school_id) VALUES(?,?)''',(uid,inv['school_id']))
        db.execute('''UPDATE school_memberships SET status='active' WHERE user_id=? AND school_id=?''',(uid,inv['school_id']))
        db.execute('UPDATE school_teacher_invites SET accepted_by=? WHERE id=?',(uid,inv['id']))
        db.execute('INSERT OR IGNORE INTO verified_emails(user_id,email) VALUES(?,?)',(uid,inv['email']))
        audit(db,uid,uid,inv['school_id'],'invitation_accepted',{'invite_id':inv['id']})
    return {'ok':True,'user_id':uid,'school_id':inv['school_id'],'existing_account':bool(existing)}


class EmailChallenge(BaseModel):
    email:str=Field(max_length=180)


@router.post('/personal-email/challenge')
def request_personal_email(body:EmailChallenge,user=Depends(require('prof'))):
    email=body.email.strip().lower()
    if not EMAIL.fullmatch(email):raise HTTPException(422,'E-mail inválido.')
    if user['account_plan']=='school':
        sites=allowed_schools(user)
        if sites and any(not one('SELECT allow_personal_email FROM school_policy WHERE school_id=?',(s,)) or
                         not one('SELECT allow_personal_email FROM school_policy WHERE school_id=?',(s,))['allow_personal_email'] for s in sites):
            raise HTTPException(403,'A escola ainda não permitiu vincular e-mail pessoal a esta conta.')
    found=one('SELECT id FROM users WHERE email=?',(email,))
    if found and found['id']!=user['id']:
        raise HTTPException(409,'Este e-mail corresponde a outra conta. Use a vinculação de duas contas.')
    found_alias=one('SELECT user_id FROM verified_emails WHERE email=?',(email,))
    if found_alias and found_alias['user_id']!=user['id']:
        raise HTTPException(409,'E-mail já verificado em outra conta.')
    code=secrets.token_urlsafe(24)
    sent=send_email(email,'Confirmação de e-mail pessoal no Cognix',
                    'Digite este código no Cognix em até 30 minutos: '+code)
    with session() as db:
        db.execute('''INSERT INTO verification_challenges(id,user_id,email,purpose,code_hash,expires_at)
            VALUES(?,?,?,?,?,?)''',(secrets.token_hex(12),user['id'],email,'personal-email',
                                    hashlib.sha256(code.encode()).hexdigest(),expiry(.5)))
    result={'ok':True,'delivery':'smtp' if sent else 'manual-dev'}
    if not sent:result['development_code']=code
    return result


class VerifyEmail(BaseModel):
    code:str


@router.post('/personal-email/verify')
def verify_personal_email(body:VerifyEmail,user=Depends(require('prof'))):
    with session() as db:
        challenge=db.execute('''SELECT * FROM verification_challenges WHERE user_id=? AND purpose='personal-email'
           AND code_hash=? AND consumed_at IS NULL AND expires_at>?''',
           (user['id'],hashlib.sha256(body.code.encode()).hexdigest(),now())).fetchone()
        if not challenge:raise HTTPException(409,'Código inválido, expirado ou já utilizado.')
        db.execute('INSERT OR IGNORE INTO verified_emails(user_id,email) VALUES(?,?)',(user['id'],challenge['email']))
        db.execute('UPDATE verification_challenges SET consumed_at=? WHERE id=?',(now(),challenge['id']))
        audit(db,user['id'],user['id'],None,'email_verified',{'email':challenge['email']})
    return {'ok':True,'email':challenge['email']}


@router.get('/personal-email')
def personal_emails(user=Depends(require('prof'))):
    return rows('SELECT email,verified_at FROM verified_emails WHERE user_id=? ORDER BY verified_at',(user['id'],))


class TeacherPreferences(BaseModel):
    preferred_subject:str=Field(default='',max_length=80)
    review_layout:str='detailed'


@router.get('/personal/preferences')
def get_personal_preferences(user=Depends(require('prof'))):
    saved=one('SELECT preferences_json FROM teacher_personal_preferences WHERE user_id=?',(user['id'],))
    return json.loads(saved['preferences_json']) if saved else {'preferred_subject':'','review_layout':'detailed'}


@router.put('/personal/preferences')
def set_personal_preferences(body:TeacherPreferences,user=Depends(require('prof'))):
    if body.review_layout not in ('compact','detailed'):
        raise HTTPException(422,'Escolha visualização compacta ou detalhada.')
    values={'preferred_subject':body.preferred_subject.strip(),'review_layout':body.review_layout}
    with session() as db:
        db.execute('''INSERT INTO teacher_personal_preferences(user_id,preferences_json) VALUES(?,?)
                     ON CONFLICT(user_id) DO UPDATE SET preferences_json=excluded.preferences_json,
                     updated_at=CURRENT_TIMESTAMP''',(user['id'],json.dumps(values,ensure_ascii=False)))
    return {'ok':True,'preferences':values}


@router.post('/personal/activate')
def activate_individual_plan(user=Depends(require('prof'))):
    if not one('SELECT 1 FROM verified_emails WHERE user_id=? AND email<>?',(user['id'],user['email'])):
        raise HTTPException(403,'Verifique um e-mail pessoal diferente do institucional antes de ativar o plano.')
    sites=allowed_schools(user)
    for school in sites:
        policy=one('SELECT allow_personal_email FROM school_policy WHERE school_id=?',(school,))
        if not policy or not policy['allow_personal_email']:
            raise HTTPException(403,'A política de uma escola ativa exige conta individual separada.')
    with session() as db:
        identity=_ensure_identity(db,user['id'])
        db.execute("UPDATE users SET account_plan='individual' WHERE id=?",(user['id'],))
        audit(db,user['id'],user['id'],None,'individual_plan_activated',{'identity':identity})
    return {'ok':True,'identity_preserved':True,'school_access_unchanged':True}


class LinkAccounts(BaseModel):
    target_email:str
    target_password:str


@router.post('/link/preview')
def preview_link(body:LinkAccounts,user=Depends(require('prof'))):
    target=one('SELECT * FROM users WHERE email=?',(body.target_email.strip().lower(),))
    if (not target or target['id']==user['id'] or target['role']!='prof' or not target['active'] or
            not password_verify(body.target_password,target['password_hash'])):
        raise HTTPException(403,'É necessário comprovar acesso à segunda conta docente.')
    if target['account_plan']!='individual' or not one('SELECT 1 FROM verified_emails WHERE user_id=?',(target['id'],)):
        raise HTTPException(403,'A conta individual de destino precisa ter e-mail pessoal verificado.')
    eligible=rows('''SELECT q.id,q.title,q.prompt,q.discipline,q.topic,r.review_state,r.category_id
          FROM question_records r JOIN question_collections c ON c.id=r.collection_id
          JOIN questions q ON q.id=r.question_id
          WHERE c.kind='personal' AND c.owner_id=?
          ORDER BY q.imported_at''',(user['id'],))
    ambig=one('''SELECT COUNT(*) n FROM questions q WHERE q.creator_id=?
       AND NOT EXISTS (SELECT 1 FROM question_records r WHERE r.question_id=q.id)''',(user['id'],))['n']
    personal_settings=one('SELECT preferences_json FROM teacher_personal_preferences WHERE user_id=?',(user['id'],))
    target_settings=one('SELECT preferences_json FROM teacher_personal_preferences WHERE user_id=?',(target['id'],))
    challenge=secrets.token_urlsafe(24)
    with session() as db:
        db.execute('INSERT INTO account_link_challenges(id,source_id,target_id,expires_at) VALUES(?,?,?,?)',
                  (hashlib.sha256(challenge.encode()).hexdigest(),user['id'],target['id'],expiry(.5)))
    return {'challenge':challenge,'target':{'id':target['id'],'email':target['email']},
            'eligible':eligible,'ambiguous_legacy_count':ambig,
            'personal_preferences':json.loads(personal_settings['preferences_json']) if personal_settings else None,
            'target_has_preferences':bool(target_settings),
            'excluded':'Turmas, alunos, notas, respostas, relatórios, provas e acervo escolar'}


class ConfirmTransfer(BaseModel):
    challenge:str
    question_ids:list[str]=Field(default_factory=list,max_length=300)
    include_personal_preferences:bool=False
    confirm:bool=False


@router.post('/link/confirm')
def confirm_link(body:ConfirmTransfer,user=Depends(require('prof'))):
    if not body.confirm:raise HTTPException(422,'Confirme a prévia da transferência.')
    with session() as db:
        ch=db.execute('SELECT * FROM account_link_challenges WHERE id=?',
                      (hashlib.sha256(body.challenge.encode()).hexdigest(),)).fetchone()
        if not ch or ch['source_id']!=user['id'] or ch['expires_at']<=now():
            raise HTTPException(409,'Confirmação inválida, expirada ou já utilizada.')
        if ch['confirmed_at']:
            original=set(json.loads(ch['selection_json']))
            if set(body.question_ids)!=original or bool(ch['preferences_transferred'])!=body.include_personal_preferences:
                raise HTTPException(409,'Esta confirmação já foi utilizada com outra seleção.')
            # Repetição idempotente não cria cópias nem revoga permissões.
            return {'ok':True,'already_confirmed':True,'transferred':len(body.question_ids),
                    'target_user_id':ch['target_id'],'preferences_transferred':bool(ch['preferences_transferred'])}
        target=db.execute("SELECT * FROM users WHERE id=? AND role='prof' AND account_plan='individual' AND active=1",(ch['target_id'],)).fetchone()
        if not target or not db.execute('SELECT 1 FROM verified_emails WHERE user_id=?',(target['id'],)).fetchone():
            raise HTTPException(409,'Destino não está verificado.')
        source_id=user['id'];target_id=target['id']
        target_collection=f'personal-{target_id}'
        db.execute('''INSERT OR IGNORE INTO question_collections(id,kind,owner_id,name) VALUES(?,'personal',?,'Meu acervo')''',
                   (target_collection,target_id))
        transfer_batch='transfer-'+hashlib.sha256(ch['id'].encode()).hexdigest()[:20]
        db.execute('''INSERT OR IGNORE INTO question_batches(id,collection_id,uploader_id,origin_format,filename,content_sha256)
                 VALUES(?,?,?,'transfer','Itens particulares transferidos',?)''',
                 (transfer_batch,target_collection,target_id,hashlib.sha256(('transfer:'+ch['id']).encode()).hexdigest()))
        if len(set(body.question_ids))!=len(body.question_ids):raise HTTPException(422,'Itens duplicados na seleção.')
        transferred=[]
        for qid in body.question_ids:
            q=db.execute('''SELECT r.question_id,r.category_id,cat.discipline,cat.topic,cat.normalized
                  FROM question_records r JOIN question_collections c ON c.id=r.collection_id
                  LEFT JOIN question_categories cat ON cat.id=r.category_id
                  WHERE r.question_id=? AND c.kind='personal' AND c.owner_id=?''',
                  (qid,source_id)).fetchone()
            if not q:raise HTTPException(403,'A seleção contém um item sem propriedade comprovada.')
            category_id=None
            if q['category_id']:
                cat=db.execute('''SELECT id FROM question_categories WHERE collection_id=? AND discipline=? AND normalized=?''',
                               (target_collection,q['discipline'],q['normalized'])).fetchone()
                category_id=cat['id'] if cat else secrets.token_hex(12)
                if not cat:db.execute('''INSERT INTO question_categories(id,collection_id,discipline,topic,normalized,confirmed_by)
                        VALUES(?,?,?,?,?,?)''',(category_id,target_collection,q['discipline'],q['topic'],q['normalized'],target_id))
            # O titular muda; a autoria e a procedência da importação permanecem auditáveis.
            db.execute('''UPDATE question_records SET collection_id=?,category_id=? WHERE question_id=?''',
                       (target_collection,category_id,qid))
            # Rascunhos transferidos permanecem editáveis no lote próprio de destino.
            db.execute('''UPDATE question_import_items SET batch_id=?,position=? WHERE question_id=?''',
                       (transfer_batch,len(transferred)+1,qid))
            db.execute('''INSERT OR IGNORE INTO personal_transfers(source_id,target_id,question_id,confirmed_by)
                          VALUES(?,?,?,?)''',(source_id,target_id,qid,source_id))
            transferred.append(qid)
        preferences_transferred=False
        if body.include_personal_preferences:
            private=db.execute('SELECT preferences_json FROM teacher_personal_preferences WHERE user_id=?',(source_id,)).fetchone()
            if not private:raise HTTPException(409,'A origem não possui preferências particulares para transferir.')
            source_preferences=json.loads(private['preferences_json'])
            previous=db.execute('SELECT preferences_json FROM teacher_personal_preferences WHERE user_id=?',(target_id,)).fetchone()
            # Campos já escolhidos na conta de destino prevalecem; não toca em estado escolar.
            destination_preferences=json.loads(previous['preferences_json']) if previous else {}
            combined={**source_preferences,**destination_preferences}
            db.execute('''INSERT INTO teacher_personal_preferences(user_id,preferences_json) VALUES(?,?)
               ON CONFLICT(user_id) DO UPDATE SET preferences_json=excluded.preferences_json,
               updated_at=CURRENT_TIMESTAMP''',(target_id,json.dumps(combined,ensure_ascii=False)))
            preferences_transferred=True
        identity=_ensure_identity(db,source_id)
        _ensure_identity(db,target_id)
        db.execute('UPDATE account_identities SET identity_id=? WHERE user_id=?',(identity,target_id))
        db.execute('''UPDATE account_link_challenges SET confirmed_at=?,selection_json=?,preferences_transferred=?
                      WHERE id=?''',(now(),json.dumps(sorted(transferred)),int(preferences_transferred),ch['id']))
        audit(db,source_id,target_id,None,'personal_transfer',{'items':transferred,
              'preferences_transferred':preferences_transferred})
    return {'ok':True,'transferred':len(transferred),'target_user_id':target_id,
            'preferences_transferred':preferences_transferred}


@router.get('/school/{school_id}/members/{teacher_id}/impact')
def departure_impact(school_id:str,teacher_id:str,user=Depends(require('coord'))):
    assert_school(user,school_id)
    prof=one("SELECT id,name,email,account_plan FROM users WHERE id=? AND role='prof'",(teacher_id,))
    membership=one("SELECT status FROM school_memberships WHERE user_id=? AND school_id=?",(teacher_id,school_id))
    if not prof or not membership:raise HTTPException(404,'Professor não vinculado à escola.')
    other=rows("SELECT school_id FROM school_memberships WHERE user_id=? AND school_id<>? AND status='active'",(teacher_id,school_id))
    # O e-mail institucional verificado não é uma credencial pessoal independente.
    personal_alias=bool(one('''SELECT 1 FROM verified_emails v JOIN users u ON u.id=v.user_id
         WHERE v.user_id=? AND v.email<>u.email''',(teacher_id,)))
    linked_individual=bool(one('''SELECT 1 FROM account_identities ai
         JOIN account_identities linked ON linked.identity_id=ai.identity_id
         JOIN users u ON u.id=linked.user_id
         JOIN verified_emails v ON v.user_id=u.id
         WHERE ai.user_id=? AND linked.user_id<>? AND u.active=1
           AND u.role='prof' AND u.account_plan='individual' LIMIT 1''',(teacher_id,teacher_id)))
    private_count=one('''SELECT COUNT(*) n FROM question_records r JOIN question_collections c ON c.id=r.collection_id
         WHERE c.kind='personal' AND c.owner_id=?''',(teacher_id,))['n']
    return {'professor':prof,'school_id':school_id,'status':membership['status'],
            'other_school_links':other,'verified_personal_access':linked_individual,
            'personal_alias_on_this_credential':personal_alias,
            'personal_questions_remaining':private_count,
            'may_close_dedicated_account':prof['account_plan']=='school' and not other and private_count==0 and not personal_alias,
            'institutional_records_preserved':True,
            'impact':'Acesso institucional da escola encerrado imediatamente; turmas, provas e resultados preservados.'}


class EndSchoolLink(BaseModel):
    confirm:bool=False


@router.post('/school/{school_id}/members/{teacher_id}/end')
def end_link(school_id:str,teacher_id:str,body:EndSchoolLink,user=Depends(require('coord'))):
    assert_school(user,school_id)
    if not body.confirm:raise HTTPException(422,'Confirme o impacto antes de encerrar o vínculo.')
    with session() as db:
        membership=db.execute('SELECT status FROM school_memberships WHERE user_id=? AND school_id=?',(teacher_id,school_id)).fetchone()
        if not membership:raise HTTPException(404,'Vínculo não encontrado.')
        db.execute("UPDATE school_memberships SET status='revoked' WHERE user_id=? AND school_id=?",(teacher_id,school_id))
        audit(db,user['id'],teacher_id,school_id,'school_link_revoked')
    return {'ok':True,'school_access_revoked':True,'institutional_records_preserved':True}


@router.post('/institutional/close')
def close_institutional_account(password:str,confirm:bool=False,user=Depends(require('prof'))):
    if user['account_plan']!='school':raise HTTPException(403,'Ação reservada à credencial institucional dedicada.')
    account=one('SELECT password_hash FROM users WHERE id=?',(user['id'],))
    if not confirm or not password_verify(password,account['password_hash']):
        raise HTTPException(403,'Confirme a ação com a senha da conta institucional.')
    if one('''SELECT 1 FROM question_records r JOIN question_collections c ON c.id=r.collection_id
              WHERE c.kind='personal' AND c.owner_id=? LIMIT 1''',(user['id'],)):
        raise HTTPException(409,'Transfira os itens particulares antes de encerrar esta conta.')
    if len(allowed_schools(user))>1:
        raise HTTPException(409,'Esta credencial tem vínculos com outras escolas. Encerre apenas o vínculo específico.')
    if one('''SELECT 1 FROM verified_emails v JOIN users u ON u.id=v.user_id
             WHERE v.user_id=? AND v.email<>u.email''',(user['id'],)):
        raise HTTPException(409,'Esta credencial também contém e-mail pessoal verificado; ative o plano individual antes de encerrá-la.')
    with session() as db:
        db.execute('UPDATE users SET active=0 WHERE id=?',(user['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        db.execute("UPDATE school_memberships SET status='revoked' WHERE user_id=?",(user['id'],))
        audit(db,user['id'],user['id'],None,'institutional_account_closed')
    return {'ok':True,'institutional_records_preserved':True}


@router.get('/institutional/impact')
def own_account_impact(user=Depends(require('prof'))):
    memberships=rows('SELECT school_id,status FROM school_memberships WHERE user_id=?',(user['id'],))
    personal=rows('''SELECT v.email FROM verified_emails v JOIN users u ON u.id=v.user_id
                     WHERE v.user_id=? AND v.email<>u.email''',(user['id'],))
    private_count=one('''SELECT COUNT(*) n FROM question_records r JOIN question_collections c ON c.id=r.collection_id
              WHERE c.kind='personal' AND c.owner_id=?''',(user['id'],))['n']
    active=[m for m in memberships if m['status']=='active']
    return {'account_plan':user['account_plan'],'memberships':memberships,
            'verified_personal_emails_on_this_credential':personal,
            'can_close_dedicated_credential':user['account_plan']=='school' and len(active)<=1
               and private_count==0 and not personal,
            'personal_questions_remaining':private_count,
            'warning':'Encerrar esta credencial encerra todas as sessões; outros acessos pessoais requerem login próprio verificado. Dados escolares não serão apagados.'}


class ClosePersonal(BaseModel):
    password:str
    confirm:bool=False


@router.get('/personal/close-impact')
def personal_close_impact(user=Depends(require('prof'))):
    if user['account_plan']!='individual':raise HTTPException(403,'Conta individual exigida.')
    return {'active_school_links':allowed_schools(user),
            'personal_questions':one('''SELECT COUNT(*) n FROM question_records r JOIN question_collections c
               ON c.id=r.collection_id WHERE c.kind='personal' AND c.owner_id=?''',(user['id'],))['n'],
            'warning':'A conta e todas as sessões serão desativadas. Vínculos escolares ativos deixam de conceder acesso; provas e registros institucionais permanecem. O acervo privado fica retido sem acesso até recuperação administrativa.'}


@router.post('/personal/close')
def close_personal(body:ClosePersonal,user=Depends(require('prof'))):
    if user['account_plan']!='individual':raise HTTPException(403,'Ação exclusiva do titular da conta pessoal.')
    row=one('SELECT password_hash FROM users WHERE id=?',(user['id'],))
    if not body.confirm or not password_verify(body.password,row['password_hash']):
        raise HTTPException(403,'Confirme explicitamente com a senha da própria conta.')
    with session() as db:
        db.execute('UPDATE users SET active=0 WHERE id=?',(user['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        db.execute("UPDATE school_memberships SET status='revoked' WHERE user_id=?",(user['id'],))
        audit(db,user['id'],user['id'],None,'personal_account_closed')
    return {'ok':True,'institutional_records_preserved':True}


@router.post('/school/{school_id}/members/{teacher_id}/close-institutional-access')
def coordinator_close_institutional_access(school_id:str,teacher_id:str,body:EndSchoolLink,user=Depends(require('coord'))):
    assert_school(user,school_id)
    if not body.confirm:raise HTTPException(422,'Confirme o encerramento definitivo da credencial escolar.')
    impact=departure_impact(school_id,teacher_id,user)
    if not impact['may_close_dedicated_account']:
        raise HTTPException(409,'Conta não é exclusiva ou ainda contém itens particulares a transferir.')
    with session() as db:
        db.execute('UPDATE users SET active=0 WHERE id=?',(teacher_id,))
        db.execute('DELETE FROM sessions WHERE user_id=?',(teacher_id,))
        db.execute("UPDATE school_memberships SET status='revoked' WHERE user_id=? AND school_id=?",
                   (teacher_id,school_id))
        audit(db,user['id'],teacher_id,school_id,'institutional_access_closed_by_school')
    return {'ok':True,'sessions_revoked':True,'institutional_records_preserved':True}


class SchoolPolicy(BaseModel):
    school_id:str
    allow_personal_email:bool=False


@router.post('/school/policy')
def update_school_policy(body:SchoolPolicy,user=Depends(require('coord'))):
    assert_school(user,body.school_id)
    with session() as db:
        db.execute('''INSERT INTO school_policy(school_id,allow_personal_email) VALUES(?,?)
          ON CONFLICT(school_id) DO UPDATE SET allow_personal_email=excluded.allow_personal_email''',
          (body.school_id,int(body.allow_personal_email)))
        audit(db,user['id'],None,body.school_id,'school_policy_updated',{'personal_email':body.allow_personal_email})
    return {'ok':True}


class AuthorizeQuestion(BaseModel):
    school_id:str
    recipient_id:str
    confirm:bool=False


@router.get('/school/{school_id}/external-recipients')
def authorized_recipients(school_id:str,user=Depends(require('coord'))):
    assert_school(user,school_id)
    return rows('''SELECT DISTINCT u.id,u.name,u.email FROM school_memberships m
       JOIN users u ON u.id=m.user_id
       JOIN verified_emails v ON v.user_id=u.id
       WHERE m.school_id=? AND m.status='active' AND u.role='prof'
       AND u.account_plan='individual' AND u.active=1 ORDER BY u.name''',(school_id,))


@router.post('/school/questions/{qid}/authorize')
def authorize_question_reuse(qid:str,body:AuthorizeQuestion,user=Depends(require('coord'))):
    assert_school(user,body.school_id)
    if not body.confirm:raise HTTPException(422,'Confirme a autorização específica desta questão.')
    with session() as db:
        rec=db.execute('''SELECT r.version,q.* FROM question_records r
             JOIN question_collections c ON c.id=r.collection_id
             JOIN questions q ON q.id=r.question_id
             WHERE q.id=? AND c.kind='school' AND c.school_id=?''',(qid,body.school_id)).fetchone()
        target=db.execute("SELECT id FROM users WHERE id=? AND role='prof' AND account_plan='individual' AND active=1",(body.recipient_id,)).fetchone()
        verified=db.execute('SELECT 1 FROM verified_emails WHERE user_id=?',(body.recipient_id,)).fetchone()
        if not rec or rec['status']!='published' or rec['rights_status']!='authorized':
            raise HTTPException(422,'Questão escolar não publicada ou direitos pendentes.')
        if not target or not verified:raise HTTPException(422,'Destinatário precisa de conta individual verificada.')
        frozen={key:rec[key] for key in ('title','context','prompt','alternatives_json','media_json',
                 'correct_letter','discipline','topic','difficulty','source')}
        db.execute('''INSERT INTO question_authorizations(school_id,question_id,recipient_id,authorized_by,question_version,snapshot_json)
            VALUES(?,?,?,?,?,?) ON CONFLICT(school_id,question_id,recipient_id) DO NOTHING''',
            (body.school_id,qid,body.recipient_id,user['id'],rec['version'],json.dumps(frozen,ensure_ascii=False)))
        audit(db,user['id'],body.recipient_id,body.school_id,'question_external_reuse_authorized',{'question_id':qid,'version':rec['version']})
    return {'ok':True,'question_id':qid,'recipient_id':body.recipient_id}


@router.get('/personal/authorized-questions')
def my_authorized_questions(user=Depends(require('prof'))):
    grants=rows('''SELECT school_id,question_id,question_version,snapshot_json
          FROM question_authorizations WHERE recipient_id=?''',(user['id'],))
    result=[]
    for r in grants:
        content=json.loads(r['snapshot_json'])
        media=json.loads(content.get('media_json') or '[]')
        content['media_json']=json.dumps([x.replace('/api/bank/attachments/',
           '/api/accounts/personal/authorized-questions/'+r['question_id']+'/attachment/')
           for x in media],ensure_ascii=False)
        result.append({'school_id':r['school_id'],'question_id':r['question_id'],
                       'version':r['question_version'],'content':content})
    return result


@router.get('/personal/authorized-questions/{qid}/attachment/{attachment_id}')
def authorized_attachment(qid:str,attachment_id:str,user=Depends(require('prof'))):
    grant=one('SELECT snapshot_json FROM question_authorizations WHERE question_id=? AND recipient_id=?',
              (qid,user['id']))
    if not grant:raise HTTPException(404,'Autorização indisponível.')
    frozen=json.loads(grant['snapshot_json'])
    if '/api/bank/attachments/'+attachment_id not in json.loads(frozen.get('media_json') or '[]'):
        raise HTTPException(404,'Mídia não incluída na autorização.')
    attachment=one('''SELECT storage_key,media_type,filename FROM question_attachments
                      WHERE id=? AND question_id=?''',(attachment_id,qid))
    if not attachment or not attachment['media_type'].startswith('image/'):
        raise HTTPException(404,'Mídia indisponível.')
    from .question_bank import STORE
    path=(STORE/attachment['storage_key']).resolve()
    if path.parent!=STORE or not path.is_file():raise HTTPException(404,'Anexo ausente.')
    return FileResponse(path,media_type=attachment['media_type'],filename=attachment['filename'])
