"""
P0-G: reject/void is append-only. Proposed -> rejected with no journals;
posted -> mirror-image reversals + rejected, books net to zero, audit shows
the void. Q2: voided rows stay visible as history.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import decide
from apps.api.ledger import post_transaction
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa

CAT = "6030"


def _authed(prefix="rejvoid"):
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
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type,"
        " account_number, template) VALUES (?,?,?,?,?,?,?)",
        (f"bank-{tenant}-111", tenant, "1000", "Bank 111",
         "asset", "111", "personal"),
    )
    db.commit()


def _txn(tenant, status="proposed"):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, f"bank-{tenant}-111", "111", "2026-10-10",
         "VOID ME", -10000, "debit", f"fp-{uuid.uuid4().hex[:8]}", status),
    )
    db.commit()
    return txn_id


def _post(tenant, txn_id, user_id=None):
    db = get_db()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    txn = dict(row) if not isinstance(row, dict) else row
    uid = int(user_id) if user_id else None
    cls = decide(txn_id, "business", 100, CAT, "seed", uid, "p0g", tenant)
    return post_transaction(txn, {"id": cls["id"], "category_id": CAT,
                             "nature": "business", "business_pct": 100})


def _journals_net(tenant, txn_id):
    db = get_db()
    cur = db.execute(
        "SELECT COALESCE(SUM(jl.debit_minor),0) AS d,"
        " COALESCE(SUM(jl.credit_minor),0) AS c,"
        " COUNT(DISTINCT je.id) AS n FROM journal_lines jl"
        " JOIN journal_entries je ON jl.entry_id=je.id"
        " WHERE je.tenant_id=? AND je.transaction_id=?",
        (tenant, txn_id))
    r = cur.fetchone()
    d = dict(r) if not isinstance(r, dict) else r
    return d["d"], d["c"], d["n"]


def test_reject_proposed_no_journals():
    client, tenant, h = _authed()
    try:
        _seed(tenant)
        txn_id = _txn(tenant)
        r = client.post(f"/v1/review-queue/{txn_id}/reject",
                        json={"reason": "duplicate of paper receipt"}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"
        assert r.json()["reversed_entry_ids"] == []
        d, c, n = _journals_net(tenant, txn_id)
        assert (d, c, n) == (0, 0, 0)
        db = get_db()
        cur = db.execute("SELECT status FROM transactions WHERE id=?", (txn_id,))
        row = cur.fetchone()
        assert (row["status"] if isinstance(row, dict) else row[0]) == "rejected"
    finally:
        cleanup_tenant(tenant)


def test_void_posted_nets_zero_and_audited():
    client, tenant, h = _authed()
    uid = h["X-User-Id"]
    try:
        _seed(tenant)
        txn_id = _txn(tenant, status="confirmed")
        _post(tenant, txn_id, uid)
        d0, c0, n0 = _journals_net(tenant, txn_id)
        assert n0 == 1 and d0 == c0 == 10000
        r = client.post(f"/v1/review-queue/{txn_id}/reject",
                        json={"reason": "charged in error"}, headers=h)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "rejected"
        assert len(out["reversed_entry_ids"]) == 1
        d, c, n = _journals_net(tenant, txn_id)
        assert n == 2  # original + reversal both remain (Q2 history)
        assert d == c == 20000  # mirror image nets to zero effect
        from apps.api.ledger import trial_balance
        tb = trial_balance(tenant)
        assert tb["balanced"] is True
        assert tb["total_debits"] == tb["total_credits"] == 20000
        db = get_db()
        cur = db.execute(
            "SELECT COUNT(*) AS c FROM audit_log WHERE tenant_id=?"
            " AND action IN ('review.reject','ledger.void')", (tenant,))
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) >= 1
    finally:
        cleanup_tenant(tenant)


def test_reject_requires_reason_and_ownership():
    client, tenant, h = _authed()
    try:
        _seed(tenant)
        txn_id = _txn(tenant)
        r = client.post(f"/v1/review-queue/{txn_id}/reject",
                        json={"reason": "  "}, headers=h)
        assert r.status_code == 422, r.text
        r = client.post("/v1/review-queue/nope/reject",
                        json={"reason": "x"}, headers=h)
        assert r.status_code == 422, r.text
        _, tenant2, h2 = _authed(prefix="rejvoid2")
        try:
            r = client.post(f"/v1/review-queue/{txn_id}/reject",
                            json={"reason": "x"}, headers=h2)
            assert r.status_code == 403, r.text
        finally:
            cleanup_tenant(tenant2)
    finally:
        cleanup_tenant(tenant)
