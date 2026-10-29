"""
Duplicate re-upload after vault bytes are lost (ephemeral disk wiped by a
redeploy) must restore the bytes AND requeue the document - otherwise the
user is stuck on "already in your vault" with nothing to extract. Live
case: sha c681db6a... 127KB, duplicate:true, zero extraction.
"""

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api import main as main_mod
from apps.api.db import init_db, get_db


def _pdf_bytes(tag):
    import fitz

    d = fitz.open()
    p = d.new_page()
    p.insert_text((72, 72), f"restore probe {tag}")
    return d.tobytes()


def test_duplicate_with_lost_bytes_restores_and_requeues(tmp_path):
    init_db()
    client = TestClient(app)
    tag = "restore1"
    pdf = _pdf_bytes(tag)
    sha = hashlib.sha256(pdf).hexdigest()
    db = get_db()
    db.execute("DELETE FROM users WHERE email='restore@test.com'")
    db.execute("DELETE FROM source_documents WHERE sha256=?", (sha,))
    db.commit()
    tenant = "restore-tenant"

    vault = Path(tmp_path) / "vault"
    vault.mkdir()
    old = main_mod.VAULT_PATH
    main_mod.VAULT_PATH = vault
    try:
        client.post("/v1/auth/register",
                    json={"email": "restore@test.com", "password": "test1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login",
                        json={"email": "restore@test.com",
                              "password": "test1234"})
        uid = r.json()["id"]

        files = {"file": ("probe.pdf", pdf, "application/pdf")}
        r1 = client.post("/v1/documents", files=files,
                         headers={"X-User-Id": str(uid)})
        assert r1.status_code == 200, r1.text
        assert r1.json()["duplicate"] is False
        trial_first = r1.json()["trial_pages_remaining"]
        stored = vault / f"{sha}.pdf"
        assert stored.exists()

        # Simulate redeploy wipe: bytes gone, DB row (exception) survives.
        stored.unlink()
        db.execute("UPDATE source_documents SET status='exception'"
                   " WHERE tenant_id=? AND sha256=?", (tenant, sha))
        db.commit()

        files = {"file": ("probe.pdf", pdf, "application/pdf")}
        r2 = client.post("/v1/documents", files=files,
                         headers={"X-User-Id": str(uid)})
        assert r2.status_code == 200, r2.text
        out = r2.json()
        assert out["duplicate"] is True
        assert out["trial_pages_remaining"] == trial_first  # still free
        assert stored.exists(), "bytes must be restored"
        assert out["status"] == "queued", out
        assert out.get("requeued") is True
        cur = db.execute("SELECT status FROM source_documents"
                         " WHERE tenant_id=? AND sha256=?", (tenant, sha))
        row = cur.fetchone()
        assert (row["status"] if isinstance(row, dict) else row[0]) == "queued"
    finally:
        main_mod.VAULT_PATH = old


def test_duplicate_with_bytes_present_stays_put(tmp_path):
    # Normal duplicate (bytes intact, already proposed): no requeue churn.
    init_db()
    client = TestClient(app)
    pdf = _pdf_bytes("restore2")
    sha = hashlib.sha256(pdf).hexdigest()
    db = get_db()
    db.execute("DELETE FROM users WHERE email='restore2@test.com'")
    db.execute("DELETE FROM source_documents WHERE sha256=?", (sha,))
    db.commit()
    tenant = "restore-tenant-2"

    vault = Path(tmp_path) / "vault2"
    vault.mkdir()
    old = main_mod.VAULT_PATH
    main_mod.VAULT_PATH = vault
    try:
        client.post("/v1/auth/register",
                    json={"email": "restore2@test.com", "password": "test1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login",
                        json={"email": "restore2@test.com",
                              "password": "test1234"})
        uid = r.json()["id"]
        files = {"file": ("probe.pdf", pdf, "application/pdf")}
        client.post("/v1/documents", files=files,
                    headers={"X-User-Id": str(uid)})
        db.execute("UPDATE source_documents SET status='proposed'"
                   " WHERE tenant_id=? AND sha256=?", (tenant, sha))
        db.commit()
        files = {"file": ("probe.pdf", pdf, "application/pdf")}
        r2 = client.post("/v1/documents", files=files,
                         headers={"X-User-Id": str(uid)})
        assert r2.json()["duplicate"] is True
        assert r2.json()["status"] == "proposed"
        assert r2.json().get("requeued", False) is False
    finally:
        main_mod.VAULT_PATH = old
