"""Login seguro para o protótipo: scrypt e sessões opacas em cookie HttpOnly."""
import os, re, secrets, hashlib, hmac, datetime
from fastapi import Request, HTTPException, Depends
from .db import one, session

ROLE_NAMES = {'coord':'Coordenação','prof':'Professor(a)','aluno':'Aluno(a)'}
COOKIE = 'cognix_session'
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

def password_hash(password):
    if len(password) < 10 or len(password) > 256:
        raise HTTPException(422,'A senha deve ter de 10 a 256 caracteres.')
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
    return f'scrypt$16384$8$1${salt.hex()}${dk.hex()}'

def password_verify(password, encoded):
    try:
        _,n,r,p,salt,expected=encoded.split('$')
        dk=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=int(n),r=int(r),p=int(p))
        return hmac.compare_digest(dk,bytes.fromhex(expected))
    except (ValueError,KeyError,TypeError):
        return False

def utc_after(hours):
    return (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=hours)).isoformat()

def new_session(response, user_id):
    token=secrets.token_urlsafe(48)
    token_digest=hashlib.sha256(token.encode()).hexdigest()
    with session() as db:
        db.execute('DELETE FROM sessions WHERE expires_at < ?', (datetime.datetime.now(datetime.timezone.utc).isoformat(),))
        db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',(token_digest,user_id,utc_after(24*7)))
    response.set_cookie(COOKIE,token,httponly=True,samesite='lax',secure=os.getenv('COGNIX_SECURE_COOKIES','0')=='1',max_age=604800,path='/')

def current_user(request:Request):
    token=request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401,'Faça login para continuar.')
    u=one('SELECT u.id,u.name,u.email,u.role,u.active,u.account_plan FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?',(hashlib.sha256(token.encode()).hexdigest(),datetime.datetime.now(datetime.timezone.utc).isoformat()))
    if not u or not u['active']:
        raise HTTPException(401,'Sessão inválida ou expirada.')
    return u

def require(*roles):
    def check(user=Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(403,'Você não tem permissão para esta operação.')
        return user
    return check

def register_user(name,email,password,role,invite='',school_id=''):
    name=(name or '').strip()[:100]
    email=(email or '').strip().lower()
    if len(name)<3 or len(email)>180 or not EMAIL.fullmatch(email):
        raise HTTPException(422,'Informe nome e e-mail válidos.')
    if role not in ('coord','prof','aluno'):
        raise HTTPException(422,'Perfil inválido.')
    pw=password_hash(password)
    school_id=(school_id or '').strip()
    id=secrets.token_hex(12)
    with session() as db:
        if role in ('prof','aluno') and school_id and not db.execute('SELECT 1 FROM schools WHERE id=?',(school_id,)).fetchone():
            raise HTTPException(422,'Escola de cadastro inválida.')
        if (db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone() or
            db.execute('SELECT user_id FROM verified_emails WHERE email=?',(email,)).fetchone()):
            raise HTTPException(409,'Este e-mail já possui cadastro.')
        if role=='coord':
            code_hash=hashlib.sha256(invite.encode()).hexdigest()
            existing=db.execute("SELECT COUNT(*) FROM users WHERE role='coord'").fetchone()[0]
            if existing==0:
                setup=os.getenv('COGNIX_SETUP_CODE','')
                if len(setup)<16 or not hmac.compare_digest(invite,setup):
                    raise HTTPException(403,'Informe o código de configuração inicial da coordenação.')
            else:
                row=db.execute('SELECT * FROM invitations WHERE code_hash=? AND role=? AND used_by IS NULL AND expires_at>datetime(\'now\')',(code_hash,'coord')).fetchone()
                # Datas salvas em UTC YYYY-MM-DD HH:MM:SS
                if not row or (row['email'] and row['email']!=email):
                    raise HTTPException(403,'Convite da coordenação inválido ou expirado.')
        db.execute('INSERT INTO users(id,name,email,password_hash,role,account_plan) VALUES (?,?,?,?,?,?)',(id,name,email,pw,role,'individual' if role=='prof' else 'school'))
        if role in ('prof','aluno') and school_id:
            db.execute('INSERT INTO school_join_requests(id,user_id,school_id) VALUES(?,?,?)',
                       (secrets.token_hex(12),id,school_id))
        if role=='coord':
            if existing>0:
                db.execute('UPDATE invitations SET used_by=? WHERE code_hash=?',(id,code_hash))
                chosen_school = row['school_id'] if row['school_id'] else None
            else:
                chosen_school = os.getenv('COGNIX_SETUP_SCHOOL','escola-x')
            if chosen_school:
                db.execute('INSERT OR IGNORE INTO coordinator_schools(user_id,school_id) VALUES(?,?)',
                           (id,chosen_school))
    return id


def create_school_account(*, creator_id, school_id, name, email, password, role):
    """Provisiona usuário no plano institucional, sem autocadastro ou exposição entre escolas."""
    name=(name or '').strip()
    email=(email or '').strip().lower()
    if not 3 <= len(name) <= 100 or len(email)>180 or not EMAIL.fullmatch(email):
        raise HTTPException(422,'Informe nome e e-mail válidos.')
    if role not in ('coord','prof','aluno'):
        raise HTTPException(422,'Perfil institucional inválido.')
    pw=password_hash(password)
    uid=secrets.token_hex(12)
    with session() as db:
        if (db.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone() or
            db.execute('SELECT 1 FROM verified_emails WHERE email=?',(email,)).fetchone()):
            raise HTTPException(409,'O e-mail já está em uso. Para professor individual, use o pedido de vínculo.')
        # A autorização da escola é repetida na mesma transação da criação.
        if not db.execute('SELECT 1 FROM coordinator_schools WHERE user_id=? AND school_id=?',(creator_id,school_id)).fetchone():
            raise HTTPException(403,'Você só pode criar contas da sua escola.')
        db.execute('''INSERT INTO users(id,name,email,password_hash,role,account_plan)
            VALUES(?,?,?,?,?,?)''',(uid,name,email,pw,role,'school'))
        if role=='coord':
            db.execute('INSERT INTO coordinator_schools(user_id,school_id) VALUES(?,?)',(uid,school_id))
        else:
            db.execute('INSERT INTO school_memberships(user_id,school_id) VALUES(?,?)',(uid,school_id))
    return {'id':uid,'name':name,'email':email,'role':role,'school_id':school_id,'account_plan':'school'}
