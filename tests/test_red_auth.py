"""
Red tests for auth - ensure software fails for right reasons.
Uses unique emails/tenants per test to avoid FK constraint issues.
"""
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.db import init_db, get_db
import uuid

def setup_user_random():
    init_db()
    email = f"red_{uuid.uuid4().hex[:8]}@test.com"
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    r = client.post('/v1/auth/register', json={'email':email,'password':'correct123','name':'Red','tenant_id':tenant})
    assert r.status_code == 200, f"Register failed {r.text}"
    r = client.post('/v1/auth/login', json={'email':email,'password':'correct123'})
    assert r.status_code == 200
    uid = r.json()['id']
    return client, uid, tenant, email

def setup_user_fixed(email, password, tenant):
    init_db()
    db = get_db()
    # Clean dependent in correct order
    db.execute("DELETE FROM transactions WHERE tenant_id=?", (tenant,))
    db.execute("DELETE FROM source_documents WHERE tenant_id=?", (tenant,))
    db.execute("DELETE FROM users WHERE email=?", (email,))
    db.commit()
    client = TestClient(app)
    r = client.post('/v1/auth/register', json={'email':email,'password':password,'name':'Red','tenant_id':tenant})
    # May be 200 or 400 if race, but for fixed we expect 200 after cleanup
    if r.status_code != 200:
        # If still exists, try delete again and register
        db.execute("DELETE FROM users WHERE email=?", (email,))
        db.commit()
        r = client.post('/v1/auth/register', json={'email':email,'password':password,'name':'Red','tenant_id':tenant})
    assert r.status_code == 200, f"Register failed {r.text}"
    r = client.post('/v1/auth/login', json={'email':email,'password':password})
    assert r.status_code == 200
    uid = r.json()['id']
    return client, uid, tenant

def test_login_wrong_password_fails_401():
    client, uid, tenant, email = setup_user_random()
    r = client.post('/v1/auth/login', json={'email':email,'password':'wrongpass'})
    assert r.status_code == 401

def test_register_duplicate_email_fails_400():
    email = f"dup_{uuid.uuid4().hex[:6]}@test.com"
    tenant = f"dup-tenant-{uuid.uuid4().hex[:4]}"
    client, uid, tenant = setup_user_fixed(email, "pass123", tenant)
    r = client.post('/v1/auth/register', json={'email':email,'password':'other123','name':'Dup','tenant_id':'other'})
    assert r.status_code in (400, 409)

def test_reset_invalid_token_fails():
    client = TestClient(app)
    r = client.post('/v1/auth/reset', json={'token':'invalid_token_123456','password':'newpass123'})
    assert r.status_code == 400

def test_reset_expired_token_fails():
    from datetime import datetime, timedelta, timezone
    client, uid, tenant, email = setup_user_random()
    db = get_db()
    token = uuid.uuid4().hex
    expired = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    db.execute("INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?,?,?)", (uid, token, expired))
    db.commit()
    r = client.post('/v1/auth/reset', json={'token':token,'password':'newpass123'})
    assert r.status_code == 400

def test_reset_used_token_fails():
    client, uid, tenant, email = setup_user_random()
    r = client.post('/v1/auth/forgot', json={'email':email})
    assert r.status_code == 200
    token = r.json().get('reset_token')
    assert token
    r = client.post('/v1/auth/reset', json={'token':token,'password':'newpass123'})
    assert r.status_code == 200
    r = client.post('/v1/auth/reset', json={'token':token,'password':'another123'})
    assert r.status_code == 400

def test_non_admin_settings_403():
    client, uid, tenant, email = setup_user_random()
    r = client.get('/v1/settings', headers={'X-User-Id': str(uid)})
    assert r.status_code == 403

def test_trial_exhausted_402():
    client, uid, tenant, email = setup_user_random()
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("trial_pages","1"))
    db.commit()
    import hashlib
    sha = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename, uploaded_by) VALUES (?,?,?,?,?,?,?)",
               (f"doc-trial-{uuid.uuid4().hex[:6]}", tenant, sha, 100, "vault/f.pdf", "f.pdf", uid))
    db.commit()
    r = client.get('/v1/dashboard/summary', headers={'X-User-Id': str(uid)})
    assert r.status_code == 200
    assert r.json().get('trial_pages_remaining') == 0
    files = {'file': ('test.pdf', b'%PDF-1.4 fake', 'application/pdf')}
    r = client.post('/v1/documents', headers={'X-User-Id': str(uid)}, files=files)
    assert r.status_code == 402
    db.execute("DELETE FROM source_documents WHERE tenant_id=?", (tenant,))
    db.execute("DELETE FROM settings WHERE key='trial_pages'")
    db.commit()

def test_cross_tenant_transaction_403():
    import hashlib
    client_a, uid_a, tenant_a, email_a = setup_user_random()
    client_b, uid_b, tenant_b, email_b = setup_user_random()
    db = get_db()
    sha_a = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
    doc_id = f"doc-cross-{uuid.uuid4().hex[:6]}"
    txn_id = f"txn-cross-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename, uploaded_by) VALUES (?,?,?,?,?,?,?)",
               (doc_id, tenant_a, sha_a, 100, "vault/a.pdf", "a.pdf", uid_a))
    db.execute("INSERT INTO transactions (id, tenant_id, document_id, txn_date, description_raw, amount_minor, fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?)",
               (txn_id, tenant_a, doc_id, "2026-10-26", "Test", -10000, "fp-a", "confirmed"))
    db.commit()
    r = client_b.get(f'/v1/transactions/{txn_id}/sources', headers={'X-User-Id': str(uid_b)})
    assert r.status_code == 403
    db.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
    db.execute("DELETE FROM source_documents WHERE id=?", (doc_id,))
    db.commit()

def test_missing_auth_401():
    client = TestClient(app)
    r = client.get('/v1/transactions')
    assert r.status_code == 401
    r = client.get('/v1/dashboard/summary')
    assert r.status_code == 401
