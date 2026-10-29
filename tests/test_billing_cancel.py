# Cancel subscription: active -> cancelled locally, trial metering resumes (not unlimited).
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db


def _setup(email, status="active"):
    init_db()
    db = get_db()
    db.execute("DELETE FROM users WHERE email=?", (email,))
    db.commit()
    client = TestClient(app)
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test1234", "name": "T", "tenant_id": "cancel-tenant"},
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    db.execute("UPDATE users SET subscription_status=? WHERE id=?", (status, uid))
    db.commit()
    return client, uid


def test_cancel_active_subscription():
    client, uid = _setup("cancel_active@test.com")
    r = client.post("/v1/billing/cancel", headers={"X-User-Id": str(uid)})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    me = client.get("/v1/auth/me", headers={"X-User-Id": str(uid)}).json()
    assert me["is_trial_unlimited"] is False


def test_cancel_without_subscription_is_noop():
    client, uid = _setup("cancel_free@test.com", status="free")
    r = client.post("/v1/billing/cancel", headers={"X-User-Id": str(uid)})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "free"


def test_cancel_requires_login():
    client = TestClient(app)
    r = client.post("/v1/billing/cancel")
    assert r.status_code == 401
