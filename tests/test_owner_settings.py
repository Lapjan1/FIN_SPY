"""
P0-H: tenant owners (default role) may read/change non-secret model/effort
preferences; keys stay admin-only + redacted; billing-ish keys (trial_,
cost guards) stay admin-only. /v1/settings itself stays admin-only
(pinned by tests/test_settings.py).
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _register(prefix, role=None):
    client = TestClient(app)
    init_db()
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    if role:
        db = get_db()
        db.execute("UPDATE users SET role=? WHERE email=?", (role, email))
        db.commit()
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def test_owner_reads_nonsecret_preferences():
    client, tenant, h = _register("ownpref")
    try:
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                   ("model", "muse-spark-1.3"))
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                   ("paystack_secret_key", "sk_live_REAL"))
        db.commit()
        r = client.get("/v1/settings/preferences", headers=h)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["model"] == "muse-spark-1.3"
        assert "paystack_secret_key" not in out
        assert "sk_live_REAL" not in r.text
        # Admin-only table still closed to owners (pinned contract).
        r = client.get("/v1/settings", headers=h)
        assert r.status_code == 403, r.text
    finally:
        cleanup_tenant(tenant)


def test_owner_changes_model_effort_not_secrets_or_billing():
    client, tenant, h = _register("ownw")
    try:
        r = client.post("/v1/settings/preferences", headers=h,
                        json={"key": "model", "value": "muse-spark-1.3"})
        assert r.status_code == 200, r.text
        r = client.post("/v1/settings/preferences", headers=h,
                        json={"key": "effort", "value": "high"})
        assert r.status_code == 200, r.text
        r = client.get("/v1/settings/preferences", headers=h)
        assert r.json()["model"] == "muse-spark-1.3"
        assert r.json()["effort"] == "high"
        # Secrets rejected even for well-formed writes.
        r = client.post("/v1/settings/preferences", headers=h,
                        json={"key": "meta_api_key", "value": "sk_x"})
        assert r.status_code == 400, r.text
        # Billing-ish keys stay admin-only.
        r = client.post("/v1/settings/preferences", headers=h,
                        json={"key": "trial_pages", "value": "99999"})
        assert r.status_code == 403, r.text
    finally:
        cleanup_tenant(tenant)


def test_member_and_anonymous_denied_admin_allowed():
    client, tenant, h = _register("memb", role="member")
    try:
        r = client.get("/v1/settings/preferences", headers=h)
        assert r.status_code == 403, r.text
        r = client.post("/v1/settings/preferences", headers=h,
                        json={"key": "model", "value": "x"})
        assert r.status_code == 403, r.text
    finally:
        cleanup_tenant(tenant)
    client2, tenant2, ha = _register("adm2", role="admin")
    db = get_db()
    cur = db.execute("SELECT value FROM settings WHERE key='trial_pages'")
    row = cur.fetchone()
    prev = (row["value"] if isinstance(row, dict) else row[0]) if row else None
    try:
        r = client2.post("/v1/settings/preferences", headers=ha,
                         json={"key": "trial_pages", "value": "50"})
        assert r.status_code == 200, r.text
        r = client2.get("/v1/settings", headers=ha)
        assert r.status_code == 200, r.text
    finally:
        if prev is None:
            db.execute("DELETE FROM settings WHERE key='trial_pages'")
        else:
            db.execute("UPDATE settings SET value=? WHERE key='trial_pages'",
                       (prev,))
        db.commit()
        cleanup_tenant(tenant2)
    anon = TestClient(app)
    r = anon.get("/v1/settings/preferences")
    assert r.status_code == 401, r.text
