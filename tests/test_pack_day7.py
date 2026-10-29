"""
Day-7 evidence pack: builder emits Appendix-C manifest + ZIP that the
independent verifier accepts, and rejects a tampered pack.
"""
import hashlib
import importlib.util
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant, append_audit_log
from apps.api.reports import generate_evidence_pack


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_pack", Path("scripts/verify_pack.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seed(tenant, uid=1):
    db = get_db()
    if not db.execute("SELECT id FROM tenants WHERE id=?", (tenant,)).fetchone():
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
    sha = hashlib.sha256(f"packdoc-{tenant}".encode()).hexdigest()
    vault = Path("data/vault")
    vault.mkdir(parents=True, exist_ok=True)
    (vault / f"{sha}.pdf").write_bytes(b"%PDF-1.4 fake vault bytes for pack test")
    db.execute(
        "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, mime,"
        " storage_key, original_filename, uploaded_by, status)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (f"doc-{uuid.uuid4().hex[:8]}", tenant, sha, 38, "application/pdf",
         str(vault / f"{sha}.pdf"), "statement.pdf", uid, "proposed"))
    db.execute(
        "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
        " amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (f"txn-{uuid.uuid4().hex[:8]}", tenant, "2026-03-01", "WOOLWORTHS",
         50000, "debit", f"pk-{uuid.uuid4().hex[:8]}", "confirmed"))
    db.commit()
    append_audit_log(tenant, uid, "pack.seed", "test", tenant, {"seed": True})
    db.commit()
    return sha


def test_pack_builds_manifest_and_zip():
    init_db()
    tenant = f"pack7-{uuid.uuid4().hex[:6]}"
    try:
        sha = _seed(tenant)
        pack = generate_evidence_pack(tenant)
        assert Path(pack["file_key"]).exists()
        assert pack["sha256"] == hashlib.sha256(
            Path(pack["file_key"]).read_bytes()).hexdigest()
        m = pack["manifest"]
        assert m["manifest_version"] == 1
        assert m["tenant"] == tenant
        assert m["audit_chain"]["head_hash"], "audit head must pin the chain"
        assert m["audit_chain"]["anchor_tsr"] is None  # TSA not faked
        roles = {f["role"] for f in m["files"]}
        assert {"original", "report", "audit", "extraction_raw"} <= roles
        orig = [f for f in m["files"] if f["role"] == "original"][0]
        assert orig["path"] == f"originals/{sha}.pdf"
        assert len(orig["sha256"]) == 64
        with zipfile.ZipFile(pack["file_key"]) as z:
            names = set(z.namelist())
        assert "manifest.json" in names and "manifest.sha256" in names
        assert f"originals/{sha}.pdf" in names
    finally:
        cleanup_tenant(tenant)


def test_verifier_accepts_pack_and_rejects_tamper(monkeypatch, tmp_path):
    init_db()
    tenant = f"pack7v-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        pack = generate_evidence_pack(tenant)
        verifier = _load_verifier()
        monkeypatch.setattr("sys.argv", ["verify_pack.py", pack["file_key"]])
        with pytest.raises(SystemExit) as ok:
            verifier.main()
        assert ok.value.code == 0
        # Tamper: flip one byte in the auditor copy inside a re-zipped pack
        tamper_src = tmp_path / "tamper"
        with zipfile.ZipFile(pack["file_key"]) as z:
            z.extractall(tamper_src)
        csvs = sorted((tamper_src).rglob("auditor_export_*.csv"))
        assert csvs, "pack must contain the auditor csv"
        data = csvs[0].read_bytes() + b"X"
        csvs[0].write_bytes(data)
        bad_zip = tmp_path / "tampered.zip"
        with zipfile.ZipFile(bad_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(tamper_src.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(tamper_src).as_posix())
        monkeypatch.setattr("sys.argv", ["verify_pack.py", str(bad_zip)])
        with pytest.raises(SystemExit) as bad:
            verifier.main()
        assert bad.value.code == 1
    finally:
        cleanup_tenant(tenant)


def test_pack_endpoint():
    client = TestClient(app)
    init_db()
    tenant = f"pack7e-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        _seed(tenant, r.json()["id"])
        r = client.get("/v1/reports/evidence-pack", headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/zip")
        import io
        import zipfile
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        assert "manifest.json" in names
        assert "manifest.sha256" in names
        assert len(names) >= 4
    finally:
        cleanup_tenant(tenant)
