"""
P0-F: debt screen extra-cash default comes from the tenant's own ledger
(average monthly net across months with postings), never a hardcoded guess.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _authed(prefix="debtdef"):
    client = TestClient(app)
    init_db()
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def _txn(tenant, date, amount, direction, desc="X"):
    db = get_db()
    db.execute(
        "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
        " amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (f"txn-{uuid.uuid4().hex[:8]}", tenant, date, desc, amount,
         direction, f"fp-{uuid.uuid4().hex[:8]}", "confirmed"),
    )
    db.commit()


def test_debt_defaults_avg_monthly_net():
    client, tenant, h = _authed()
    try:
        # Sep: +20000 in, -5000 out => net +15000. Oct: +10000, -4000 => +6000.
        _txn(tenant, "2026-09-05", 20000, "credit", "PAY")
        _txn(tenant, "2026-09-06", -5000, "debit", "SHOP")
        _txn(tenant, "2026-10-05", 10000, "credit", "PAY")
        _txn(tenant, "2026-10-06", -4000, "debit", "SHOP")
        r = client.get("/v1/debt/defaults", headers=h)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["months"] == 2
        assert out["avg_net_per_month_minor"] == 10500
        assert out["extra_cash_default_minor"] == 10500
    finally:
        cleanup_tenant(tenant)


def test_debt_defaults_empty_and_negative():
    client, tenant, h = _authed()
    try:
        r = client.get("/v1/debt/defaults", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["months"] == 0
        assert r.json()["extra_cash_default_minor"] == 0
        # Net-negative months clamp the default to zero (never negative cash).
        _txn(tenant, "2026-10-05", 1000, "credit", "PAY")
        _txn(tenant, "2026-10-06", -5000, "debit", "SHOP")
        r = client.get("/v1/debt/defaults", headers=h)
        assert r.json()["avg_net_per_month_minor"] == -4000
        assert r.json()["extra_cash_default_minor"] == 0
    finally:
        cleanup_tenant(tenant)
