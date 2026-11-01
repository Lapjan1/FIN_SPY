# API landing: the bare service URL explains itself instead of FastAPI 404.
# Local :8000 and Railway finspy-production both showed {"detail":"Not Found"}.
from fastapi.testclient import TestClient

import apps.api.main as main


def test_index_no_auth_explains_service():
    client = TestClient(main.app)
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "FIN_SPY API"
    assert body["docs"] == "/docs"
    assert body["health"] == "/health/ready"
    assert body["web_ui"].startswith("http")
