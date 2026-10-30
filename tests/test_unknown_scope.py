"""Pin __unknown scope: empty-account rows selectable, not 422."""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.parsers.registry import seed_coa


def _authed():
    client = TestClient(app)
    init_db()
    tenant = f"unk-{uuid.uuid4().hex[:6]}"
    email = f"unk_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def test_unknown_scope_lists_empty_account_rows():
    client, tenant, h = _authed()
    try:
        db = get_db()
        seed_coa(tenant, template="personal", db=db)
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256,"
            " size_bytes, storage_key, status, original_filename)"
            " VALUES (?,?,?,?,?,?,?)",
            (f"doc-{tenant}-u", tenant, f"sha-{tenant}-u", 10,
             "k-u", "proposed", "mystery.pdf"),
        )
        db.execute(
            "INSERT INTO transactions (id, tenant_id, document_id,"
            " txn_date, description_raw, amount_minor, direction,"
            " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"txn-{tenant}-u", tenant, f"doc-{tenant}-u",
             "2026-10-10", "MYSTERY",
             -100, "debit", f"fp-{tenant}-u", "proposed"),
        )
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-k", tenant, "1000", "Bank K",
             "asset", "999", "personal"),
        )
        db.execute(
            "INSERT INTO transactions (id, tenant_id, account_number,"
            " txn_date, description_raw, amount_minor, direction,"
            " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"txn-{tenant}-k", tenant, "999", "2026-10-10", "KNOWN",
             -200, "debit", f"fp-{tenant}-k", "proposed"),
        )
        db.commit()
        r = client.get("/v1/transactions?account_number=__unknown",
                       headers=h)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["description_raw"] == "MYSTERY"
    finally:
        cleanup_tenant(tenant)


def test_unknown_scope_still_rejects_garbage():
    client, tenant, h = _authed()
    try:
        seed_coa(tenant, template="personal", db=get_db())
        r = client.get("/v1/transactions?account_number=nope-123",
                       headers=h)
        assert r.status_code == 422
    finally:
        cleanup_tenant(tenant)
