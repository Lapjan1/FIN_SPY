"""
Auth posture A (disclose + gate): numeric Bearer / X-User-Id / user_id query
are demo conveniences. DEV_AUTH_ENABLED=false disables all three (401);
default on for the hackathon demo + test suite. Real prod needs JWT -
see README disclosure.
"""

import os

from fastapi.testclient import TestClient

from apps.api.db import init_db, cleanup_tenant
from apps.api.main import app


def test_dev_auth_disabled_rejects_headers(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    import apps.api.auth as auth_mod
    import importlib

    importlib.reload(auth_mod)
    try:
        client = TestClient(app)
        init_db()
        tenant = "devauth-off"
        email = "devauth_off@test.com"
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login",
                        json={"email": email, "password": "pass1234"})
        uid = str(r.json()["id"])
        r = client.get("/v1/books/active",
                       headers={"X-User-Id": uid})
        assert r.status_code == 401, r.text
        r = client.get(f"/v1/books/active?user_id={uid}")
        assert r.status_code == 401, r.text
    finally:
        monkeypatch.undo()
        importlib.reload(auth_mod)
        cleanup_tenant("devauth-off")


def test_dev_auth_enabled_default_allows(monkeypatch):
    monkeypatch.delenv("DEV_AUTH_ENABLED", raising=False)
    import apps.api.auth as auth_mod
    import importlib

    importlib.reload(auth_mod)
    try:
        client = TestClient(app)
        init_db()
        tenant = "devauth-on"
        email = "devauth_on@test.com"
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login",
                        json={"email": email, "password": "pass1234"})
        uid = str(r.json()["id"])
        r = client.get("/v1/books/active",
                       headers={"X-User-Id": uid})
        assert r.status_code == 200, r.text
    finally:
        cleanup_tenant("devauth-on")
