"""Wichtelzauber: self-hosted Secret Santa app (FastAPI + SQLite)."""
import os
from pathlib import Path
from contextlib import closing
from datetime import date
from typing import Literal
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .db import connect, initialize, transaction, one, all_rows
from .security import (new_id, now, after, hash_password, check_password,
                       create_session, read_session, revoke_all, digest, SESSION_SECONDS)
from .lottery import draw_assignment, ImpossibleDraw

ROOT = Path(__file__).parent
STATIC = ROOT / 'static'
app = FastAPI(title='Wichtelzauber', docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')
initialize()


class AdminLogin(BaseModel):
    username: str
    password: str


class GroupInput(BaseModel):
    name: str
    description: str = ''
    rules: str = ''
    budget_cents: int | None = Field(default=None, ge=0, le=100000000)
    event_date: str | None = None
    location: str = ''


class NameInput(BaseModel):
    name: str


class AuthInput(BaseModel):
    participant_id: str
    pin: str
    pin_confirm: str | None = None


class ExclusionInput(BaseModel):
    kind: Literal['pair', 'direct']
    giver_id: str
    receiver_id: str


class ConfirmationInput(BaseModel):
    confirmation: str


class WishInput(BaseModel):
    wish: str


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


def clean(s, max_length=300, required=False):
    s = str(s or '').strip()
    if required and not s:
        fail('Dieses Feld darf nicht leer sein.')
    if len(s) > max_length:
        fail(f'Maximal {max_length} Zeichen erlaubt.')
    return s


def validate_group(body):
    name = clean(body.name, 100, True)
    desc = clean(body.description, 3000)
    rules = clean(body.rules, 3000)
    place = clean(body.location, 150)
    if body.event_date:
        try:
            date.fromisoformat(body.event_date)
        except ValueError:
            fail('Das Datum ist ungültig.')
    return name, desc, rules, body.budget_cents, body.event_date or None, place


def validate_pin(pin):
    if len(pin) != 6 or not pin.isascii() or not pin.isdecimal():
        fail('Die PIN muss aus genau sechs Ziffern bestehen.')


def must_session(request, conn, kind=None):
    session = read_session(conn, request.cookies.get('wz_session'))
    if not session:
        fail('Bitte melde dich zuerst an.', 401)
    if kind and session['kind'] != kind:
        fail('Keine Berechtigung für diese Aktion.', 403)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if request.headers.get('x-csrf-token') != session['csrf_token']:
            fail('Die Sicherheitsbestätigung fehlt. Bitte Seite neu laden.', 403)
    if session['kind'] == 'admin':
        actor = one(conn, 'SELECT id,username FROM admins WHERE id=?', (session['subject_id'],))
    else:
        actor = one(conn, "SELECT id,group_id,name,status FROM participants WHERE id=? AND status='active'", (session['subject_id'],))
    if not actor:
        fail('Deine Anmeldung ist nicht mehr gültig.', 401)
    return session, dict(actor)


def owned(conn, group_id, admin_id, require_unarchived=False):
    group = one(conn, 'SELECT * FROM groups WHERE id=? AND owner_id=?', (group_id, admin_id))
    if not group:
        fail('Gruppe nicht gefunden.', 404)
    group = dict(group)
    if require_unarchived and group['archived']:
        fail('Diese Gruppe ist archiviert.')
    return group


def get_invite(conn, token):
    group = one(conn, 'SELECT * FROM groups WHERE invite_token=?', (token,))
    if not group:
        fail('Ungültiger oder abgelaufener Einladungslink.', 404)
    return dict(group)


def active_round(conn, gid):
    row = one(conn, "SELECT id,created_at FROM draw_rounds WHERE group_id=? AND state='active'", (gid,))
    return dict(row) if row else None


def status_of(conn, group):
    if group['archived']:
        return 'Archiviert'
    if active_round(conn, group['id']):
        return 'Ausgelost'
    counts = one(conn, "SELECT COUNT(*) AS total, SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS ready, SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending FROM participants WHERE group_id=?", (group['id'],))
    total, ready = counts['total'], counts['ready'] or 0
    if total >= 3 and total == ready:
        return 'Bereit zur Auslosung'
    if ready or counts['pending']:
        return 'Registrierung läuft'
    return 'Vorbereitung'


def public_group(g):
    return {k: g[k] for k in ('id', 'name','description','rules','budget_cents','event_date','location','notice')}


def log(conn, gid, actor, action, detail=''):
    conn.execute('INSERT INTO audit_events VALUES (?,?,?,?,?,?)', (new_id(), gid, actor, action, detail, now()))


def participant_in(conn, gid, pid):
    p = one(conn, 'SELECT * FROM participants WHERE group_id=? AND id=?', (gid, pid))
    if not p:
        fail('Teilnehmer nicht gefunden.', 404)
    return dict(p)


def not_drawn(conn, gid):
    if active_round(conn, gid):
        fail('Die Auslosung ist bereits erfolgt. Diese Einstellung ist gesperrt.')


def cookie(response, raw):
    response.set_cookie('wz_session', raw, max_age=SESSION_SECONDS,
                        httponly=True, secure=os.getenv('WZ_SECURE_COOKIES', '0') == '1',
                        samesite='lax', path='/')


@app.middleware('http')
async def safety_headers(request, call_next):
    if request.url.path.startswith('/api/') and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            return Response('JSON benötigt', status_code=415)
        origin = request.headers.get('origin')
        if origin:
            from urllib.parse import urlsplit
            parsed = urlsplit(origin)
            if parsed.scheme not in ('http', 'https') or parsed.netloc != request.url.netloc:
                return Response('Unzulässiger Ursprung', status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/session')
def session_info(request: Request):
    with closing(connect()) as conn:
        s = read_session(conn, request.cookies.get('wz_session'))
        if not s:
            return {'logged_in': False}
        try:
            _, actor = must_session(request, conn)
        except HTTPException:
            return {'logged_in': False}
        return {'logged_in': True, 'kind': s['kind'], 'name': actor.get('username', actor.get('name')),
                'csrf': s['csrf_token'], 'group_id': actor.get('group_id')}


@app.post('/api/logout')
def logout(request: Request, response: Response):
    with transaction() as conn:
        s = read_session(conn, request.cookies.get('wz_session'))
        if s:
            must_session(request, conn)
            conn.execute('DELETE FROM sessions WHERE token_hash=?', (s['token_hash'],))
    response.delete_cookie('wz_session', path='/')
    return {'ok': True}


@app.post('/api/admin/login')
def admin_login(body: AdminLogin, response: Response):
    username = clean(body.username, 80)
    error = None
    raw, csrf = None, None
    with transaction() as conn:
        a = one(conn, 'SELECT * FROM admins WHERE username=? COLLATE NOCASE', (username,))
        if a and a['locked_until'] and a['locked_until'] > now():
            error = ('Zu viele Versuche. Bitte später erneut anmelden.', 429)
        elif not a or not check_password(a['password_hash'], body.password):
            if a:
                tries = a['failed_attempts'] + 1
                conn.execute('UPDATE admins SET failed_attempts=?,locked_until=? WHERE id=?',
                             (0 if tries >= 5 else tries, after(15*60) if tries >= 5 else None, a['id']))
            error = ('Benutzername oder Passwort ist falsch.', 401)
        else:
            conn.execute('UPDATE admins SET failed_attempts=0,locked_until=NULL WHERE id=?', (a['id'],))
            raw, csrf = create_session(conn, 'admin', a['id'])
    if error:
        fail(*error)
    cookie(response, raw)
    return {'ok': True, 'csrf': csrf}


@app.get('/api/admin/groups')
def admin_groups(request: Request):
    with closing(connect()) as conn:
        _, admin = must_session(request, conn, 'admin')
        gs = all_rows(conn, '''SELECT g.*, (SELECT COUNT(*) FROM participants p WHERE p.group_id=g.id) total,
          (SELECT COUNT(*) FROM participants p WHERE p.group_id=g.id AND p.status='active') ready
          FROM groups g WHERE owner_id=? ORDER BY created_at DESC''', (admin['id'],))
        return {'groups': [{**public_group(g), 'id': g['id'], 'invite_token':g['invite_token'],
                             'archived':bool(g['archived']), 'total':g['total'], 'ready':g['ready'],
                             'status': status_of(conn,g)} for g in gs]}


@app.post('/api/admin/groups')
def create_group(request: Request, body: GroupInput):
    data = validate_group(body)
    with transaction() as conn:
        _, admin = must_session(request, conn, 'admin')
        gid, token = new_id(), __import__('secrets').token_urlsafe(24)
        conn.execute('''INSERT INTO groups (id,owner_id,invite_token,name,description,rules,budget_cents,event_date,location,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)''', (gid, admin['id'], token, *data, now()))
        log(conn, gid, admin['username'], 'Gruppe erstellt')
    return {'id': gid, 'invite_token': token}


@app.get('/api/admin/groups/{gid}')
def group_detail(request: Request, gid: str):
    with closing(connect()) as conn:
        _, admin = must_session(request, conn, 'admin')
        g = owned(conn, gid, admin['id'])
        ps = all_rows(conn, 'SELECT id,name,status,opened_at,created_at FROM participants WHERE group_id=? ORDER BY created_at', (gid,))
        exclusions = all_rows(conn, 'SELECT * FROM exclusions WHERE group_id=? ORDER BY kind,pair_key', (gid,))
        audit = all_rows(conn, 'SELECT actor,action,detail,created_at FROM audit_events WHERE group_id=? ORDER BY created_at DESC LIMIT 25', (gid,))
        return {'group': {**public_group(g), 'status': status_of(conn,g), 'archived':bool(g['archived']),
                          'invite_token':g['invite_token']}, 'participants':ps, 'exclusions':exclusions,
                'audit':audit, 'drawn':bool(active_round(conn,gid))}


@app.patch('/api/admin/groups/{gid}')
def edit_group(request: Request, gid: str, body: GroupInput):
    data = validate_group(body)
    with transaction() as conn:
        _, admin = must_session(request, conn, 'admin')
        owned(conn, gid, admin['id'], True)
        conn.execute('''UPDATE groups SET name=?,description=?,rules=?,budget_cents=?,event_date=?,location=? WHERE id=?''', (*data,gid))
        log(conn,gid,admin['username'],'Gruppendetails geändert')
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/participants')
def add_participant(request:Request, gid:str, body:NameInput):
    name = clean(body.name, 80, True)
    with transaction() as conn:
        _, admin = must_session(request, conn, 'admin')
        owned(conn, gid, admin['id'], True)
        not_drawn(conn,gid)
        total = one(conn,'SELECT COUNT(*) AS n FROM participants WHERE group_id=?',(gid,))['n']
        if total >= 60:
            fail('Pro Gruppe sind höchstens 60 Teilnehmer möglich.')
        pid = new_id()
        conn.execute('INSERT INTO participants (id,group_id,name,created_at) VALUES (?,?,?,?)', (pid,gid,name,now()))
        log(conn,gid,admin['username'],'Teilnehmer hinzugefügt',name)
    return {'id':pid}


@app.patch('/api/admin/groups/{gid}/participants/{pid}')
def rename_participant(request:Request, gid:str, pid:str, body:NameInput):
    name = clean(body.name,80,True)
    with transaction() as conn:
        _, admin = must_session(request, conn, 'admin')
        owned(conn,gid,admin['id'],True)
        not_drawn(conn,gid)
        participant_in(conn,gid,pid)
        conn.execute('UPDATE participants SET name=? WHERE id=?', (name,pid))
        log(conn,gid,admin['username'],'Teilnehmer umbenannt',name)
    return {'ok':True}


@app.delete('/api/admin/groups/{gid}/participants/{pid}')
def delete_participant(request:Request,gid:str,pid:str):
    with transaction() as conn:
        _, admin = must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        not_drawn(conn,gid)
        p = participant_in(conn,gid,pid)
        revoke_all(conn,'member',pid)
        conn.execute('DELETE FROM participants WHERE id=?',(pid,))
        log(conn,gid,admin['username'],'Teilnehmer entfernt',p['name'])
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/participants/{pid}/{action}')
def change_registration(request:Request,gid:str,pid:str,action:Literal['approve','reject','reset']):
    with transaction() as conn:
        _, admin = must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        p = participant_in(conn,gid,pid)
        if action == 'approve':
            if p['status'] != 'pending' or not p['pin_hash']:
                fail('Keine offene Registrierungsanfrage vorhanden.')
            conn.execute("UPDATE participants SET status='active' WHERE id=?",(pid,))
        elif action == 'reject':
            if p['status'] != 'pending':
                fail('Keine offene Registrierungsanfrage vorhanden.')
            conn.execute("UPDATE participants SET status='new',pin_hash=NULL,failed_attempts=0,locked_until=NULL WHERE id=?",(pid,))
            revoke_all(conn,'member',pid)
        elif action == 'reset':
            conn.execute("UPDATE participants SET status='reset',pin_hash=NULL,failed_attempts=0,locked_until=NULL WHERE id=?",(pid,))
            revoke_all(conn,'member',pid)
        log(conn,gid,admin['username'],'Zugang: '+action,p['name'])
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/exclusions')
def add_exclusion(request:Request,gid:str,body:ExclusionInput):
    if body.giver_id == body.receiver_id:
        fail('Eine Person ist bereits von der Selbstziehung ausgeschlossen.')
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        not_drawn(conn,gid)
        participant_in(conn,gid,body.giver_id)
        participant_in(conn,gid,body.receiver_id)
        forward = one(conn,'SELECT id FROM exclusions WHERE group_id=? AND giver_id=? AND receiver_id=?',
                      (gid,body.giver_id,body.receiver_id))
        reverse = one(conn,'SELECT id FROM exclusions WHERE group_id=? AND giver_id=? AND receiver_id=?',
                      (gid,body.receiver_id,body.giver_id))
        if forward or (body.kind=='pair' and reverse):
            fail('Für diese Kombination besteht bereits eine Ausschlussregel.')
        key = new_id() if body.kind=='pair' else None
        for giver, receiver in ([(body.giver_id,body.receiver_id),(body.receiver_id,body.giver_id)]
                                 if body.kind=='pair' else [(body.giver_id,body.receiver_id)]):
            conn.execute('INSERT INTO exclusions VALUES (?,?,?,?,?,?)',
                         (new_id(),gid,giver,receiver,body.kind,key))
        log(conn,gid,admin['username'],'Ausschluss hinzugefügt',body.kind)
    return {'ok':True}


@app.delete('/api/admin/groups/{gid}/exclusions/{eid}')
def delete_exclusion(request:Request,gid:str,eid:str):
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        not_drawn(conn,gid)
        ex = one(conn,'SELECT * FROM exclusions WHERE group_id=? AND (id=? OR pair_key=?)',(gid,eid,eid))
        if not ex: fail('Ausschluss nicht gefunden.',404)
        if ex['kind']=='pair':
            conn.execute('DELETE FROM exclusions WHERE group_id=? AND pair_key=?',(gid,ex['pair_key']))
        else:
            conn.execute('DELETE FROM exclusions WHERE id=?',(ex['id'],))
        log(conn,gid,admin['username'],'Ausschluss entfernt')
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/draw')
def draw(request:Request,gid:str):
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        not_drawn(conn,gid)
        participants = all_rows(conn,'SELECT id,name,status FROM participants WHERE group_id=?',(gid,))
        if len(participants) < 3:
            fail('Mindestens drei Teilnehmer benötigt (vier oder mehr empfohlen).')
        if any(p['status']!='active' for p in participants):
            fail('Vor der Auslosung müssen alle Teilnehmer bestätigt sein.')
        forbidden = [(x['giver_id'],x['receiver_id']) for x in all_rows(conn,'SELECT giver_id,receiver_id FROM exclusions WHERE group_id=?',(gid,))]
        try:
            match = draw_assignment([p['id'] for p in participants],forbidden)
        except ImpossibleDraw as e:
            fail(str(e))
        rid = new_id()
        conn.execute('INSERT INTO draw_rounds (id,group_id,state,created_at) VALUES (?,?,?,?)', (rid,gid,'active',now()))
        for giver,receiver in match.items():
            conn.execute('INSERT INTO assignments VALUES (?,?,?,?)', (new_id(),rid,giver,receiver))
        conn.execute("UPDATE participants SET opened_at=NULL WHERE group_id=?",(gid,))
        conn.execute("UPDATE groups SET notice='' WHERE id=?",(gid,))
        log(conn,gid,admin['username'],'Wichtelrunde ausgelost',f'{len(participants)} Personen')
    return {'ok':True, 'count':len(participants)}


@app.post('/api/admin/groups/{gid}/restart')
def restart(request:Request,gid:str,body:ConfirmationInput):
    if body.confirmation != 'NEUSTART': fail('Bitte NEUSTART zur Bestätigung eingeben.')
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        owned(conn,gid,admin['id'],True)
        round_ = active_round(conn,gid)
        if not round_: fail('Noch keine aktive Auslosung vorhanden.')
        conn.execute("UPDATE draw_rounds SET state='invalidated',invalidated_at=? WHERE id=?",(now(),round_['id']))
        conn.execute('UPDATE participants SET opened_at=NULL WHERE group_id=?',(gid,))
        conn.execute("UPDATE groups SET notice='WICHTIG: Die vorherige Auslosung wurde annulliert. Alle alten Lose sind ungültig. Bitte auf die neue Auslosung warten.' WHERE id=?",(gid,))
        log(conn,gid,admin['username'],'Auslosung annulliert')
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/archive')
def archive(request:Request,gid:str):
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        g = owned(conn,gid,admin['id'])
        conn.execute('UPDATE groups SET archived=? WHERE id=?',(0 if g['archived'] else 1,gid))
        log(conn,gid,admin['username'],'Gruppe archiviert' if not g['archived'] else 'Gruppe wiederhergestellt')
    return {'ok':True}


@app.post('/api/admin/groups/{gid}/clone')
def clone(request:Request,gid:str):
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        old = owned(conn,gid,admin['id'])
        nid,token = new_id(),__import__('secrets').token_urlsafe(24)
        next_name=old['name']+' – Kopie'
        conn.execute('''INSERT INTO groups (id,owner_id,invite_token,name,description,rules,budget_cents,event_date,location,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''', (nid,admin['id'],token,next_name,old['description'],old['rules'],old['budget_cents'],None,old['location'],now()))
        old_to_new={}
        for p in all_rows(conn,'SELECT id,name FROM participants WHERE group_id=?',(gid,)):
            pid = new_id()
            old_to_new[p['id']]=pid
            conn.execute('INSERT INTO participants (id,group_id,name,created_at) VALUES (?,?,?,?)',(pid,nid,p['name'],now()))
        keys={}
        for x in all_rows(conn,'SELECT * FROM exclusions WHERE group_id=?',(gid,)):
            if x['pair_key'] and x['pair_key'] not in keys: keys[x['pair_key']]=new_id()
            conn.execute('INSERT INTO exclusions VALUES (?,?,?,?,?,?)',
                         (new_id(),nid,old_to_new[x['giver_id']],old_to_new[x['receiver_id']],x['kind'],keys.get(x['pair_key'])))
        log(conn,nid,admin['username'],'Aus Gruppe dupliziert',old['name'])
    return {'id':nid,'invite_token':token}


@app.delete('/api/admin/groups/{gid}')
def delete_group(request:Request,gid:str,body:ConfirmationInput):
    with transaction() as conn:
        _,admin=must_session(request,conn,'admin')
        g=owned(conn,gid,admin['id'])
        if body.confirmation != g['name']:
            fail('Bitte den exakten Gruppennamen zur Bestätigung eingeben.')
        conn.execute('DELETE FROM sessions WHERE kind=\'member\' AND subject_id IN (SELECT id FROM participants WHERE group_id=?)',(gid,))
        conn.execute('DELETE FROM groups WHERE id=?',(gid,))
    return {'ok':True}


@app.get('/api/public/{token}')
def public_view(token:str):
    with closing(connect()) as conn:
        g=get_invite(conn,token)
        people = all_rows(conn, 'SELECT id,name,status FROM participants WHERE group_id=? ORDER BY created_at',(g['id'],))
        return {'group':{**public_group(g),'status':status_of(conn,g),'archived':bool(g['archived'])},
                'participants':[{'id':p['id'],'name':p['name'],'status':p['status']} for p in people]}


@app.post('/api/public/{token}/register')
def register(token:str,body:AuthInput):
    validate_pin(body.pin)
    if body.pin_confirm != body.pin:
        fail('Die beiden PIN-Eingaben stimmen nicht überein.')
    with transaction() as conn:
        g=get_invite(conn,token)
        if g['archived']: fail('Diese Gruppe ist archiviert.')
        p=participant_in(conn,g['id'],body.participant_id)
        if p['status'] not in ('new','reset'):
            fail('Dieser Teilnehmer hat bereits einen Zugang oder eine offene Anfrage.',409)
        phash=hash_password(body.pin)
        conn.execute("UPDATE participants SET pin_hash=?,status='pending',failed_attempts=0,locked_until=NULL WHERE id=?",
                     (phash,p['id']))
        log(conn,g['id'],p['name'],'Registrierung angefragt')
    return {'ok':True,'message':'Deine Registrierung wartet auf die Bestätigung des Admins.'}


@app.post('/api/public/{token}/login')
def member_login(token:str,body:AuthInput,response:Response):
    validate_pin(body.pin)
    error = None
    raw,csrf = None,None
    with transaction() as conn:
        g=get_invite(conn,token)
        p=participant_in(conn,g['id'],body.participant_id)
        if p['status']!='active':
            error=('Dieser Zugang ist noch nicht bestätigt oder wurde zurückgesetzt.',403)
        elif p['locked_until'] and p['locked_until'] > now():
            error=('Zu viele Versuche. Bitte in 15 Minuten erneut versuchen.',429)
        elif not check_password(p['pin_hash'],body.pin):
            attempts=p['failed_attempts']+1
            conn.execute('UPDATE participants SET failed_attempts=?,locked_until=? WHERE id=?',
                         (0 if attempts>=5 else attempts,after(15*60) if attempts>=5 else None,p['id']))
            error=('Die PIN ist falsch.',401)
        else:
            conn.execute('UPDATE participants SET failed_attempts=0,locked_until=NULL WHERE id=?',(p['id'],))
            raw,csrf=create_session(conn,'member',p['id'])
    if error:
        fail(*error)
    cookie(response,raw)
    return {'ok':True,'csrf':csrf}


def member_data(conn, member):
    g=one(conn,'SELECT * FROM groups WHERE id=?',(member['group_id'],))
    if not g: fail('Gruppe nicht gefunden.',404)
    r=active_round(conn,g['id'])
    p=participant_in(conn,g['id'],member['id'])
    return dict(g),r,p


@app.get('/api/member/dashboard')
def member_dashboard(request:Request):
    with closing(connect()) as conn:
        _,member=must_session(request,conn,'member')
        g,r,p=member_data(conn,member)
        return {'group':{**public_group(g),'status':status_of(conn,g),'archived':bool(g['archived'])},
                'participant':{'name':p['name'],'wish':p['wish'],'opened_at':p['opened_at']},
                'drawn':bool(r)}


@app.put('/api/member/wish')
def update_wish(request:Request,body:WishInput):
    wish=clean(body.wish,2000)
    with transaction() as conn:
        _,member=must_session(request,conn,'member')
        g,_,_=member_data(conn,member)
        if g['archived']: fail('Archivierte Wunschzettel können nicht bearbeitet werden.')
        conn.execute('UPDATE participants SET wish=? WHERE id=?',(wish,member['id']))
    return {'ok':True}


@app.post('/api/member/reveal')
def reveal(request:Request):
    with transaction() as conn:
        _,member=must_session(request,conn,'member')
        g,r,p=member_data(conn,member)
        if not r: fail('Für diese Gruppe wurde noch nicht ausgelost.')
        a=one(conn,'''SELECT p.name,p.wish FROM assignments a JOIN participants p ON p.id=a.receiver_id
                         WHERE a.round_id=? AND a.giver_id=?''',(r['id'],member['id']))
        if not a: fail('Dein Los konnte nicht gefunden werden.',404)
        if not p['opened_at']:
            conn.execute('UPDATE participants SET opened_at=? WHERE id=?',(now(),member['id']))
        return {'recipient_name':a['name'],'recipient_wish':a['wish'],
                'budget_cents':g['budget_cents'],'event_date':g['event_date']}


@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(STATIC/'manifest.webmanifest',media_type='application/manifest+json')


@app.get('/service-worker.js')
def service_worker():
    return FileResponse(STATIC/'service-worker.js',media_type='text/javascript')


@app.get('/')
@app.get('/admin')
@app.get('/g/{token}')
def index_page(token: str | None = None):
    return FileResponse(STATIC/'index.html',media_type='text/html')
