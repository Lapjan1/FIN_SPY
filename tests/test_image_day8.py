"""
Day-8 Meta depth: Wonder/image + SAM clients refuse when unconfigured,
pass through real provider payloads when configured (mocked transports).
"""
import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, cleanup_tenant
from apps.worker.llm import image as img


def test_wonder_model_id_from_config():
    assert img._wonder_model_id() == "muse-wonder-1.0"


def test_generate_passthrough(monkeypatch):
    import apps.worker.llm.image as mod

    class FakeItem:
        b64_json = "aGVsbG8="
        url = None

    class FakeResp:
        data = [FakeItem()]

    class FakeImages:
        def generate(self, **kw):
            assert kw["model"] == "muse-wonder-1.0"
            assert kw["prompt"] == "a robot"
            return FakeResp()

    class FakeOpenAI:
        def __init__(self, base_url=None, api_key=None):
            self.images = FakeImages()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("IMAGE_BASE_URL", "http://127.0.0.1:3001/v1")
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    out = mod.generate_image("a robot")
    assert out["b64_json"] == "aGVsbG8="
    assert out["mock"] is False
    with pytest.raises(ValueError, match="prompt"):
        mod.generate_image("  ")


def test_generate_refused_when_unconfigured(monkeypatch):
    monkeypatch.delenv("IMAGE_BASE_URL", raising=False)
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    assert img.image_configured() is False
    with pytest.raises(ValueError, match="not configured"):
        img.generate_image("x")
    client = TestClient(app)
    init_db()
    tenant = f"img8-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    try:
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
        h = {"X-User-Id": str(r.json()["id"])}
        r = client.post("/v1/images/generate", headers=h, json={"prompt": "x"})
        assert r.status_code == 422
    finally:
        cleanup_tenant(tenant)


def test_segment_passthrough_and_guards(monkeypatch):
    import apps.worker.llm.image as mod

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"masks": [{"bbox": [1, 2, 3, 4], "area": 10}], "model": "sam-test"}

    monkeypatch.setenv("SAM_ENDPOINT_URL", "http://127.0.0.1:9999/segment")
    monkeypatch.setattr(mod.requests, "post",
                        lambda url, json=None, timeout=None: Resp())
    out = mod.segment_image(base64.b64encode(b"img").decode(),
                            points=[[5, 5]])
    assert out["masks"][0]["bbox"] == [1, 2, 3, 4]
    with pytest.raises(ValueError, match="base64"):
        mod.segment_image("!!!not-b64!!!")
    monkeypatch.delenv("SAM_ENDPOINT_URL")
    assert mod.sam_configured() is False
    with pytest.raises(ValueError, match="SAM not configured"):
        mod.segment_image(base64.b64encode(b"img").decode())


def test_segment_endpoint_422_unconfigured(monkeypatch):
    monkeypatch.delenv("SAM_ENDPOINT_URL", raising=False)
    client = TestClient(app)
    init_db()
    tenant = f"img8s-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    try:
        client.post("/v1/auth/register",
                    json={"email": email, "password": "pass1234",
                          "name": "T", "tenant_id": tenant})
        r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
        h = {"X-User-Id": str(r.json()["id"])}
        r = client.post("/v1/images/segment", headers=h,
                        json={"image_b64": base64.b64encode(b"img").decode()})
        assert r.status_code == 422
    finally:
        cleanup_tenant(tenant)
