"""
P0-A: report endpoints stream file bytes (downloads), not server paths.
Today each GET returns JSON with a server-local file_key the browser
cannot use. Red: content-type is application/json for all five.
"""

import io
import uuid
import zipfile

from fastapi.testclient import TestClient

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import app


def _register(client, prefix="dl"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234",
              "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    return tenant, {"X-User-Id": str(r.json()["id"])}


def _seed_txn(tenant, desc="WOOLWORTHS"):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
        " amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (txn_id, tenant, "2026-10-10", desc, -45000, "debit",
         f"fp-{uuid.uuid4().hex[:8]}", "confirmed"),
    )
    db.commit()
    return txn_id


def _is_download(resp, kind):
    ctype = resp.headers.get("content-type", "")
    disp = resp.headers.get("content-disposition", "")
    assert resp.status_code == 200, resp.text[:200]
    assert "attachment" in disp, f"no attachment: {disp}"
    assert len(resp.content) > 100, "empty body"
    if kind == "xlsx":
        assert ctype.startswith(
            "application/vnd.openxmlformats"), ctype
        assert resp.content[:2] == b"PK"
    elif kind == "zip":
        assert ctype.startswith("application/zip"), ctype
        assert resp.content[:2] == b"PK"
    elif kind == "csv":
        assert ctype.startswith("text/csv"), ctype
    elif kind == "pdf":
        assert ctype.startswith("application/pdf"), ctype
        assert resp.content[:4] == b"%PDF"


def test_excel_downloads_bytes():
    client, tenant, h = TestClient(app), None, None
    init_db()
    tenant, h = _register(client)
    try:
        _seed_txn(tenant)
        r = client.get("/v1/reports/excel", headers=h)
        _is_download(r, "xlsx")
    finally:
        cleanup_tenant(tenant)


def test_powerbi_downloads_zip():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        _seed_txn(tenant)
        r = client.get("/v1/reports/powerbi", headers=h)
        _is_download(r, "zip")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        assert any(n.endswith(".xlsx") for n in names)
        assert any(n.endswith(".csv") for n in names)
    finally:
        cleanup_tenant(tenant)


def test_auditor_csv_downloads_and_isolates():
    client = TestClient(app)
    init_db()
    tenant_a, ha = _register(client, prefix="dla")
    tenant_b, hb = _register(client, prefix="dlb")
    try:
        _seed_txn(tenant_a, desc="SECRET-ALPHA-STORE")
        _seed_txn(tenant_b, desc="BETA SHOP")
        r = client.get("/v1/reports/auditor-csv", headers=hb)
        _is_download(r, "csv")
        assert "BETA SHOP" in r.text
        assert "SECRET-ALPHA-STORE" not in r.text
    finally:
        cleanup_tenant(tenant_a)
        cleanup_tenant(tenant_b)


def test_evidence_pack_downloads_zip():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        _seed_txn(tenant)
        r = client.get("/v1/reports/evidence-pack", headers=h)
        _is_download(r, "zip")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        assert "manifest.json" in names
    finally:
        cleanup_tenant(tenant)


def test_signed_pdf_gate_and_download():
    client = TestClient(app)
    init_db()
    tenant, h = _register(client)
    try:
        # Unconfigured here -> honest 422 (prod needs signing keys).
        r = client.get("/v1/reports/signed-pdf", headers=h)
        assert r.status_code in (200, 422), r.text[:200]
        if r.status_code == 200:
            _is_download(r, "pdf")
    finally:
        cleanup_tenant(tenant)


def test_downloads_need_auth():
    client = TestClient(app)
    for url in ("/v1/reports/excel", "/v1/reports/powerbi",
                "/v1/reports/auditor-csv", "/v1/reports/evidence-pack",
                "/v1/reports/signed-pdf"):
        r = client.get(url)
        assert r.status_code == 401, (url, r.status_code)
