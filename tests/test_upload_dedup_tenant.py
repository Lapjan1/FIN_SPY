# Upload dedup is per-tenant: same bytes from two tenants -> two queued rows (vault
# stores bytes once globally). Same tenant twice -> duplicate:true, no new row,
# no extra trial consumed.
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db


def _pdf_bytes():
    import fitz

    d = fitz.open()
    p = d.new_page()
    p.insert_text((72, 72), "dedup probe statement")
    return d.tobytes()


def _register(client, email, tenant):
    db = get_db()
    db.execute("DELETE FROM users WHERE email=?", (email,))
    db.commit()
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test1234", "name": "T", "tenant_id": tenant},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload(client, uid, pdf, name="probe.pdf"):
    return client.post(
        "/v1/documents", files={"file": (name, pdf, "application/pdf")}, headers={"X-User-Id": str(uid)}
    )


def _rows_for_tenant(sha, tenant):
    db = get_db()
    cur = db.execute("SELECT id, status FROM source_documents WHERE sha256=? AND tenant_id=?", (sha, tenant))
    return cur.fetchall()


def test_same_bytes_two_tenants_two_rows():
    init_db()
    import hashlib

    pdf = _pdf_bytes()
    sha = hashlib.sha256(pdf).hexdigest()
    db = get_db()
    db.execute("DELETE FROM source_documents WHERE sha256=?", (sha,))
    db.commit()
    client = TestClient(app)
    u1 = _register(client, "dedup_t1@test.com", "dedup-tenant-1")
    u2 = _register(client, "dedup_t2@test.com", "dedup-tenant-2")

    r1 = _upload(client, u1, pdf)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("duplicate") is False
    r2 = _upload(client, u2, pdf)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is False

    rows1 = _rows_for_tenant(sha, "dedup-tenant-1")
    rows2 = _rows_for_tenant(sha, "dedup-tenant-2")
    assert len(rows1) == 1 and len(rows2) == 1
    id1 = rows1[0]["id"] if isinstance(rows1[0], dict) else rows1[0][0]
    id2 = rows2[0]["id"] if isinstance(rows2[0], dict) else rows2[0][0]
    assert id1 != id2
    assert r1.json()["id"] == id1
    assert r2.json()["id"] == id2


def test_same_tenant_twice_is_duplicate_no_extra_trial():
    init_db()
    import hashlib

    pdf = _pdf_bytes()
    sha = hashlib.sha256(pdf).hexdigest()
    db = get_db()
    db.execute("DELETE FROM source_documents WHERE sha256=?", (sha,))
    db.commit()
    client = TestClient(app)
    uid = _register(client, "dedup_same@test.com", "dedup-tenant-same")

    r1 = _upload(client, uid, pdf)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("duplicate") is False
    trial_after_first = r1.json()["trial_pages_remaining"]
    r2 = _upload(client, uid, pdf)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True
    assert r2.json()["trial_pages_remaining"] == trial_after_first
    assert len(_rows_for_tenant(sha, "dedup-tenant-same")) == 1
