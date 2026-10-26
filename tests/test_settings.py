"""
Test Settings UI for Meta models compliance - admin-only + forbidden secret keys
Per docs/SETTINGS.md hackathon guidelines: pure Meta, no openai phi4, ollama-local only fallback, admin-only keys redacted, user-visible read-only model/effort/cost, freellmapi active badge + meta pending warning
"""
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.db import init_db, get_db

def setup_admin():
    init_db()
    db = get_db()
    db.execute("DELETE FROM users WHERE email='admin_settings@test.com'")
    db.commit()
    client = TestClient(app)
    client.post('/v1/auth/register', json={'email':'admin_settings@test.com','password':'admin123','name':'Admin','tenant_id':'admin-tenant'})
    db.execute("UPDATE users SET role='admin' WHERE email='admin_settings@test.com'")
    db.commit()
    r = client.post('/v1/auth/login', json={'email':'admin_settings@test.com','password':'admin123'})
    uid = r.json()['id']
    return client, uid

def test_settings_admin_only():
    client, admin_uid = setup_admin()
    # Non-admin user
    client.post('/v1/auth/register', json={'email':'user_settings@test.com','password':'user123','name':'User','tenant_id':'user-tenant'})
    r = client.post('/v1/auth/login', json={'email':'user_settings@test.com','password':'user123'})
    user_uid = r.json()['id']
    # Non-admin should 403
    r = client.get('/v1/settings', headers={'X-User-Id': str(user_uid)})
    assert r.status_code == 403
    # Admin should 200
    r = client.get('/v1/settings', headers={'X-User-Id': str(admin_uid)})
    assert r.status_code == 200

def test_settings_forbidden_secret():
    client, admin_uid = setup_admin()
    # Try to set META_API_KEY via API should 400 per docs/SETTINGS.md - must be env var
    r = client.post('/v1/settings', headers={'X-User-Id': str(admin_uid)}, json={'key':'meta_api_key','value':'sk_test_123'})
    assert r.status_code == 400
    assert 'must be env var' in r.json()['detail']
    # Try paystack_secret_key
    r = client.post('/v1/settings', headers={'X-User-Id': str(admin_uid)}, json={'key':'paystack_secret_key','value':'sk_test_123'})
    assert r.status_code == 400
    # Allowed: model
    r = client.post('/v1/settings', headers={'X-User-Id': str(admin_uid)}, json={'key':'model','value':'muse-spark-1.3'})
    assert r.status_code == 200
    assert r.json()['ok'] is True

def test_privacy_terms_endpoints():
    client = TestClient(app)
    r = client.get('/privacy')
    assert r.status_code == 200
    assert r.json()['page'] == 'privacy'
    assert 'POPIA' in r.json()['content_markdown'] or 'adapted' in r.json()['source'].lower()
    r = client.get('/terms')
    assert r.status_code == 200
    assert r.json()['page'] == 'terms'
    r = client.get('/refund')
    assert r.status_code == 200
    assert r.json()['page'] == 'refund'
    r = client.get('/ai-disclosure')
    assert r.status_code == 200
    assert 'muse-spark-1.3' in r.json()['content_markdown'] or 'spark' in str(r.json()['models']).lower()
