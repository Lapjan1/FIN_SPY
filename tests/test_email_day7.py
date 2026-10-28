"""
Day-7 email wiring: welcome on register, reset on forgot (token emailed in
prod, returned only in dev), dunning on failed payments. Mock path audited,
never leaks tokens to logs.
"""
import uuid

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant


def _audit(tenant, action):
    db = get_db()
    return db.execute("SELECT action, object_id, payload_json FROM audit_log"
                      " WHERE tenant_id=? AND action=?", (tenant, action)).fetchall()


def test_register_sends_welcome_mock():
    client = TestClient(app)
    init_db()
    tenant = f"mail7-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    try:
        r = client.post("/v1/auth/register",
                        json={"email": email, "password": "pass1234",
                              "name": "T", "tenant_id": tenant})
        assert r.status_code == 200
        rows = _audit(tenant, "email.mock_sent")
        assert len(rows) == 1
        assert email in (dict(rows[0]).get("payload_json") or "")
    finally:
        cleanup_tenant(tenant)


def test_forgot_dev_returns_token_and_mocks():
    client = TestClient(app)
    init_db()
    tenant = f"mail7f-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    try:
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/forgot", json={"email": email})
        assert r.status_code == 200
        assert r.json().get("reset_token"), "dev (no key) must return token"
        rows = _audit(tenant, "email.mock_sent")
        assert len(rows) >= 1  # welcome + reset
        # token must not leak into audit payloads
        for row in rows:
            assert r.json()["reset_token"] not in (dict(row).get("payload_json") or "")
    finally:
        cleanup_tenant(tenant)


def test_forgot_prod_emails_without_token(monkeypatch):
    import apps.api.email as mail

    client = TestClient(app)
    init_db()
    tenant = f"mail7p-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return Resp()

    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(mail.requests, "post", fake_post)
    try:
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/forgot", json={"email": email})
        assert r.status_code == 200
        assert "reset_token" not in r.json(), "prod must email, never return token"
        assert len(calls) == 2  # welcome + reset via Resend
        reset_call = calls[1]
        assert reset_call["url"] == "https://api.resend.com/emails"
        assert reset_call["headers"]["Authorization"] == "Bearer re_test_key"
        assert "/reset?token=" in reset_call["json"]["text"]
        rows = _audit(tenant, "email.sent")
        assert len(rows) == 2
    finally:
        cleanup_tenant(tenant)


def test_failed_payment_sends_dunning():
    from apps.api.paystack import handle_webhook_event

    init_db()
    tenant = f"mail7d-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
        db.execute("INSERT INTO users (email, password_hash, name, tenant_id)"
                   " VALUES (?,?,?,?)", (email, "x", "T", tenant))
        db.commit()
        out = handle_webhook_event("invoice.payment_failed",
                                   {"customer": {"email": email}, "reference": "r1"})
        assert out == tenant
        rows = _audit(tenant, "email.mock_sent")
        assert len(rows) == 1
        assert "Payment failed" in (dict(rows[0]).get("payload_json") or "")
    finally:
        cleanup_tenant(tenant)


def test_resend_failure_falls_back_without_smtp(monkeypatch):
    import apps.api.email as mail

    def boom(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(mail.requests, "post", boom)
    # no SMTP configured -> logged as mock, returns True, never raises
    assert mail.send_email("a@test.com", "s", "b", tenant_id="mail7x") is True
