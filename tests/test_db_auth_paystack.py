"""
Test DB + Auth + Paystack adapter (prior art documented in docs/AUTH_PAYSTACK.md)
Per AGENTS.md run before every commit: uv run pytest -q
"""
import hashlib
import hmac
import os
from pathlib import Path

def test_db_dual_init():
    from apps.api.db import init_db, get_db, is_postgres
    init_db()
    db = get_db()
    assert db.backend in ("sqlite","pg")
    # Check tables exist
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table'" if db.backend=="sqlite" else "SELECT tablename FROM pg_tables WHERE schemaname='public'")
    tables = [r[0] for r in cur.fetchall()] if db.backend=="sqlite" else [r["tablename"] for r in cur.fetchall()]
    # At least core tables
    assert "users" in tables
    assert "tenants" in tables
    assert "audit_log" in tables
    assert "source_documents" in tables

def test_hash_chain():
    from apps.api.db import compute_row_hash, get_last_audit_hash, append_audit_log, init_db, get_db
    init_db()
    db = get_db()
    # Clean audit for test tenant
    db.execute("DELETE FROM audit_log WHERE tenant_id='test-chain'")
    db.commit()
    prev = get_last_audit_hash("test-chain")
    assert prev == "0"*64
    h1 = append_audit_log("test-chain", 1, "test.action", "test", "1", {"a":1})
    assert len(h1)==64
    h2 = append_audit_log("test-chain", 1, "test.action2", "test", "2", {"b":2})
    assert h2 != h1
    # Verify chain
    cur = db.execute("SELECT prev_hash, row_hash FROM audit_log WHERE tenant_id='test-chain' ORDER BY id")
    rows = cur.fetchall()
    assert len(rows)>=2
    # Second prev should be first hash
    second_prev = rows[1]["prev_hash"] if isinstance(rows[1], dict) else rows[1][0]
    first_hash = rows[0]["row_hash"] if isinstance(rows[0], dict) else rows[0][1]
    assert second_prev == first_hash

def test_bcrypt_not_sha256():
    from apps.api.auth import hash_password, verify_password, BCRYPT_AVAILABLE
    # Bcrypt should be available and produce $2b$ hash, not 64 hex sha256
    h = hash_password("test123")
    assert "$2b$" in h or "$2a$" in h or len(h)==60  # bcrypt format
    assert h != hashlib.sha256(b"test123").hexdigest()
    assert verify_password("test123", h) is True
    assert verify_password("wrong", h) is False
    # Legacy SHA256 fallback
    legacy = hashlib.sha256(b"test123").hexdigest()
    assert verify_password("test123", legacy) is True

def test_user_isolation():
    from apps.api.db import init_db, get_db, cleanup_tenant
    from apps.api.auth import create_user
    init_db()
    db = get_db()
    # Hermetic vs a live worker: it may attach extraction_runs children to
    # these queued fixture docs between runs, so clean children-first.
    for _t in ("tenant-a", "tenant-b"):
        cleanup_tenant(_t)
    try:
        uid_a = create_user("a@test.com", "pass123", "A", "tenant-a")
        uid_b = create_user("b@test.com", "pass123", "B", "tenant-b")
    except:
        # Already exists, get ids
        cur = db.execute("SELECT id FROM users WHERE email='a@test.com'")
        uid_a = cur.fetchone()[0]
        cur = db.execute("SELECT id FROM users WHERE email='b@test.com'")
        uid_b = cur.fetchone()[0]
    # Create docs for each tenant
    db.execute("DELETE FROM source_documents WHERE tenant_id IN ('tenant-a','tenant-b')")
    db.commit()
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename, uploaded_by) VALUES (?,?,?,?,?,?,?)",
               ("doc-a", "tenant-a", "a"*64, 100, "vault/a.pdf", "a.pdf", uid_a))
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename, uploaded_by) VALUES (?,?,?,?,?,?,?)",
               ("doc-b", "tenant-b", "b"*64, 100, "vault/b.pdf", "b.pdf", uid_b))
    db.commit()
    # Check isolation: tenant-a should see only doc-a
    cur = db.execute("SELECT id FROM source_documents WHERE tenant_id='tenant-a'")
    rows = cur.fetchall()
    ids = [r["id"] if isinstance(r, dict) else r[0] for r in rows]
    assert "doc-a" in ids
    assert "doc-b" not in ids
    for _t in ("tenant-a", "tenant-b"):
        cleanup_tenant(_t)

def test_paystack_timing_safe():
    from apps.api.paystack import verify_paystack_signature
    payload = b'{"event":"charge.success","data":{"customer":{"email":"a@test.com"}}}'
    secret = "sk_test_12345"
    sig = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
    assert verify_paystack_signature(payload, sig, secret) is True
    assert verify_paystack_signature(payload, "bad_sig", secret) is False
    assert verify_paystack_signature(payload, sig, "wrong_secret") is False

def test_trial_pages():
    from apps.api.db import init_db, get_db, cleanup_tenant
    from apps.api.auth import get_trial_pages_remaining, create_user, get_user
    init_db()
    db = get_db()
    # Hermetic vs a live worker (see test_user_isolation).
    cleanup_tenant("trial-tenant")
    try:
        from apps.api.auth import create_user
        uid = create_user("trial@test.com", "pass123", "Trial", "trial-tenant")
    except:
        cur = db.execute("SELECT id FROM users WHERE email='trial@test.com'")
        uid = cur.fetchone()[0]
    # No docs yet, trial 20 default
    remaining = get_trial_pages_remaining(uid)
    assert remaining == 20
    # Add 5 docs
    for i in range(5):
        db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename, uploaded_by) VALUES (?,?,?,?,?,?,?)",
                   (f"doc-trial-{i}", "trial-tenant", f"{i}"*64, 100, f"vault/{i}.pdf", f"{i}.pdf", uid))
    db.commit()
    remaining = get_trial_pages_remaining(uid)
    assert remaining == 15
    # Set subscription active -> None unlimited
    db.execute("UPDATE users SET subscription_status='active' WHERE id=?", (uid,))
    db.commit()
    assert get_trial_pages_remaining(uid) is None
    cleanup_tenant("trial-tenant")
