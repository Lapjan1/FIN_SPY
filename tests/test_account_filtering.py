"""
Account channel: every function slices by bank account. Two uploads on two
accounts must be listed, told apart (doc + account columns), and filtered
independently. Unknown account numbers 422 like trial-balance does.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa


def _authed(prefix="acctf"):
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


def _seed(tenant):
    db = get_db()
    seed_coa(tenant, template="personal", db=db)
    for acct, bank in (("111", "FNB"), ("222", "ABSA")):
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-{acct}", tenant, "1000", f"{bank} {acct}",
             "asset", acct, "personal"),
        )
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
            " storage_key, status, original_filename, account_number,"
            " bank_name) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"doc-{tenant}-{acct}", tenant, f"sha-{tenant}-{acct}", 10,
             f"k-{acct}", "proposed", f"{bank}.pdf", acct, bank),
        )
        db.execute(
            "INSERT INTO transactions (id, tenant_id, account_id,"
            " account_number, document_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"txn-{tenant}-{acct}", tenant, f"bank-{tenant}-{acct}",
             acct, f"doc-{tenant}-{acct}", "2026-10-10", f"{bank} SHOP",
             -5000, "debit", f"fp-{tenant}-{acct}", "proposed"),
        )
    db.commit()


def test_bank_accounts_lists_both():
    client, tenant, h = _authed()
    try:
        _seed(tenant)
        r = client.get("/v1/bank-accounts", headers=h)
        assert r.status_code == 200, r.text
        rows = {a["account_number"]: a for a in r.json()}
        assert set(rows) == {"111", "222"}
        assert rows["111"]["txn_count"] == 1
        assert "FNB" in (rows["111"].get("bank_name") or "")
    finally:
        cleanup_tenant(tenant)


def test_transactions_filter_by_account_and_doc():
    client, tenant, h = _authed()
    try:
        _seed(tenant)
        r = client.get("/v1/transactions?account_number=111", headers=h)
        assert r.status_code == 200, r.text
        txns = r.json()
        assert len(txns) == 1
        assert txns[0]["account_number"] == "111"
        assert txns[0]["original_filename"] == "FNB.pdf"
        r = client.get(f"/v1/transactions?document_id=doc-{tenant}-222",
                       headers=h)
        assert len(r.json()) == 1
        assert r.json()[0]["account_number"] == "222"
        r = client.get("/v1/transactions?account_number=999", headers=h)
        assert r.status_code == 422, r.text
    finally:
        cleanup_tenant(tenant)


def test_documents_carry_account_columns():
    client, tenant, h = _authed()
    try:
        _seed(tenant)
        r = client.get("/v1/documents", headers=h)
        assert r.status_code == 200, r.text
        by_acct = {d.get("account_number"): d for d in r.json()}
        assert "111" in by_acct and "222" in by_acct
    finally:
        cleanup_tenant(tenant)
