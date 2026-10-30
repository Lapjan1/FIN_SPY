"""
Image uploads (jpg/png) are accepted by intake but the extractor has no OCR
(ValueError at extract time -> doc exception, quota spent). Fail fast at
upload with a clear 422 instead of burning trial quota on a doomed file.
"""

import uuid

from fastapi.testclient import TestClient

from apps.api.db import init_db, cleanup_tenant
from apps.api.main import app


def test_image_upload_rejected_with_clear_message():
    client = TestClient(app)
    init_db()
    tenant = f"imgrej-{uuid.uuid4().hex[:6]}"
    email = f"imgrej_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        r = client.post("/v1/documents", headers=h, files={
            "file": ("receipt.png", png, "image/png")})
        assert r.status_code == 422, r.text
        assert "OCR" in r.text
    finally:
        cleanup_tenant(tenant)
