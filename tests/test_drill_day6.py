"""
Day-6 drill chain: real spans persisted (bbox + page dims), sources endpoint
returns dims + doc info, vault file endpoint serves PDF bytes tenant-guarded.
"""
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant
from apps.worker.main import process_one_document
from tests.test_e2e_day2 import create_simple_pdf, get_tmp_path


def _user(client, prefix="drill6"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    return tenant, {"X-User-Id": str(r.json()["id"])}, r.json()["id"]


def _upload_and_process(client, h, uid, tenant):
    tmp_pdf = get_tmp_path("test_drill6")
    assert create_simple_pdf(tmp_pdf)
    with tmp_pdf.open("rb") as f:
        r = client.post("/v1/documents", headers=h,
                        files={"file": (tmp_pdf.name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    tmp_pdf.unlink()
    db = get_db()
    row = db.execute(
        "SELECT id, sha256, storage_key, uploaded_by FROM source_documents"
        " WHERE tenant_id=? ORDER BY uploaded_at_utc DESC LIMIT 1",
        (tenant,)).fetchone()
    d = dict(row)
    status, result = process_one_document(d["id"], tenant, d["sha256"],
                                          d["storage_key"], d["uploaded_by"])
    assert status in ("proposed", "exception")
    assert len(result.rows) >= 1
    return d["id"]


def test_spans_carry_real_bbox_and_dims():
    client = TestClient(app)
    init_db()
    tenant, h, uid = _user(client)
    try:
        doc_id = _upload_and_process(client, h, uid, tenant)
        db = get_db()
        spans = db.execute(
            "SELECT page_no, line_id, bbox_x0, bbox_y0, bbox_x1, bbox_y1,"
            " page_width, page_height FROM source_spans WHERE document_id=?",
            (doc_id,)).fetchall()
        assert len(spans) >= 1
        s = dict(spans[0])
        assert s["page_width"] and s["page_height"], "page dims must persist"
        assert (s["bbox_x0"], s["bbox_y0"], s["bbox_x1"], s["bbox_y1"]) != (0, 0, 100, 10), \
            "placeholder bbox must be replaced by real extraction coords"
        assert s["bbox_x1"] > s["bbox_x0"] and s["bbox_y1"] > s["bbox_y0"]
    finally:
        cleanup_tenant(tenant)


def test_sources_returns_dims_and_doc():
    client = TestClient(app)
    init_db()
    tenant, h, uid = _user(client)
    try:
        doc_id = _upload_and_process(client, h, uid, tenant)
        db = get_db()
        txn = dict(db.execute(
            "SELECT id FROM transactions WHERE document_id=? LIMIT 1",
            (doc_id,)).fetchone())
        r = client.get(f"/v1/transactions/{txn['id']}/sources", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["document_id"] == doc_id
        assert body["page_width"] and body["page_height"]
        assert len(body["bboxes"]) >= 1
        assert body["line_ids"] == [b["line_id"] for b in body["bboxes"]]
        assert client.get("/v1/transactions/nope/sources", headers=h).status_code == 404
    finally:
        cleanup_tenant(tenant)


def test_sources_unlinked_and_cross_tenant():
    client = TestClient(app)
    init_db()
    tenant, h, uid = _user(client, "drill6a")
    tenant2, h2, _ = _user(client, "drill6b")
    try:
        db = get_db()
        txn_id = f"orph-{uuid.uuid4().hex[:6]}"
        db.execute(
            "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (txn_id, tenant, "2026-01-05", "ORPHAN", 100, "debit",
             f"fp-{uuid.uuid4().hex[:8]}", "confirmed"))
        db.commit()
        r = client.get(f"/v1/transactions/{txn_id}/sources", headers=h)
        assert r.status_code == 200
        assert r.json()["unlinked"] is True
        assert r.json()["bboxes"] == []
        r = client.get(f"/v1/transactions/{txn_id}/sources", headers=h2)
        assert r.status_code == 403
    finally:
        cleanup_tenant(tenant)
        cleanup_tenant(tenant2)


def test_document_file_serves_pdf_guarded():
    client = TestClient(app)
    init_db()
    tenant, h, uid = _user(client)
    tenant2, h2, _ = _user(client, "drill6c")
    try:
        doc_id = _upload_and_process(client, h, uid, tenant)
        r = client.get(f"/v1/documents/{doc_id}/file", headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"
        assert client.get("/v1/documents/nope/file", headers=h).status_code == 404
        assert client.get(f"/v1/documents/{doc_id}/file", headers=h2).status_code == 403
    finally:
        cleanup_tenant(tenant)
        cleanup_tenant(tenant2)
