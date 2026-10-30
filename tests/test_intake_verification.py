"""Intake gate: non-statements are rejected with a verdict (no row, no
quota); real statements carry their verification; gray-zone uploads are
flagged needs_review instead of dying silently in exception."""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _authed(prefix="gate"):
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


def _invoice_pdf():
    import fitz

    d = fitz.open()
    p = d.new_page()
    p.insert_text((72, 72), "INVOICE Acme Corp 123 Main Road Cape Town")
    p.insert_text((72, 92), "Plumbing call-out 2h labour plus parts fitted")
    p.insert_text((72, 112), "Total due 1500 EFT to Acme thank you kindly")
    return d.tobytes()


STATEMENT_CSV = (
    "FNB Statement Account Number 62123456789 Opening Balance 12000.00\n"
    "Date,Description,Amount,Balance\n"
    "25 Oct 2026,WOOLWORTHS,-450.00,11550.00\n"
    "26 Oct 2026,RENT,-5000.00,6550.00\n"
    "27 Oct 2026,SALARY,20000.00,26550.00\n"
    "Closing Balance 26550.00\n"
).encode()

GRAY_CSV = (b"Date,Description,Amount,Balance\n"
            b"2026-10-10,SHOP,-50.00,100.00\n")


def _doc_count(tenant):
    cur = get_db().execute(
        "SELECT COUNT(*) AS n FROM source_documents WHERE tenant_id=?",
        (tenant,))
    row = cur.fetchone()
    return row["n"] if isinstance(row, dict) else row[0]


def test_invoice_rejected_with_verdict_no_quota():
    client, tenant, h = _authed()
    try:
        before = _doc_count(tenant)
        r = client.post("/v1/documents", headers=h,
                        files={"file": ("invoice.pdf", _invoice_pdf(),
                                        "application/pdf")})
        assert r.status_code == 422, r.text
        assert "bank statement" in r.text.lower()
        assert _doc_count(tenant) == before
    finally:
        cleanup_tenant(tenant)


def test_statement_carries_verdict():
    client, tenant, h = _authed()
    try:
        r = client.post("/v1/documents", headers=h,
                        files={"file": ("fnb.csv", STATEMENT_CSV,
                                        "text/csv")})
        assert r.status_code == 200, r.text
        v = r.json()["verification"]
        assert v["is_bank_statement"] is True
        assert v["confidence"] >= 0.5
        assert v["needs_review"] is False
        docs = client.get("/v1/documents", headers=h).json()
        assert docs[0]["verification"]["is_bank_statement"] is True
    finally:
        cleanup_tenant(tenant)


def test_gray_upload_flagged_not_rejected():
    client, tenant, h = _authed()
    try:
        r = client.post("/v1/documents", headers=h,
                        files={"file": ("stmt.csv", GRAY_CSV,
                                        "text/csv")})
        assert r.status_code == 200, r.text
        v = r.json()["verification"]
        assert v["is_bank_statement"] is False
        assert v["needs_review"] is True
    finally:
        cleanup_tenant(tenant)
