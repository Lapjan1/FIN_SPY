"""
Day-6 chat: real answers from tenant DB via tools, tenant-guarded, honest
about model availability (deterministic when no local model is reachable).
"""
import uuid

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant
from apps.worker.spy.chat import run_tool


def _user(client, prefix="chat6"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    return tenant, {"X-User-Id": str(r.json()["id"])}


def _seed(tenant):
    db = get_db()
    rows = [("NETFLIX.COM", 19999, "2026-01-05"),
            ("NETFLIX.COM", 19999, "2026-02-04"),
            ("NETFLIX.COM", 19999, "2026-03-06"),
            ("Monthly account fee", 9900, "2026-03-01"),
            ("WOOLWORTHS", 50000, "2026-03-02"),
            ("SALARY", 500000, "2026-03-01", "credit")]
    for i, row in enumerate(rows):
        desc, amt, date = row[0], row[1], row[2]
        direction = row[3] if len(row) > 3 else "debit"
        db.execute(
            "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"ch6-{i}-{uuid.uuid4().hex[:6]}", tenant, date, desc, amt,
             direction, f"ch6-{uuid.uuid4().hex[:8]}", "confirmed"))
    db.commit()


def _ask(client, h, tenant, question):
    return client.post("/v1/chat", headers=h,
                       json={"tenant_id": tenant,
                             "messages": [{"role": "user", "content": question}]})


def test_chat_totals_from_db():
    client = TestClient(app)
    init_db()
    tenant, h = _user(client)
    try:
        _seed(tenant)
        r = _ask(client, h, tenant, "give me totals")
        assert r.status_code == 200
        body = r.json()
        assert "R5,000.00" in body["answer"]  # inflow
        assert "R1,198.97" in body["answer"]  # outflow 19999*3+9900+50000
        assert body["tool_calls"][0]["tool"] == "totals"
        assert "deterministic" in body["model"]  # no local model in test env
    finally:
        cleanup_tenant(tenant)


def test_chat_subscriptions_and_spend():
    client = TestClient(app)
    init_db()
    tenant, h = _user(client)
    try:
        _seed(tenant)
        r = _ask(client, h, tenant, "what subscriptions do I have?")
        assert r.status_code == 200
        body = r.json()
        assert "netflix com" in body["answer"].lower()
        assert "R199.99" in body["answer"]
        assert len(body["citations"]) >= 1
        r = _ask(client, h, tenant, "spend on woolworths")
        assert r.status_code == 200
        assert "R500.00" in r.json()["answer"]
    finally:
        cleanup_tenant(tenant)


def test_chat_guards_and_empty():
    client = TestClient(app)
    init_db()
    tenant, h = _user(client)
    tenant2, _ = _user(client, "chat6b")
    try:
        _seed(tenant)
        r = _ask(client, h, tenant2, "totals")
        assert r.status_code == 403
        r = client.post("/v1/chat", headers=h,
                        json={"tenant_id": tenant, "messages": []})
        assert r.status_code == 422
        r = _ask(client, h, tenant, "totals")
        assert r.status_code == 200  # own tenant fine
    finally:
        cleanup_tenant(tenant)
        cleanup_tenant(tenant2)


def test_chat_empty_tenant_and_tools():
    client = TestClient(app)
    init_db()
    tenant, h = _user(client)
    try:
        r = _ask(client, h, tenant, "totals")
        assert r.status_code == 200
        assert "No transactions yet" in r.json()["answer"]
    finally:
        cleanup_tenant(tenant)
    assert run_tool("nope", [], {})["error"].startswith("unknown tool")
    assert run_tool("top_vendors", [], {"n": "x"}) == []
