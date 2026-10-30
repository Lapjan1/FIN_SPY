"""
Move out of suspense: confirmed rows (invisible to the review queue) get a
POST /v1/transactions/{id}/move {to_code, reason} that appends a new
classification revision and transfers the posted leg. 9999 drains to zero.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import decide
from apps.api.ledger import post_transaction, trial_balance
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa


def _authed(prefix="move"):
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
        (f"bank-{tenant}-111", tenant, "1000", "Bank 111", "asset",
         "111", "personal"),
    )
    db.commit()


def _txn(tenant):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, f"bank-{tenant}-111", "111", "2026-10-10",
         "MYSTERY DEBIT", -10000, "debit", f"fp-{uuid.uuid4().hex[:8]}",
         "proposed"),
    )
    db.commit()
    return txn_id


def _accept_to_suspense(tenant, txn_id, uid):
    db = get_db()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    txn = dict(row) if not isinstance(row, dict) else row
    cls = decide(txn_id, "unknown", 0, "9999", "unsure", int(uid),
                 "accepting to suspense", tenant)
    post_transaction(txn, {"id": cls["id"], "category_id": "9999",
                          "nature": "unknown", "business_pct": 0})
    db.execute("UPDATE transactions SET status='confirmed' WHERE id=?",
               (txn_id,))
    db.commit()


def _suspense_net(tenant):
    tb = trial_balance(tenant)
    for ln in tb["lines"]:
        if ln["code"] == "9999":
            return ln["debits"] - ln["credits"], tb["balanced"]
    return 0, tb["balanced"]


def test_move_drains_suspense():
    client, tenant, h = _authed()
    uid = h["X-User-Id"]
    try:
        _seed(tenant)
        txn_id = _txn(tenant)
        _accept_to_suspense(tenant, txn_id, uid)
        net0, _ = _suspense_net(tenant)
        assert net0 == 10000
        r = client.post(f"/v1/transactions/{txn_id}/move", headers=h,
                        json={"to_code": "6030",
                              "reason": "till slip says fuel"})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["from_code"] == "9999"
        assert out["to_code"] == "6030"
        assert out["transfer_entry_id"]
        net1, balanced = _suspense_net(tenant)
        assert net1 == 0
        assert balanced is True
        db = get_db()
        cur = db.execute("SELECT COUNT(*) AS c FROM classifications"
                         " WHERE transaction_id=?", (txn_id,))
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == 2
    finally:
        cleanup_tenant(tenant)


def test_move_validates():
    client, tenant, h = _authed()
    uid = h["X-User-Id"]
    try:
        _seed(tenant)
        txn_id = _txn(tenant)
        _accept_to_suspense(tenant, txn_id, uid)
        r = client.post(f"/v1/transactions/{txn_id}/move", headers=h,
                        json={"to_code": "6030", "reason": "  "})
        assert r.status_code == 422, r.text
        r = client.post(f"/v1/transactions/{txn_id}/move", headers=h,
                        json={"to_code": "ZZZ", "reason": "x"})
        assert r.status_code == 422, r.text
        r = client.post(f"/v1/transactions/{txn_id}/move", headers=h,
                        json={"to_code": "9999", "reason": "x"})
        assert r.status_code == 422, r.text
        _, tenant2, h2 = _authed(prefix="move2")
        try:
            r = client.post(f"/v1/transactions/{txn_id}/move", headers=h2,
                            json={"to_code": "6030", "reason": "x"})
            assert r.status_code == 403, r.text
        finally:
            cleanup_tenant(tenant2)
    finally:
        cleanup_tenant(tenant)
