"""
9999 Suspense: unclassified transactions park in 9999 so statements stay complete,
then re-decode transfers the leg to the real account. Suspense must stay small.

Per user research: post unknowns under proper debit/credit to statements,
otherwise income/expense would be incomplete. Auto + AI classify ~95%; human
re-decodes the rest; 9999 watchdog flags balance/count/aging/completeness.
"""

import uuid

import pytest

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.ledger import (
    post_transaction,
    transfer_posting,
    trial_balance,
    suspense_status,
    UnknownAccount,
)
from apps.api.classify import suggest_classification, decide
from apps.worker.parsers.registry import seed_coa, get_coa_templates


def _tenant(prefix="susp"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    init_db()
    db = get_db()
    db.execute(
        "INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}")
    )
    db.commit()
    return tenant


def _bank_account(tenant, acct_no="123456", template="personal"):
    db = get_db()
    bank_id = f"bank-{tenant}-{acct_no}"
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, template)"
        " VALUES (?,?,?,?,?,?,?)",
        (bank_id, tenant, "1000", "Bank - Test", "asset", acct_no, template),
    )
    db.commit()
    return bank_id


def _txn(
    tenant,
    bank_id,
    acct_no="123456",
    amount=-45000,
    direction="debit",
    desc="XQZ UNKNOWN 12345",
    date="2026-10-10",
    status="proposed",
):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number, txn_date,"
        " description_raw, amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            txn_id,
            tenant,
            bank_id,
            acct_no,
            date,
            desc,
            amount,
            direction,
            f"fp-{uuid.uuid4().hex[:8]}",
            status,
        ),
    )
    db.commit()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    return dict(row) if not isinstance(row, dict) else row


def test_9999_in_all_templates_and_reseed_migration():
    templates = get_coa_templates()
    for name in ("personal", "sme_cc", "mixed_sole_prop"):
        codes = [a["code"] for a in templates[name]["accounts"]]
        assert "9999" in codes, f"Template {name} must define 9999 suspense"
    tenant = _tenant()
    try:
        # Simulate tenant seeded before 9999 existed: seed, drop 9999, reseed
        seed_coa(tenant, template="personal")
        db = get_db()
        db.execute("DELETE FROM accounts WHERE tenant_id=? AND code='9999'", (tenant,))
        db.commit()
        # Re-seed (as set_active_template does) restores only the missing code
        created = seed_coa(tenant, template="personal")
        assert created == 1
        cur = db.execute(
            "SELECT name, type FROM accounts WHERE tenant_id=? AND code='9999'",
            (tenant,),
        )
        row = cur.fetchone()
        d = dict(row) if not isinstance(row, dict) else row
        assert "Suspense" in d["name"]
        assert d["type"] == "expense"
    finally:
        cleanup_tenant(tenant)


def test_unknown_suggests_9999():
    tenant = _tenant()
    try:
        sug = suggest_classification(
            "XQZ UNKNOWN 12345", "123", tenant, amount_minor=-500, direction="debit"
        )
        assert sug["nature"] == "unknown"
        assert sug["category_id"] == "9999"
        assert sug["confidence"] == 0.0
    finally:
        cleanup_tenant(tenant)


def test_accept_unknown_posts_to_9999_via_api():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"suspapi-{uuid.uuid4().hex[:6]}"
    email = f"susp_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234", "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        r = client.post(
            f"/v1/review-queue/{txn['id']}/accept",
            headers=h,
            json={"reason": "park unknown"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "confirmed"
        assert body["classification"]["nature"] == "unknown"
        assert body["classification"]["category_id"] == "9999"
        codes = [ln["code"] for ln in body["journal_entry"]["lines"]]
        assert "9999" in codes
        assert body["journal_entry"]["debits"] == body["journal_entry"]["credits"]
        # Trial balance includes 9999 and still balances
        r = client.get("/v1/journal/trial-balance", headers=h)
        assert r.json()["balanced"] is True
        line9999 = [ln for ln in r.json()["lines"] if ln["code"] == "9999"]
        assert line9999 and line9999[0]["debits"] == 45000
    finally:
        cleanup_tenant(tenant)


def test_inflow_unknown_credits_9999():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(
            tenant, bank_id, amount=77700, direction="credit", desc="MYSTERY INFLOW"
        )
        entry = post_transaction(
            txn, {"category_id": "9999", "nature": "unknown", "business_pct": 0}
        )
        assert entry["debits"] == entry["credits"] == 77700
        by_code = {ln["code"]: ln for ln in entry["lines"]}
        assert by_code["9999"]["credit_minor"] == 77700
        assert by_code["1000"]["debit_minor"] == 77700
    finally:
        cleanup_tenant(tenant)


def test_redecide_transfers_out_of_9999():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        c1 = decide(txn["id"], "unknown", 0, "9999", "parked", 1, "first pass", tenant)
        assert "transfer_entry_id" not in c1  # first decision posts nothing yet
        post_transaction(
            txn,
            {
                "id": c1["id"],
                "category_id": "9999",
                "nature": "unknown",
                "business_pct": 0,
            },
        )
        status = suspense_status(tenant)
        assert status["balance_minor"] == 45000
        assert status["txn_count"] == 1
        # Human remembers: groceries. Transfer moves the leg 9999 -> 6020.
        c2 = decide(
            txn["id"], "private", 0, "6020", "groceries", 1, "remembered", tenant
        )
        assert c2["supersedes_id"] == c1["id"]
        assert "transfer_entry_id" in c2
        status = suspense_status(tenant)
        assert status["balance_minor"] == 0
        assert status["txn_count"] == 0
        assert status["status"] == "ok"
        tb = trial_balance(tenant)
        assert tb["balanced"] is True and tb["zero"] is True
        by_code = {ln["code"]: ln for ln in tb["lines"]}
        assert by_code["6020"]["debits"] == 45000
        assert by_code["9999"]["debits"] == 45000  # gross legs remain auditable
        assert by_code["9999"]["credits"] == 45000
    finally:
        cleanup_tenant(tenant)


def test_redecide_same_category_no_transfer():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        decide(txn["id"], "private", 0, "6020", "groceries", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})
        c2 = decide(
            txn["id"], "private", 0, "6020", "confirmed", 1, "second look", tenant
        )
        assert "transfer_entry_id" not in c2
        db = get_db()
        cur = db.execute(
            "SELECT COUNT(*) c FROM journal_entries WHERE tenant_id=?", (tenant,)
        )
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == 1
    finally:
        cleanup_tenant(tenant)


def test_redecide_unposted_creates_no_journal():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        decide(txn["id"], "unknown", 0, "9999", "parked", 1, "first", tenant)
        c2 = decide(
            txn["id"],
            "private",
            0,
            "6020",
            "groceries",
            1,
            "decoded before posting",
            tenant,
        )
        assert "transfer_entry_id" not in c2
        assert transfer_posting(tenant, txn["id"], "9999", "6020") is None
        db = get_db()
        cur = db.execute(
            "SELECT COUNT(*) c FROM journal_entries WHERE tenant_id=?", (tenant,)
        )
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == 0
    finally:
        cleanup_tenant(tenant)


def test_transfer_validates_and_isolates():
    a = _tenant(prefix="suspa")
    b = _tenant(prefix="suspb")
    try:
        seed_coa(a, template="personal")
        seed_coa(b, template="personal")
        bank_a = _bank_account(a, acct_no="111")
        txn = _txn(a, bank_a, acct_no="111")
        with pytest.raises(PermissionError, match="Cross-tenant"):
            transfer_posting(b, txn["id"], "9999", "6020")
        with pytest.raises(ValueError, match="must differ"):
            transfer_posting(a, txn["id"], "6020", "6020")
        with pytest.raises(ValueError, match="does not exist"):
            transfer_posting(a, "nope", "9999", "6020")
        # From-code must exist once there is something to move
        decide(txn["id"], "unknown", 0, "9999", "parked", 1, "first", a)
        post_transaction(txn, {"category_id": "9999"})
        with pytest.raises(UnknownAccount, match="Invalid parameters"):
            transfer_posting(a, txn["id"], "NOPE", "6020")
    finally:
        cleanup_tenant(a)
        cleanup_tenant(b)


def test_suspense_watchdog_endpoint():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"suspw-{uuid.uuid4().hex[:6]}"
    email = f"suspw_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234", "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        seed_coa(tenant, template="personal")
        r = client.get("/v1/journal/suspense", headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["suspense_code"] == "9999"
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        decide(txn["id"], "unknown", 0, "9999", "parked", 1, "first", tenant)
        post_transaction(txn, {"category_id": "9999"})
        r = client.get("/v1/journal/suspense", headers=h)
        body = r.json()
        assert body["status"] == "review"  # 100% of postings > 5% limit
        assert body["balance_minor"] == 45000
        assert body["txn_count"] == 1
        assert any("5%" in reason for reason in body["reasons"])
        # Completeness: confirmed-but-unposted txn is flagged
        db = get_db()
        ghost = _txn(tenant, bank_id, desc="GHOST", date="2026-10-11")
        db.execute(
            "UPDATE transactions SET status='confirmed' WHERE id=?", (ghost["id"],)
        )
        db.commit()
        r = client.get("/v1/journal/suspense", headers=h)
        body = r.json()
        assert body["unposted_confirmed_count"] == 1
        assert ghost["id"] in body["unposted_confirmed_ids"]
        assert any("incomplete" in reason for reason in body["reasons"])
    finally:
        cleanup_tenant(tenant)
