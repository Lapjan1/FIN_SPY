"""Tamper wired: every processed doc carries a stored verdict, the
verification endpoint combines intake + tamper + attribution, and an
incrementally-updated PDF is flagged not-original."""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app
from apps.worker.main import process_one_document


def _authed(prefix="tamp"):
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


def _statement_pdf(path: Path, incremental=False):
    import fitz

    d = fitz.open()
    p = d.new_page()
    p.insert_text((72, 72), "FNB Statement Account Number 62123456789")
    p.insert_text((72, 92), "Opening Balance: R12 340.55")
    p.insert_text((72, 112), "25 Oct 2026 SHOP R450.00 R11 890.55")
    p.insert_text((72, 132), "26 Oct 2026 SHOP R450.00 R11 440.55")
    p.insert_text((72, 152), "27 Oct 2026 SHOP R450.00 R10 990.55")
    p.insert_text((72, 172), "Closing Balance: R10 990.55")
    d.save(str(path))
    d.close()
    if incremental:
        # Appended revision: /Prev + second %%EOF, text still extracts.
        with path.open("ab") as f:
            f.write(b"\n% appended revision\n1 0 obj\n<< /Prev 0 >>\n"
                    b"endobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")


def _upload(client, h, path, name):
    with path.open("rb") as f:
        r = client.post("/v1/documents", headers=h,
                        files={"file": (name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_processed_doc_carries_tamper_verdict(tmp_path):
    client, tenant, h, uid = _authed()
    try:
        pdf = tmp_path / "stmt.pdf"
        _statement_pdf(pdf)
        doc_id = _upload(client, h, pdf, "stmt.pdf")
        row = get_db().execute(
            "SELECT sha256, storage_key FROM source_documents WHERE id=?",
            (doc_id,)).fetchone()
        d = dict(row)
        process_one_document(doc_id, tenant, d["sha256"],
                             d["storage_key"], uid)
        docs = client.get("/v1/documents", headers=h).json()
        mine = [x for x in docs if x["id"] == doc_id][0]
        assert mine["tamper"] is not None
        assert mine["tamper"]["is_original_likely"] is True
    finally:
        cleanup_tenant(tenant)


def test_incremental_update_flagged(tmp_path):
    client, tenant, h, uid = _authed()
    try:
        pdf = tmp_path / "edit.pdf"
        _statement_pdf(pdf, incremental=True)
        doc_id = _upload(client, h, pdf, "edit.pdf")
        row = get_db().execute(
            "SELECT sha256, storage_key FROM source_documents WHERE id=?",
            (doc_id,)).fetchone()
        d = dict(row)
        process_one_document(doc_id, tenant, d["sha256"],
                             d["storage_key"], uid)
        r = client.get(f"/v1/documents/{doc_id}/verification",
                       headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tamper"]["is_original_likely"] is False
        assert any("Prev" in i or "EOF" in i
                   for i in body["tamper"]["tamper_indicators"])
        assert "verification" in body  # intake verdict included
        assert "account_match" in body
    finally:
        cleanup_tenant(tenant)


def test_verification_cross_tenant_denied(tmp_path):
    client, tenant, h, uid = _authed(prefix="tampa")
    _, tenant_b, hb, _ = _authed(prefix="tampb")
    try:
        pdf = tmp_path / "stmt.pdf"
        _statement_pdf(pdf)
        doc_id = _upload(client, h, pdf, "stmt.pdf")
        r = client.get(f"/v1/documents/{doc_id}/verification",
                       headers=hb)
        assert r.status_code == 403, r.text
    finally:
        cleanup_tenant(tenant)
        cleanup_tenant(tenant_b)
