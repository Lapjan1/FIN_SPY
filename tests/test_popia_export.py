"""
P0-B: POPIA subject-access export - GET /v1/me/export streams a ZIP with
everything held on the caller's tenant, and nothing else.
"""

import io
import json
import uuid
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _register(client, prefix="pop"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234",
              "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return tenant, {"X-User-Id": str(r.json()["id"])}


def _seed_full(tenant, uid, desc="WOOLWORTHS"):
    from apps.worker.parsers.registry import seed_coa

    db = get_db()
    seed_coa(tenant, template="personal", db=db)
    bank_id = f"bank-{tenant}"
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type,"
        " account_number, template) VALUES (?,?,?,?,?,?,?)",
        (bank_id, tenant, "1000", "Bank", "asset", "123456", "personal"),
    )
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, bank_id, "123456", "2026-10-10", desc, -45000,
         "debit", f"fp-{uuid.uuid4().hex[:8]}", "proposed"),
    )
    db.execute(
        "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
        " storage_key, original_filename, uploaded_by, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (f"doc-{tenant}", tenant, f"sha-{tenant}", 9,
         f"data/vault/sha-{tenant}.pdf", "statement.pdf", uid,
         "proposed"),
    )
    db.execute(
        "INSERT INTO flags (id, tenant_id, test_id) VALUES (?,?,?)",
        (f"flag-{tenant}", tenant, "duplicate"),
    )
    db.commit()
    vault = Path(f"data/vault/sha-{tenant}.pdf")
    vault.parent.mkdir(parents=True, exist_ok=True)
    vault.write_bytes(b"%PDF-fake")
    return txn_id, vault


def test_export_downloads_complete_zip():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    uid = int(h["X-User-Id"])
    txn_id, vault = _seed_full(tenant, uid)
    try:
        # Real accept flow so journals + classifications exist.
        r = client.post(f"/v1/review-queue/{txn_id}/accept", headers=h,
                        json={"reason": "seed"})
        assert r.status_code == 200, r.text
        r = client.get("/v1/me/export", headers=h)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("application/zip")
        assert "attachment" in r.headers.get("content-disposition", "")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(zf.namelist())
        for need in ("profile.json", "source_documents.csv", "transactions.csv",
                     "classifications.csv", "accounts.csv",
                     "journal_entries.csv", "journal_lines.csv", "flags.csv",
                     "audit_log.csv", "manifest.json", "README.txt"):
            assert need in names, f"missing {need}"
        assert any(n.startswith("originals/") for n in names)
        # Manifest completeness vs DB row counts (the POPIA check).
        manifest = json.loads(zf.read("manifest.json"))
        db = get_db()
        for table in ("transactions", "classifications", "accounts",
                      "journal_entries", "flags"):
            n = db.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE tenant_id=?",
                (tenant,)).fetchone()
            n = n["c"] if isinstance(n, dict) else n[0]
            assert manifest["tables"][table] == n, table
        n = db.execute(
            "SELECT COUNT(*) AS c FROM journal_lines l"
            " JOIN journal_entries e ON l.entry_id=e.id"
            " WHERE e.tenant_id=?", (tenant,)).fetchone()
        n = n["c"] if isinstance(n, dict) else n[0]
        assert manifest["tables"]["journal_lines"] == n
        # No secrets, no other-tenant bytes.
        blob = r.content
        assert b"password_hash" not in blob
        assert b"$2b$" not in blob
    finally:
        vault.unlink(missing_ok=True)
        cleanup_tenant(tenant)


def test_export_isolates_tenants():
    client = TestClient(app)
    init_db()
    tenant_a, ha = _register(client, prefix="popa")
    tenant_b, hb = _register(client, prefix="popb")
    _, vault_a = _seed_full(tenant_a, int(ha["X-User-Id"]),
                            desc="ALPHA-SECRET-STORE")
    _, vault_b = _seed_full(tenant_b, int(hb["X-User-Id"]), desc="BETA")
    try:
        r = client.get("/v1/me/export", headers=hb)
        assert r.status_code == 200, r.text[:200]
        assert "ALPHA-SECRET-STORE" not in str(r.content)
        assert tenant_a.encode() not in r.content
    finally:
        vault_a.unlink(missing_ok=True)
        vault_b.unlink(missing_ok=True)
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)


def test_export_needs_auth():
    client = TestClient(app)
    r = client.get("/v1/me/export")
    assert r.status_code == 401
