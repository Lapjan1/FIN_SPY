"""
P0-D: trial balance slices per bank account (the missing books primitive).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import decide
from apps.api.ledger import post_transaction, trial_balance
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa

CAT = "6030"  # personal-template expense code


def _setup(prefix="tbacc"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    init_db()
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, f"Test {tenant}"))
    seed_coa(tenant, template="personal", db=db)
    for acct in ("111", "222"):
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-{acct}", tenant, "1000", f"Bank {acct}",
             "asset", acct, "personal"),
        )
    db.commit()
    return tenant


def _post(tenant, acct, amount, direction, desc, cat=CAT):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    bank_id = f"bank-{tenant}-{acct}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, bank_id, acct, "2026-10-10", desc, amount,
         direction, f"fp-{uuid.uuid4().hex[:8]}", "proposed"),
    )
    db.commit()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    txn = dict(row) if not isinstance(row, dict) else row
    cls = decide(txn_id, "business", 100, cat, f"seed {acct}",
                 None, "p0d test", tenant)
    post_transaction(txn, {"id": cls["id"], "category_id": cat,
                          "nature": "business", "business_pct": 100})
    return txn_id


def test_trial_filters_to_bank_account():
    tenant = _setup()
    try:
        _post(tenant, "111", -10000, "debit", "FUEL A")
        _post(tenant, "222", -25000, "debit", "FUEL B")
        full = trial_balance(tenant)
        assert full["balanced"] is True
        assert full["total_debits"] == 35000
        one = trial_balance(tenant, account_number="111")
        assert one["balanced"] is True
        assert one["account_number"] == "111"
        assert one["total_debits"] == 10000
        assert one["total_credits"] == 10000
        codes = {ln["code"] for ln in one["lines"]
                 if ln["debits"] or ln["credits"]}
        assert CAT in codes
        two = trial_balance(tenant, account_number="222")
        assert two["total_debits"] == 25000
        assert (one["total_debits"] + two["total_debits"]
                == full["total_debits"])
    finally:
        cleanup_tenant(tenant)


def test_trial_unknown_account_422():
    tenant = _setup()
    try:
        with pytest.raises(ValueError, match="Invalid parameters"):
            trial_balance(tenant, account_number="999")
    finally:
        cleanup_tenant(tenant)


def test_trial_endpoint_account_filter():
    client = TestClient(app)
    init_db()
    tenant = f"tbapi-{uuid.uuid4().hex[:6]}"
    email = f"tb_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        db = get_db()
        seed_coa(tenant, template="personal", db=db)
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-111", tenant, "1000", "Bank 111",
             "asset", "111", "personal"),
        )
        db.commit()
        _post(tenant, "111", -10000, "debit", "FUEL A")
        r = client.get("/v1/journal/trial-balance?account_number=111",
                       headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["total_debits"] == 10000
        r = client.get("/v1/journal/trial-balance?account_number=999",
                       headers=h)
        assert r.status_code == 422, r.text
    finally:
        cleanup_tenant(tenant)
