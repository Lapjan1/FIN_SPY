"""
Day-7 PAdES: real pyHanko signatures with an ephemeral self-signed cert,
verified back, tamper detected, TSA fallback honest, unconfigured refused.
No network dependence: TSA pointed at a closed port.
"""
import datetime as dt
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api import signing


def _ephemeral_cert(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "FIN-SPY Test")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
            .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    key_path = tmp_path / "test.key.pem"
    cert_path = tmp_path / "test.cert.pem"
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_path), str(key_path)


def _configure(monkeypatch, tmp_path):
    cert, key = _ephemeral_cert(tmp_path)
    monkeypatch.setenv("FINSPY_SIGN_CERT", cert)
    monkeypatch.setenv("FINSPY_SIGN_KEY", key)
    monkeypatch.setenv("FINSPY_TSA_URL", "http://127.0.0.1:9/tsr")  # closed port
    return cert, key


def _user(client, prefix="sign7"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    return tenant, {"X-User-Id": str(r.json()["id"])}


def test_sign_and_verify_roundtrip(monkeypatch, tmp_path):
    init_db()
    tenant = f"sign7-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
        db.execute(
            "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"txn-{uuid.uuid4().hex[:8]}", tenant, "2026-03-01", "WOOLWORTHS",
             50000, "debit", f"sg-{uuid.uuid4().hex[:8]}", "confirmed"))
        db.commit()
        _configure(monkeypatch, tmp_path)
        assert signing.signing_configured()
        unsigned = tmp_path / "report.pdf"
        info = signing.build_report_pdf(tenant, "2026-01-01", "2026-12-31", unsigned)
        assert info["pages"] == 1
        assert unsigned.read_bytes()[:5] == b"%PDF-"
        signed = tmp_path / "report_signed.pdf"
        out = signing.sign_pdf_file(unsigned, signed)
        assert out["timestamped"] is False  # closed-port TSA honestly skipped
        assert out["warning"] and "timestamp omitted" in out["warning"]
        v = signing.verify_pdf_file(signed)
        assert v["signatures"] == 1
        assert v["valid"] is True
        assert v["intact"] is True
        assert v["trusted"] is False  # self-signed: valid signature, untrusted chain
        assert v["signer"] is not None and "FIN-SPY Test" in v["signer"]
        # unsigned input has no signatures at all
        assert signing.verify_pdf_file(unsigned)["signatures"] == 0
    finally:
        cleanup_tenant(tenant)


def test_tamper_breaks_signature(monkeypatch, tmp_path):
    init_db()
    tenant = f"sign7t-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
        db.commit()
        _configure(monkeypatch, tmp_path)
        unsigned = tmp_path / "r.pdf"
        signing.build_report_pdf(tenant, None, None, unsigned)
        signed = tmp_path / "r_signed.pdf"
        signing.sign_pdf_file(unsigned, signed)
        assert signing.verify_pdf_file(signed)["intact"] is True
        import re
        raw = bytearray(signed.read_bytes())
        m = re.search(rb"/ByteRange\s*\[\s*0\s+(\d+)", bytes(raw))
        assert m, "signed pdf must carry a ByteRange"
        # Flip a covered content byte past the header (inside range 1, so the
        # digest must break while the xref stays parseable).
        flip_at = 50
        assert flip_at < int(m.group(1))
        raw[flip_at] ^= 0xFF
        tampered = tmp_path / "r_tampered.pdf"
        tampered.write_bytes(bytes(raw))
        assert signing.verify_pdf_file(tampered)["intact"] is False
    finally:
        cleanup_tenant(tenant)


def test_unconfigured_refused(monkeypatch):
    monkeypatch.delenv("FINSPY_SIGN_CERT", raising=False)
    monkeypatch.delenv("FINSPY_SIGN_KEY", raising=False)
    assert signing.signing_configured() is False
    try:
        signing.build_and_sign("any-tenant", None, None)
        raise AssertionError("must refuse without cert")
    except ValueError as e:
        assert "signing not configured" in str(e)


def test_signed_pdf_endpoint(monkeypatch, tmp_path):
    client = TestClient(app)
    init_db()
    tenant, h = _user(client)
    try:
        _configure(monkeypatch, tmp_path)
        r = client.get("/v1/reports/signed-pdf?from_date=2026-01-01&to_date=2026-12-31",
                       headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        pdf_path = tmp_path / "signed.pdf"
        pdf_path.write_bytes(r.content)
        assert r.content[:5] == b"%PDF-"
        assert "timestamp omitted" in r.headers.get("x-report-warning", "")
        v = signing.verify_pdf_file(pdf_path)
        assert v["valid"] is True
    finally:
        cleanup_tenant(tenant)


def test_pack_sign_true_embeds_signed_pdf(monkeypatch, tmp_path):
    from apps.api.reports import generate_evidence_pack

    init_db()
    tenant = f"sign7p-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
        db.commit()
        _configure(monkeypatch, tmp_path)
        pack = generate_evidence_pack(tenant, sign=True)
        assert pack["signed"] is True
        names = [f["path"] for f in pack["manifest"]["files"]]
        assert any(n.endswith("_signed.pdf") for n in names)
    finally:
        cleanup_tenant(tenant)
