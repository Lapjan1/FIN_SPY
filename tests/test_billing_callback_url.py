# Billing checkout must hand Paystack a callback URL the browser can complete:
# APP_BASE_URL host + user_id query so require_login accepts the redirect.
from fastapi.testclient import TestClient

import apps.api.main as main
from apps.api.main import app
from apps.api.db import init_db, get_db


def _register(client, email):
    db = get_db()
    db.execute("DELETE FROM users WHERE email=?", (email,))
    db.commit()
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test1234", "name": "T", "tenant_id": "cb-tenant"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_checkout_callback_url_carries_user_id(monkeypatch):
    init_db()
    captured = {}
    monkeypatch.setenv("APP_BASE_URL", "https://api.example.test")

    def fake_init(email, plan_code, callback_url, user_id, tenant_id):
        captured["callback_url"] = callback_url
        return {"authorization_url": "https://pay.example/ok", "access_code": "A", "reference": "R"}

    monkeypatch.setattr(main, "initialize_transaction", fake_init)
    client = TestClient(app)
    uid = _register(client, "callback_url@test.com")
    # Reload so the route picks up the monkeypatched APP_BASE_URL (read per-request, no reload needed)
    r = client.post("/v1/billing/checkout?plan_code=individual", headers={"X-User-Id": str(uid)})
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"] == "https://pay.example/ok"
    assert captured["callback_url"] == f"https://api.example.test/v1/billing/callback?user_id={uid}"
