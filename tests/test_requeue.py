"""
Requeue: retry a failed (exception) document, the only re-run path since
re-uploading identical bytes returns duplicate:true without reprocessing.

Regression for: 3-page FNB statement processed to exception + 0 rows with no
way to retry (upload swallows the retry as a duplicate).
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _register(client, prefix="req"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234",
              "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    uid = r.json()["id"]
    return tenant, {"X-User-Id": str(uid)}


def _doc(tenant, status, uid=1):
    db = get_db()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
        " storage_key, original_filename, uploaded_by, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (doc_id, tenant, f"sha-{uuid.uuid4().hex[:8]}", 1234,
         f"data/vault/{doc_id}.pdf", "statement.pdf", uid, status),
    )
    db.commit()
    return doc_id


def test_requeue_exception_back_to_queued():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        doc_id = _doc(tenant, "exception")
        r = client.post(f"/v1/documents/{doc_id}/requeue", headers=h)
        assert r.status_code == 200, r.text
        assert r.json() == {"id": doc_id, "status": "queued", "requeued": True}
        docs = {d["id"]: d for d in
                client.get("/v1/documents", headers=h).json()}
        assert docs[doc_id]["status"] == "queued"
    finally:
        cleanup_tenant(tenant)


def test_requeue_queued_is_idempotent():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        doc_id = _doc(tenant, "queued")
        r = client.post(f"/v1/documents/{doc_id}/requeue", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["requeued"] is False
    finally:
        cleanup_tenant(tenant)


def test_requeue_rejects_non_failed():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        doc_id = _doc(tenant, "proposed")
        r = client.post(f"/v1/documents/{doc_id}/requeue", headers=h)
        assert r.status_code == 422, r.text
        assert "only failed" in r.text
    finally:
        cleanup_tenant(tenant)


def test_requeue_missing_cross_tenant_no_auth():
    client = TestClient(app)
    init_db()
    tenant_a, ha = _register(client, prefix="reqa")
    tenant_b, hb = _register(client, prefix="reqb")
    try:
        r = client.post("/v1/documents/doc-nope/requeue", headers=ha)
        assert r.status_code == 404, r.text
        doc_id = _doc(tenant_a, "exception")
        r = client.post(f"/v1/documents/{doc_id}/requeue", headers=hb)
        assert r.status_code == 403, r.text
        r = client.post(f"/v1/documents/{doc_id}/requeue")
        assert r.status_code == 401, r.text
    finally:
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)


def test_requeue_consumes_no_trial():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        before = client.get("/v1/auth/me", headers=h).json()[
            "trial_pages_remaining"]
        doc_id = _doc(tenant, "exception")
        r = client.post(f"/v1/documents/{doc_id}/requeue", headers=h)
        assert r.status_code == 200, r.text
        after = client.get("/v1/auth/me", headers=h).json()[
            "trial_pages_remaining"]
        assert after == before
    finally:
        cleanup_tenant(tenant)
