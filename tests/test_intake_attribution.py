"""Intake attribution: the uploader asserts which account a statement
belongs to; the worker verifies against the extracted number. Assertion
wins for filing; mismatch stays visible forever (audit + badge)."""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.parsers.base import ExtractionResult, ExtractedRow
from apps.worker.parsers.extractor import persist_to_db


def _authed(prefix="attrib"):
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


def test_upload_asserts_new_account():
    client, tenant, h = _authed()
    try:
        csv = (b"Date,Description,Amount,Balance\n"
               b"2026-10-10,SHOP,-50.00,100.00\n")
        r = client.post("/v1/documents", headers=h,
                        files={"file": ("stmt.csv", csv, "text/csv")},
                        data={"account_number": "999"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["asserted_account_number"] == "999"
        db = get_db()
        brow = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=?"
            " AND account_number=?", (tenant, "999")).fetchone()
        assert brow is not None
        drow = db.execute(
            "SELECT asserted_account_number FROM source_documents"
            " WHERE id=?", (body["id"],)).fetchone()
        d = dict(drow) if not isinstance(drow, dict) else drow
        assert d["asserted_account_number"] == "999"
    finally:
        cleanup_tenant(tenant)


def test_assertion_wins_and_mismatch_is_audited():
    client, tenant, h = _authed()
    try:
        db = get_db()
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256,"
            " size_bytes, storage_key, status, original_filename,"
            " asserted_account_number) VALUES (?,?,?,?,?,?,?,?)",
            (f"doc-{tenant}", tenant, f"sha-{tenant}", 10, "k",
             "queued", "s.pdf", "999"),
        )
        db.execute(
            "INSERT INTO extraction_runs (id, document_id, status)"
            " VALUES (?,?,?)",
            (f"run-{tenant}", f"doc-{tenant}", "running"),
        )
        db.commit()
        result = ExtractionResult(
            statement={"account_number": "111", "bank": "FNB"},
            rows=[ExtractedRow(
                line_ids=["L001"], date="2026-10-10",
                description="SHOP", amount_minor=-5000,
                direction="debit", balance_after_minor=10000,
                source_quote="SHOP")],
            unaccounted_lines=[], warnings=[],
            opening_balance_minor=None, closing_balance_minor=None)
        persist_to_db(result, f"doc-{tenant}", tenant,
                      f"run-{tenant}")
        trow = db.execute(
            "SELECT account_number FROM transactions"
            " WHERE document_id=?", (f"doc-{tenant}",)).fetchone()
        t = dict(trow) if not isinstance(trow, dict) else trow
        assert t["account_number"] == "999"
        arow = db.execute(
            "SELECT action, payload_json FROM audit_log"
            " WHERE tenant_id=? AND action=?",
            (tenant, "document.account_mismatch")).fetchone()
        assert arow is not None
        docs = client.get("/v1/documents", headers=h).json()
        mine = [d for d in docs if d["id"] == f"doc-{tenant}"][0]
        assert mine["account_match"] == "mismatch"
        assert mine["extracted_account_number"] == "111"
    finally:
        cleanup_tenant(tenant)


def test_match_is_confirmed_and_visible():
    client, tenant, h = _authed()
    try:
        csv = (b"Date,Description,Amount,Balance\n"
               b"2026-10-10,SHOP,-50.00,100.00\n")
        r = client.post("/v1/documents", headers=h,
                        files={"file": ("stmt.csv", csv, "text/csv")},
                        data={"account_number": "999"})
        doc_id = r.json()["id"]
        docs = client.get("/v1/documents", headers=h).json()
        mine = [d for d in docs if d["id"] == doc_id][0]
        assert mine["asserted_account_number"] == "999"
        assert mine["account_match"] == "user-only"
    finally:
        cleanup_tenant(tenant)
