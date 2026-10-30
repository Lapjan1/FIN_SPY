"""Pin __unknown scope on trial, dashboard, auditor-csv, powerbi."""

import csv
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.api.reports import generate_auditor_csv, generate_powerbi_pack
from apps.worker.parsers.registry import seed_coa


def _authed():
    client = TestClient(app)
    init_db()
    tenant = f"unk2-{uuid.uuid4().hex[:6]}"
    email = f"unk2_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def _seed_unknown_txn(tenant):
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
         "2026-10-10", "MYSTERY", -100, "debit",
         f"fp-{tenant}-u", "proposed"),
    )
    db.commit()


def test_unknown_trial_and_dashboard_ok():
    client, tenant, h = _authed()
    try:
        _seed_unknown_txn(tenant)
        r = client.get("/v1/journal/trial-balance"
                       "?account_number=__unknown", headers=h)
        assert r.status_code == 200, r.text
        r = client.get("/v1/dashboard/summary"
                       "?account_number=__unknown", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["totals"]["txn_count"] == 1
    finally:
        cleanup_tenant(tenant)


def test_unknown_auditor_and_powerbi_ok():
    init_db()
    tenant = f"unk3-{uuid.uuid4().hex[:6]}"
    email = f"unk3_{uuid.uuid4().hex[:6]}@test.com"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        _seed_unknown_txn(tenant)
        out = generate_auditor_csv(tenant, account_number="__unknown")
        assert out["count"] == 1
        pack = generate_powerbi_pack(tenant, account_number="__unknown")
        csv_path = Path(pack["csv_dir"]) / "fact_transactions.csv"
        with csv_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["description_raw"] == "MYSTERY"
    finally:
        cleanup_tenant(tenant)
