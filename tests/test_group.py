import re

from app.auth.models import Group, GroupMembership, user_datastore
from extensions import db


def test_group_code_format_and_normalization():
    """Verifica che il codice generato rispetti il formato (xxx-yyyy-zzz) e sia normalizzato."""
    pattern = r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$"
    
    # Verifica che 10 codici generati rispettino tutti la regex
    for _ in range(10):
        code = Group.generate_group_code()
        assert re.match(pattern, code) is not None, f"Codice non valido: {code}"
    
    # Normalizzazione con o senza trattini, maiuscole/minuscole
    assert Group.normalize_code("abc-defg-hij") == "abc-defg-hij"
    assert Group.normalize_code("ABC-DEFG-HIJ") == "abc-defg-hij"
    assert Group.normalize_code("abcdefghij") == "abc-defg-hij"
    assert Group.normalize_code("ABCDEFGHIJ") == "abc-defg-hij"
    assert Group.normalize_code("abc defg hij") == "abc-defg-hij"


def test_group_creation_and_ownership(client):
    """Test creazione di un gruppo da parte di un utente autenticato."""
    with client.application.app_context():
        u = user_datastore.find_user(email="alice@example.com")
        if not u:
            u = user_datastore.create_user(
                email="alice@example.com",
                username="alice",
                password="password"
            )
            db.session.commit()

    # Login come Alice
    login_res = client.post('/login', data={'email': 'alice@example.com', 'password': 'password'}, follow_redirects=False)
    print("LOGIN RES:", login_res.status_code, login_res.headers.get('Location'))
    print("LOGIN COOKIE:", client.get_cookie('session'))
    if login_res.status_code == 200:
        print("LOGIN HTML:\n", login_res.data.decode())

    # Creazione del gruppo
    res = client.post('/groups/create', data={
        'name': 'Gruppo Studio',
        'description': 'Gruppo per preparare gli esami'
    }, follow_redirects=False)
    print("CREATE STATUS:", res.status_code, "LOCATION:", res.headers.get('Location'))

    assert res.status_code == 200
    assert b"Gruppo Studio" in res.data
    assert b"owner" in res.data

    with client.application.app_context():
        group = Group.query.filter_by(name='Gruppo Studio').first()
        assert group is not None
        assert re.match(r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$", group.code) is not None
        assert group.security_token is not None
        
        # Verifica membership come owner
        membership = GroupMembership.query.filter_by(group_id=group.id).first()
        assert membership is not None
        assert membership.role == 'owner'
        assert membership.user.username == 'alice'


def test_join_group_by_code(client):
    """Test unione a un gruppo inserendo il codice sia con trattini che compatto."""
    with client.application.app_context():
        owner = user_datastore.find_user(email="owner1@example.com")
        if not owner:
            owner = user_datastore.create_user(email="owner1@example.com", username="owner1", password="password")
        
        bob = user_datastore.find_user(email="bob@example.com")
        if not bob:
            bob = user_datastore.create_user(email="bob@example.com", username="bob", password="password")
            
        group = Group(name="Gruppo Python", code="pyt-test-cod")
        group.generate_security_token()
        db.session.add(group)
        db.session.flush()
        db.session.add(GroupMembership(user_id=owner.id, group_id=group.id, role='owner'))
        db.session.commit()
        group_id = group.id

    # Login come Bob
    client.post('/login', data={'email': 'bob@example.com', 'password': 'password'}, follow_redirects=False)

    # Bob entra inserendo il codice SENZA trattini
    res = client.post('/groups/join', data={'code': 'pyttestcod'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Ti sei unito con successo al gruppo" in res.data
    assert b"Gruppo Python" in res.data

    with client.application.app_context():
        bm = GroupMembership.query.filter_by(user_id=bob.id, group_id=group_id).first()
        assert bm is not None
        assert bm.role == 'member'

    # Bob prova ad unirsi di nuovo (non deve creare duplicati)
    res2 = client.post('/groups/join', data={'code': 'pyt-test-cod'}, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Fai gi" in res2.data  # "Fai già parte del gruppo"


def test_join_group_by_invite_token(client):
    """Test accesso al gruppo tramite link di invito con token di sicurezza."""
    with client.application.app_context():
        owner = user_datastore.find_user(email="owner2@example.com")
        if not owner:
            owner = user_datastore.create_user(email="owner2@example.com", username="owner2", password="password")

        carol = user_datastore.find_user(email="carol@example.com")
        if not carol:
            carol = user_datastore.create_user(email="carol@example.com", username="carol", password="password")

        group = Group(name="Gruppo Dev", code="dev-team-cod")
        token = group.generate_security_token()
        db.session.add(group)
        db.session.flush()
        db.session.add(GroupMembership(user_id=owner.id, group_id=group.id, role='owner'))
        db.session.commit()
        group_id = group.id

    # Login come Carol
    client.post('/login', data={'email': 'carol@example.com', 'password': 'password'}, follow_redirects=False)

    # GET sulla rotta di invito -> mostra la landing page di conferma
    res_get = client.get(f'/groups/join/{token}')
    assert res_get.status_code == 200
    assert b"Gruppo Dev" in res_get.data
    assert b"Accetta Invito" in res_get.data

    # POST per accettare l'invito
    res_post = client.post(f'/groups/join/{token}', follow_redirects=True)
    assert res_post.status_code == 200
    assert b"Ti sei unito con successo al gruppo" in res_post.data

    with client.application.app_context():
        cm = GroupMembership.query.filter_by(user_id=carol.id, group_id=group_id).first()
        assert cm is not None
        assert cm.role == 'member'


def test_token_revocation_and_regeneration(client):
    """Test revoca del token (disabilita i vecchi link) e rigenerazione del token."""
    with client.application.app_context():
        owner = user_datastore.find_user(email="owner3@example.com")
        if not owner:
            owner = user_datastore.create_user(email="owner3@example.com", username="owner3", password="password")

        dave = user_datastore.find_user(email="dave@example.com")
        if not dave:
            dave = user_datastore.create_user(email="dave@example.com", username="dave", password="password")

        group = Group(name="Gruppo Segreto", code="sec-rets-cod")
        old_token = group.generate_security_token()
        db.session.add(group)
        db.session.flush()
        db.session.add(GroupMembership(user_id=owner.id, group_id=group.id, role='owner'))
        db.session.commit()
        group_id = group.id

    # Login come owner
    client.post('/login', data={'email': 'owner3@example.com', 'password': 'password'}, follow_redirects=False)

    # Owner revoca il token
    res_revoke = client.post(f'/groups/{group_id}/token/revoke', follow_redirects=True)
    assert res_revoke.status_code == 200
    assert b"Link di invito revocato con successo" in res_revoke.data

    with client.application.app_context():
        g = Group.query.get(group_id)
        assert g.security_token is None

    # Login come Dave e tentativo di usare il vecchio link
    client.post('/login', data={'email': 'dave@example.com', 'password': 'password'}, follow_redirects=False)
    res_attempt = client.get(f'/groups/join/{old_token}', follow_redirects=True)
    assert b"Link di invito non valido o revocato" in res_attempt.data

    # Owner rigenera un nuovo token
    client.post('/login', data={'email': 'owner3@example.com', 'password': 'password'}, follow_redirects=False)
    res_regen = client.post(f'/groups/{group_id}/token/generate', follow_redirects=True)
    assert res_regen.status_code == 200
    assert b"Nuovo link di invito generato con successo" in res_regen.data

    with client.application.app_context():
        g = Group.query.get(group_id)
        new_token = g.security_token
        assert new_token is not None
        assert new_token != old_token

    # Dave prova il nuovo link ed entra con successo
    client.post('/login', data={'email': 'dave@example.com', 'password': 'password'}, follow_redirects=False)
    res_dave_post = client.post(f'/groups/join/{new_token}', follow_redirects=True)
    assert res_dave_post.status_code == 200
    assert b"Ti sei unito con successo al gruppo" in res_dave_post.data
