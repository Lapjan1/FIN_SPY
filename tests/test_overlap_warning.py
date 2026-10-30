"""Overlap honest: same statement plus a few days warns (NDUP flag +
warning + audit) and persists only new rows; per-row skips are counted
(DUP-SKIP), never silent. Unknown-account docs never false-positive."""

import json
import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.main import process_one_document


def _authed(prefix="ovl"):
    client = TestClient(app)
    init_db()
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}, r.json()["id"]


def _csv(rows):
    head = "Date,Description,Amount,Balance\n"
    return (head + "".join(
        f"{d},{desc},{amt},{bal}\n" for d, desc, amt, bal in rows)).encode()


# Balance chaining drops the first raw row, so 6 raw -> 5 extracted.
ROWS_A = [
    ("25 Oct 2026", "WOOLWORTHS", "-450.00", "11550.00"),
    ("26 Oct 2026", "RENT", "-5000.00", "6550.00"),
    ("27 Oct 2026", "SALARY", "20000.00", "26550.00"),
    ("28 Oct 2026", "SPAR", "-300.00", "26250.00"),
    ("29 Oct 2026", "UBER", "-150.00", "26100.00"),
    ("30 Oct 2026", "NETFLIX", "-200.00", "25900.00"),
]
# Same statement plus one day: 5 of 6 extracted rows overlap.
ROWS_B = ROWS_A + [
    ("31 Oct 2026", "SHELL", "-800.00", "25100.00"),
]


def _upload_process(client, h, uid, tenant, payload, name, acct=None):
    data = {"account_number": acct} if acct else {}
    r = client.post("/v1/documents", headers=h,
                    files={"file": (name, payload, "text/csv")},
                    data=data)
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]
    row = get_db().execute(
        "SELECT sha256, storage_key FROM source_documents WHERE id=?",
        (doc_id,)).fetchone()
    d = dict(row)
    process_one_document(doc_id, tenant, d["sha256"],
                         d["storage_key"], uid)
    return doc_id


def _flags(tenant, code):
    cur = get_db().execute(
        "SELECT * FROM flags WHERE tenant_id=? AND test_id=?",
        (tenant, code))
    return [dict(r) if not isinstance(r, dict) else r
            for r in cur.fetchall()]


def _txn_count(tenant):
    cur = get_db().execute(
        "SELECT COUNT(*) AS n FROM transactions WHERE tenant_id=?",
        (tenant,))
    row = cur.fetchone()
    return row["n"] if isinstance(row, dict) else row[0]


def test_overlap_warns_and_persists_new_only():
    client, tenant, h, uid = _authed()
    try:
        _upload_process(client, h, uid, tenant, _csv(ROWS_A),
                        "oct-a.csv", "62123456789")
        assert _txn_count(tenant) == 5
        _upload_process(client, h, uid, tenant, _csv(ROWS_B),
                        "oct-b.csv", "62123456789")
        # 5 old + 1 new; the 5 overlapping rows were not duplicated.
        assert _txn_count(tenant) == 6
        ndup = _flags(tenant, "NDUP")
        assert len(ndup) == 1, "overlap must raise exactly one NDUP flag"
        body = json.loads(ndup[0]["result_json"])
        assert body["overlap"] >= 5
        assert "oct-a.csv" in body.get("overlaps", "")
        skip = _flags(tenant, "DUP-SKIP")
        assert len(skip) == 1
        assert json.loads(skip[0]["result_json"])["skipped"] == 5
        cur = get_db().execute(
            "SELECT COUNT(*) AS n FROM audit_log WHERE tenant_id=?"
            " AND action IN ('persist.overlap','persist.skip')",
            (tenant,))
        row = cur.fetchone()
        n = row["n"] if isinstance(row, dict) else row[0]
        assert n == 2
    finally:
        cleanup_tenant(tenant)


def test_unknown_docs_dont_false_positive():
    client, tenant, h, uid = _authed(prefix="ovlu")
    try:
        _upload_process(client, h, uid, tenant, _csv(ROWS_A),
                        "u-a.csv")
        _upload_process(client, h, uid, tenant, _csv(ROWS_A),
                        "u-b.csv")
        assert _flags(tenant, "NDUP") == []
    finally:
        cleanup_tenant(tenant)
