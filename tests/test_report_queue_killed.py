"""
P0-J (D8): the report-job queue is dead - nothing ever consumed a "queued"
report. Every known kind now generates synchronously; unknown kinds 422
instead of vanishing into a fake queue.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, cleanup_tenant
from apps.api.main import app


def _authed(prefix="repq"):
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


def test_report_kinds_generate_synchronously():
    client, tenant, h = _authed()
    try:
        for kind in ("excel", "auditor-csv", "evidence-pack", "powerbi"):
            r = client.post(f"/v1/reports?kind={kind}", headers=h)
            assert r.status_code == 200, (kind, r.text)
            out = r.json()
            assert out["status"] == "ready", (kind, out)
            assert out["file_key"], (kind, out)
            assert out["sha256"], (kind, out)
    finally:
        cleanup_tenant(tenant)


def test_report_unknown_kind_422_not_queued():
    client, tenant, h = _authed()
    try:
        r = client.post("/v1/reports?kind=bogus", headers=h)
        assert r.status_code == 422, r.text
        assert "queued" not in r.text
    finally:
        cleanup_tenant(tenant)
