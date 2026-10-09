import os
import pytest
from fastapi.testclient import TestClient
from wichtelzauber.app import app
from wichtelzauber.db import initialize,transaction,connect
from wichtelzauber.security import hash_password,new_id,now
from wichtelzauber.lottery import draw_assignment,ImpossibleDraw

ADMIN_PW='A-strong-dev-password-123'

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('WZ_DATABASE',str(tmp_path/'wz.sqlite3'))
    initialize()
    with transaction() as db:
        db.execute('INSERT INTO admins (id,username,password_hash,created_at) VALUES (?,?,?,?)',
                   (new_id(),'santa',hash_password(ADMIN_PW),now()))
    admin=TestClient(app)
    result=admin.post('/api/admin/login',json={'username':'santa','password':ADMIN_PW})
    assert result.status_code==200,result.text
    token=result.json()['csrf']
    def act(method,url,body=None,client=None,csrf=None):
        c=client or admin
        return c.request(method,url,json=body if body is not None else {},headers={'x-csrf-token':csrf if csrf is not None else token})
    return admin,act,token


def make_group(setup,names=('Elias','Lisa','Mama','Papa')):
    admin,act,csrf=setup
    g=act('POST','/api/admin/groups',{'name':'Familienwichteln','budget_cents':5000,'event_date':'2026-12-24','rules':'Maximal 50 €'})
    assert g.status_code==200,g.text
    gid=g.json()['id']; invite=g.json()['invite_token']
    people={}
    for name in names:
        r=act('POST',f'/api/admin/groups/{gid}/participants',{'name':name})
        assert r.status_code==200,r.text
        people[name]=r.json()['id']
    return gid,invite,people


def enroll(setup,gid,token,people):
    admin,act,csrf=setup
    clients={}
    for i,(name,pid) in enumerate(people.items()):
        c=TestClient(app)
        pin=f'34{i:04d}'
        assert c.post(f'/api/public/{token}/register',json={'participant_id':pid,'pin':pin,'pin_confirm':pin}).status_code==200
        # Can't log in before admin confirms
        assert c.post(f'/api/public/{token}/login',json={'participant_id':pid,'pin':pin}).status_code==403
        assert act('POST',f'/api/admin/groups/{gid}/participants/{pid}/approve').status_code==200
        login=c.post(f'/api/public/{token}/login',json={'participant_id':pid,'pin':pin})
        assert login.status_code==200, login.text
        clients[name]=(c,login.json()['csrf'],pin)
    return clients


def test_draw_couples_and_private_reveal(setup):
    admin,act,csrf=setup
    gid,token,people=make_group(setup)
    # Pair both directions + directional exclusion
    assert act('POST',f'/api/admin/groups/{gid}/exclusions',{'kind':'pair','giver_id':people['Elias'],'receiver_id':people['Lisa']}).status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/exclusions',{'kind':'pair','giver_id':people['Mama'],'receiver_id':people['Papa']}).status_code==200
    clients=enroll(setup,gid,token,people)
    first=act('POST',f'/api/admin/groups/{gid}/draw')
    assert first.status_code==200,first.text
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==400
    # Admin API must not contain assignments even after draw
    detail=act('GET',f'/api/admin/groups/{gid}')
    assert detail.status_code==200
    assert 'assignments' not in detail.text and 'receiver_name' not in detail.text
    chosen={}
    for name,(client,member_csrf,pin) in clients.items():
        r=act('POST','/api/member/reveal',client=client,csrf=member_csrf)
        assert r.status_code==200,r.text
        recipient=r.json()['recipient_name']
        assert recipient != name
        assert r.json()['budget_cents']==5000
        chosen[name]=recipient
        assert act('POST','/api/member/reveal',client=client,csrf=member_csrf).json()['recipient_name']==recipient
    assert len(set(chosen.values()))==len(people)
    assert chosen['Elias']!='Lisa' and chosen['Lisa']!='Elias'
    assert chosen['Mama']!='Papa' and chosen['Papa']!='Mama'
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0]==4
        assert db.execute('SELECT COUNT(*) FROM participants WHERE opened_at IS NOT NULL').fetchone()[0]==4


def test_recovery_keeps_result_invalidates_session(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup)
    clients=enroll(setup,gid,t,ps)
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==200
    c,csrf,pin=clients['Elias']
    first=act('POST','/api/member/reveal',client=c,csrf=csrf).json()['recipient_name']
    assert act('POST',f'/api/admin/groups/{gid}/participants/{ps["Elias"]}/reset').status_code==200
    assert c.get('/api/member/dashboard').status_code==401
    assert c.post(f'/api/public/{t}/login',json={'participant_id':ps['Elias'],'pin':pin}).status_code==403
    new='990011'
    assert c.post(f'/api/public/{t}/register',json={'participant_id':ps['Elias'],'pin':new,'pin_confirm':new}).status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/participants/{ps["Elias"]}/approve').status_code==200
    new_auth=c.post(f'/api/public/{t}/login',json={'participant_id':ps['Elias'],'pin':new})
    second=act('POST','/api/member/reveal',client=c,csrf=new_auth.json()['csrf']).json()['recipient_name']
    assert first==second


def test_registration_collision_and_csrf(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup)
    one=TestClient(app);two=TestClient(app)
    pid=ps['Lisa']
    r=one.post(f'/api/public/{t}/register',json={'participant_id':pid,'pin':'123456','pin_confirm':'123456'})
    assert r.status_code==200
    assert two.post(f'/api/public/{t}/register',json={'participant_id':pid,'pin':'333333','pin_confirm':'333333'}).status_code==409
    assert one.get('/api/member/dashboard').status_code==401
    assert admin.post(f'/api/admin/groups/{gid}/participants',json={'name':'Hacker'}).status_code==403
    assert act('POST',f'/api/admin/groups/{gid}/participants/{pid}/approve').status_code==200
    assert two.post(f'/api/public/{t}/register',json={'participant_id':pid,'pin':'444444','pin_confirm':'444444'}).status_code==409


def test_limits_and_invalid_exclusions(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup,('A','B','C'))
    clients=enroll(setup,gid,t,ps)
    # A cannot draw B and C -> impossible.
    for r in ('B','C'):
        assert act('POST',f'/api/admin/groups/{gid}/exclusions',{'kind':'direct','giver_id':ps['A'],'receiver_id':ps[r]}).status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==400
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM draw_rounds').fetchone()[0]==0
    assert act('POST',f'/api/admin/groups/{gid}/exclusions',{'kind':'pair','giver_id':ps['A'],'receiver_id':ps['A']}).status_code==400


def test_clone_no_secrets_archive_delete(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup)
    pair=act('POST',f'/api/admin/groups/{gid}/exclusions',{'kind':'pair','giver_id':ps['Elias'],'receiver_id':ps['Lisa']})
    assert pair.status_code==200
    clients=enroll(setup,gid,t,ps)
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==200
    result=act('POST',f'/api/admin/groups/{gid}/clone');assert result.status_code==200
    clone_id=result.json()['id']
    detail=act('GET',f'/api/admin/groups/{clone_id}').json()
    assert len(detail['participants'])==4 and len(detail['exclusions'])==2
    assert not detail['drawn'] and all(p['status']=='new' for p in detail['participants'])
    assert act('POST',f'/api/admin/groups/{gid}/archive').status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/participants',{'name':'New'}).status_code==400
    assert act('DELETE',f'/api/admin/groups/{gid}',{'confirmation':'WRONG'}).status_code==400
    assert act('DELETE',f'/api/admin/groups/{gid}',{'confirmation':'Familienwichteln'}).status_code==200
    assert act('GET',f'/api/admin/groups/{gid}').status_code==404


def test_restart_annuls_previous_assignments(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup)
    clients=enroll(setup,gid,t,ps)
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/restart',{'confirmation':'yes'}).status_code==400
    assert act('POST',f'/api/admin/groups/{gid}/restart',{'confirmation':'NEUSTART'}).status_code==200
    c,csrf,pin=clients['Lisa']
    assert act('POST','/api/member/reveal',client=c,csrf=csrf).status_code==400
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==200
    with connect() as db:
        rounds=[r[0] for r in db.execute('SELECT state FROM draw_rounds WHERE group_id=?',(gid,))]
        assert sorted(rounds)==['active','invalidated']


def test_pin_bruteforce_locks_account(setup):
    admin,act,_=setup
    gid,t,ps=make_group(setup)
    client=TestClient(app);pid=ps['Mama']
    assert client.post(f'/api/public/{t}/register',json={'participant_id':pid,'pin':'345678','pin_confirm':'345678'}).status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/participants/{pid}/approve').status_code==200
    for _ in range(5):assert client.post(f'/api/public/{t}/login',json={'participant_id':pid,'pin':'999999'}).status_code==401
    assert client.post(f'/api/public/{t}/login',json={'participant_id':pid,'pin':'345678'}).status_code==429
    with connect() as db:
        assert db.execute('SELECT locked_until FROM participants WHERE id=?',(pid,)).fetchone()[0]


def test_algorithm_impossible_and_properties():
    ids=['1','2','3','4','5','6']
    banned={('1','2'),('2','1'),('3','4'),('4','3'),('5','6'),('6','5')}
    for i in range(30):
        match=draw_assignment(ids,banned)
        assert set(match)==set(ids) and set(match.values())==set(ids)
        assert all(k!=v and (k,v) not in banned for k,v in match.items())
    with pytest.raises(ImpossibleDraw):
        draw_assignment(['1','2','3'],{('1','2'),('1','3')})


def test_wishlist_private_role_and_persistence(setup):
    admin,act,_=setup
    gid,t,people=make_group(setup)
    clients=enroll(setup,gid,t,people)
    for name,(c,csrf,_) in clients.items():
        assert act('PUT','/api/member/wish',{'wish':f'Wunschliste für {name}'},client=c,csrf=csrf).status_code==200
    assert act('POST',f'/api/admin/groups/{gid}/draw').status_code==200
    # Admin must be denied the member-only API even with a valid admin CSRF.
    assert act('POST','/api/member/reveal').status_code==403
    c,csrf,pin=clients['Elias']
    recipient=act('POST','/api/member/reveal',client=c,csrf=csrf).json()
    assert recipient['recipient_wish']==f'Wunschliste für {recipient["recipient_name"]}'
    # Reinitialize the application schema as on restart: persisted result stays.
    initialize()
    assert act('POST','/api/member/reveal',client=c,csrf=csrf).json()==recipient
    assert c.get('/api/admin/groups').status_code==403


def test_only_one_concurrent_draw_succeeds(setup):
    from concurrent.futures import ThreadPoolExecutor
    admin,act,csrf=setup
    gid,t,people=make_group(setup)
    enroll(setup,gid,t,people)
    # Two requests share the same admin credential and arrive in parallel.
    def request_draw(_):
        with TestClient(app) as c:
            c.cookies.update(admin.cookies)
            return c.post(f'/api/admin/groups/{gid}/draw',json={},headers={'x-csrf-token':csrf}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(request_draw,range(2)))
    assert sorted(codes)==[200,400]
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM draw_rounds WHERE group_id=? AND state='active'",(gid,)).fetchone()[0]==1
