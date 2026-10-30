"""
Day-4 audit claim: bad codes raise 500 on some paths instead of 422.
Pins every Invalid-parameters path to 422 with the standard message.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa


def _authed(prefix="inv422"):
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


def _txn(client, tenant, h):
    db = get_db()
    seed_coa(tenant, template="personal", db=db)
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type,"
        " account_number, template) VALUES (?,?,?,?,?,?,?)",
        (f"bank-{tenant}-111", tenant, "1000", "Bank 111",
         "asset", "111", "personal"),
    )
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, f"bank-{tenant}-111", "111", "2026-10-10",
         "SASOL FUEL", -10000, "debit", f"fp-{uuid.uuid4().hex[:8]}",
         "proposed"),
    )
    db.commit()
    return txn_id


def test_bad_category_decide_is_422():
    client, tenant, h = _authed()
    try:
        txn_id = _txn(client, tenant, h)
        r = client.post("/v1/classifications/decide", headers=h, json={
            "transaction_id": txn_id, "nature": "business",
            "business_pct": 100, "category_id": "ZZZ",
            "rationale": "x", "reason": "probe"})
        assert r.status_code == 422, r.text
        assert "Invalid parameters" in r.text
    finally:
        cleanup_tenant(tenant)


def test_bad_vendor_target_is_422():
    client, tenant, h = _authed()
    try:
        _txn(client, tenant, h)
        r = client.post("/v1/vendors/rules", headers=h, json={
            "normalized_merchant": "sasol", "account_number": "111",
            "target_account_id": "no-such-account", "nature": "business",
            "business_pct": 100, "auto_book": False})
        assert r.status_code == 422, r.text
        assert "Invalid parameters" in r.text
    finally:
        cleanup_tenant(tenant)


def test_bad_journal_post_is_422():
    client, tenant, h = _authed()
    try:
        txn_id = _txn(client, tenant, h)
        r = client.post("/v1/journal/post", headers=h, json={
            "transaction_id": txn_id, "category_id": "ZZZ"})
        assert r.status_code == 422, r.text
        assert "Invalid parameters" in r.text
    finally:
        cleanup_tenant(tenant)


def test_blank_review_reason_is_422():
    client, tenant, h = _authed()
    try:
        txn_id = _txn(client, tenant, h)
        r = client.post(f"/v1/review-queue/{txn_id}/accept", headers=h,
                        json={"reason": "   "})
        assert r.status_code == 422, r.text
    finally:
        cleanup_tenant(tenant)
