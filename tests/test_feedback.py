"""Feedback channel: persist user reports + notify owner, authed + rate-limited.

Red-first: endpoint does not exist yet (expect 404s, not the coded
401/422/429/200 below).
"""
import uuid

from fastapi.testclient import TestClient

from apps.api.db import get_db, init_db
from apps.api.main import app


def _user():
    init_db()
    email = f"fb_{uuid.uuid4().hex[:8]}@test.com"
    tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    r = client.post("/v1/auth/register", json={
        "email": email, "password": "correct123", "name": "Fb",
        "tenant_id": tenant})
    assert r.status_code == 200, f"Register failed {r.text}"
    r = client.post("/v1/auth/login", json={
        "email": email, "password": "correct123"})
    assert r.status_code == 200
    return client, r.json()["id"], tenant


def _post(client, uid, **kw):
    body = {"category": "bug", "subject": "Row missing",
            "message": "A statement row never appeared in Review."}
    body.update(kw)
    return client.post("/v1/feedback", json=body,
                       headers={"X-User-Id": str(uid)})


def test_feedback_requires_auth_401():
    client, _, _ = _user()
    r = client.post("/v1/feedback", json={
        "category": "bug", "subject": "x", "message": "long enough text"})
    assert r.status_code == 401


def test_feedback_valid_persists_200():
    client, uid, tenant = _user()
    r = _post(client, uid)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] and isinstance(data["emailed"], bool)
    db = get_db()
    row = db.execute("SELECT tenant_id, user_id, category, message"
                     " FROM feedback WHERE id=?", (data["id"],)).fetchone()
    row = dict(row) if not isinstance(row, dict) else row
    assert (row["tenant_id"], row["user_id"], row["category"]) == (
        tenant, uid, "bug")
    assert "never appeared" in row["message"]


def test_feedback_short_message_422():
    client, uid, _ = _user()
    r = _post(client, uid, message="too short")
    assert r.status_code == 422


def test_feedback_bad_category_422():
    client, uid, _ = _user()
    r = _post(client, uid, category="spam")
    assert r.status_code == 422


def test_feedback_unknown_document_404():
    client, uid, _ = _user()
    r = _post(client, uid, document_id="doc-does-not-exist")
    assert r.status_code == 404


def test_feedback_rate_limited_429():
    client, uid, _ = _user()
    codes = [_post(client, uid).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5, codes
    assert codes[5] == 429, codes
