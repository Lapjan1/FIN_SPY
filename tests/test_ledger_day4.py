"""
Day4 Books: ledger-core double-entry, classify rules-first, review accept/edit, isolation.
Per docs/TIMELINE.md Day4 + docs/MODULES.md ledger-core/classify + LEARNINGS 02/03.

Money int minor only, never float. Tenant isolation enforced. Append-only revisions.
"""

import uuid

import pytest

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.ledger import post_transaction, trial_balance, UnknownAccount
from apps.api.classify import suggest_classification, decide
from apps.worker.parsers.registry import seed_coa, set_active_template


def _tenant(prefix="day4"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    init_db()
    db = get_db()
    db.execute(
        "INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}")
    )
    db.commit()
    return tenant


def _bank_account(tenant, acct_no="123456", code="1000"):
    db = get_db()
    bank_id = f"bank-{tenant}-{acct_no}"
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, template)"
        " VALUES (?,?,?,?,?,?,?)",
        (bank_id, tenant, code, "Bank - Test", "asset", acct_no, "personal"),
    )
    db.commit()
    return bank_id


def _txn(
    tenant,
    bank_id,
    acct_no="123456",
    amount=-45000,
    direction="debit",
    desc="WOOLWORTHS CT",
    date="2026-10-10",
    status="proposed",
):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    fp = f"fp-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number, txn_date,"
        " description_raw, amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, bank_id, acct_no, date, desc, amount, direction, fp, status),
    )
    db.commit()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    return dict(row) if not isinstance(row, dict) else row


def test_post_balanced_outflow():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, amount=-45000, direction="debit")
        entry = post_transaction(
            txn, {"category_id": "6020", "nature": "private", "business_pct": 0}
        )
        assert entry["debits"] == entry["credits"] == 45000
        assert len(entry["lines"]) == 2
        # Dr expense / Cr bank
        assert entry["lines"][0]["debit_minor"] == 45000
        assert entry["lines"][1]["credit_minor"] == 45000
    finally:
        cleanup_tenant(tenant)


def test_post_balanced_inflow():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(
            tenant, bank_id, amount=100000, direction="credit", desc="SALARY ACME"
        )
        entry = post_transaction(
            txn, {"category_id": "4000", "nature": "business", "business_pct": 100}
        )
        assert entry["debits"] == entry["credits"] == 100000
        # Dr bank / Cr income
        assert entry["lines"][0]["debit_minor"] == 100000
        assert entry["lines"][1]["credit_minor"] == 100000
    finally:
        cleanup_tenant(tenant)


def test_post_mixed_split_mixed_template():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="mixed_sole_prop")
        set_active_template(tenant, "mixed_sole_prop")
        db = get_db()
        bank_id = f"bank-{tenant}-999"
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, template)"
            " VALUES (?,?,?,?,?,?,?)",
            (bank_id, tenant, "1000", "Bank - Test", "asset", "999", "mixed_sole_prop"),
        )
        db.commit()
        txn = _txn(
            tenant,
            bank_id,
            acct_no="999",
            amount=-10000,
            direction="debit",
            desc="SASOL FUEL",
        )
        entry = post_transaction(
            txn, {"category_id": "6200", "nature": "mixed", "business_pct": 60}
        )
        assert entry["debits"] == entry["credits"] == 10000
        assert len(entry["lines"]) == 3
        assert entry["lines"][0]["debit_minor"] == 6000  # business
        assert entry["lines"][1]["debit_minor"] == 4000  # private suspense
    finally:
        cleanup_tenant(tenant)


def test_post_mixed_personal_has_no_drawings():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, amount=-10000, direction="debit")
        with pytest.raises(UnknownAccount, match="Invalid parameters"):
            post_transaction(
                txn, {"category_id": "6020", "nature": "mixed", "business_pct": 60}
            )
    finally:
        cleanup_tenant(tenant)


def test_post_unknown_account():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        with pytest.raises(UnknownAccount, match="Invalid parameters"):
            post_transaction(txn, {"category_id": "NOPE-9999"})
        with pytest.raises(UnknownAccount, match="Invalid parameters"):
            post_transaction(txn, {"account_id": "acc-does-not-exist"})
    finally:
        cleanup_tenant(tenant)


def test_post_rejects_float_amount():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        txn["amount_minor"] = 450.50  # float forbidden per AGENTS.md
        with pytest.raises(ValueError, match="Invalid parameters.*int cents"):
            post_transaction(txn, {"category_id": "6020"})
    finally:
        cleanup_tenant(tenant)


def test_post_rejects_zero_and_bad_pct():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        txn["amount_minor"] = 0
        with pytest.raises(ValueError, match="Invalid parameters.*non-zero"):
            post_transaction(txn, {"category_id": "6020"})
        txn["amount_minor"] = -1000
        with pytest.raises(ValueError, match="business_pct"):
            post_transaction(txn, {"category_id": "6020", "business_pct": 150})
        with pytest.raises(ValueError, match="nature"):
            post_transaction(txn, {"category_id": "6020", "nature": "bogus"})
    finally:
        cleanup_tenant(tenant)


def test_trial_balance_zero():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        t1 = _txn(tenant, bank_id, amount=-45000, direction="debit", desc="WOOLWORTHS")
        t2 = _txn(
            tenant,
            bank_id,
            amount=100000,
            direction="credit",
            desc="SALARY",
            date="2026-10-11",
        )
        post_transaction(t1, {"category_id": "6020"})
        post_transaction(t2, {"category_id": "4000"})
        tb = trial_balance(tenant)
        assert tb["balanced"] is True
        assert tb["zero"] is True
        assert tb["total_debits"] == tb["total_credits"] == 145000
        # Isolation: other tenant sees zero
        other = _tenant(prefix="day4other")
        try:
            seed_coa(other, template="personal")
            tb2 = trial_balance(other)
            assert tb2["total_debits"] == 0 and tb2["total_credits"] == 0
        finally:
            cleanup_tenant(other)
    finally:
        cleanup_tenant(tenant)


def test_journal_balance_trigger_blocks_unbalanced_post():
    """DB trigger is backstop: drafting unbalanced lines is allowed, posting is not,
    and posted entries reject unbalancing changes."""
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        db = get_db()
        bank_id = _bank_account(tenant)
        cur = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND code='6020' LIMIT 1",
            (tenant,),
        )
        exp_id = cur.fetchone()
        exp_id = exp_id["id"] if isinstance(exp_id, dict) else exp_id[0]
        entry_id = f"je-{uuid.uuid4().hex[:8]}"
        db.execute(
            "INSERT INTO journal_entries (id, tenant_id, entry_date, memo) VALUES (?,?,?,?)",
            (entry_id, tenant, "2026-10-10", "trigger test"),
        )
        # Draft: unbalanced intermediate state allowed while unposted
        db.execute(
            "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
            " VALUES (?,?,?,?,?)",
            (f"jl-{uuid.uuid4().hex[:6]}", entry_id, exp_id, 100, 0),
        )
        db.execute(
            "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
            " VALUES (?,?,?,?,?)",
            (f"jl-{uuid.uuid4().hex[:6]}", entry_id, bank_id, 0, 999),
        )
        db.commit()
        # Post must abort on unbalanced lines
        with pytest.raises(Exception, match="not balanced"):
            db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
        db.conn.rollback()
        # Fix the draft, post succeeds
        db.execute(
            "UPDATE journal_lines SET credit_minor=100 WHERE entry_id=? AND account_id=?",
            (entry_id, bank_id),
        )
        db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
        db.commit()
        # Posted entry rejects unbalancing line insert
        with pytest.raises(Exception, match="not balanced"):
            db.execute(
                "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
                " VALUES (?,?,?,?,?)",
                (f"jl-{uuid.uuid4().hex[:6]}", entry_id, exp_id, 5000, 0),
            )
        db.conn.rollback()
        # Posted entry rejects line delete (unpost first)
        with pytest.raises(Exception, match="posted entry"):
            db.execute("DELETE FROM journal_lines WHERE entry_id=?", (entry_id,))
        db.conn.rollback()
    finally:
        cleanup_tenant(tenant)


def test_suggest_rules_first():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        db = get_db()
        cur = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND code='6020' LIMIT 1",
            (tenant,),
        )
        acc_id = cur.fetchone()
        acc_id = acc_id["id"] if isinstance(acc_id, dict) else acc_id[0]
        from apps.api.vendor import create_vendor_rule

        create_vendor_rule(
            tenant,
            "WOOLWORTHS",
            "123456",
            acc_id,
            "6020",
            "private",
            0,
            auto_book=False,
            decided_by=None,
        )
        sug = suggest_classification("WOOLWORTHS CT", "123456", tenant)
        assert sug["source"] == "rule"
        assert sug["nature"] == "private"
        assert sug["category_id"] == "6020"
    finally:
        cleanup_tenant(tenant)


def test_suggest_ai_private_business_unknown():
    tenant = _tenant()
    try:
        sug = suggest_classification("WOOLWORTHS CLOTHING", "123", tenant)
        assert sug["nature"] == "private"
        assert sug["source"] == "ai"
        assert "Companies Act" in sug["rationale"]
        sug2 = suggest_classification("SUPPLIER STEEL CO", "123", tenant)
        assert sug2["nature"] == "business"
        sug3 = suggest_classification(
            "XQZ UNKNOWN 12345", "123", tenant, amount_minor=-500, direction="debit"
        )
        assert sug3["nature"] == "unknown"
        assert sug3["confidence"] == 0.0
        # Mixed only exceptional sole prop + shared keyword
        sug4 = suggest_classification(
            "SASOL FUEL", "123", tenant, entity_kind="mixed_sole_prop"
        )
        assert sug4["nature"] == "mixed"
        assert sug4["business_pct"] == 60
        sug5 = suggest_classification(
            "SASOL FUEL", "123", tenant, entity_kind="personal"
        )
        assert sug5["nature"] != "mixed"
    finally:
        cleanup_tenant(tenant)


def test_decide_revision_chain_and_memory():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        c1 = decide(
            txn["id"], "private", 0, "6020", "groceries", 1, "first review", tenant
        )
        assert c1["supersedes_id"] is None
        c2 = decide(
            txn["id"],
            "business",
            100,
            "6000",
            "correction: catering",
            1,
            "auditor asked",
            tenant,
        )
        assert c2["supersedes_id"] == c1["id"]
        db = get_db()
        cur = db.execute(
            "SELECT COUNT(*) c FROM classifications WHERE transaction_id=?",
            (txn["id"],),
        )
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == 2
        cur = db.execute(
            "SELECT COUNT(*) c FROM transaction_revisions WHERE transaction_id=?",
            (txn["id"],),
        )
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == 2
        # Merchant memory learned latest decision
        sug = suggest_classification(
            txn["description_raw"], txn["account_number"], tenant
        )
        assert sug["source"] == "rule"
        assert sug["nature"] == "business"
    finally:
        cleanup_tenant(tenant)


def test_decide_requires_reason_and_valid_category():
    tenant = _tenant()
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        with pytest.raises(ValueError, match="reason is required"):
            decide(txn["id"], "private", 0, "6020", "x", 1, "  ", tenant)
        with pytest.raises(ValueError, match="does not exist"):
            decide(txn["id"], "private", 0, "NOPE", "x", 1, "reason", tenant)
        with pytest.raises(ValueError, match="nature"):
            decide(txn["id"], "bogus", 0, "6020", "x", 1, "reason", tenant)
    finally:
        cleanup_tenant(tenant)


def test_cross_tenant_denied():
    a = _tenant(prefix="day4a")
    b = _tenant(prefix="day4b")
    try:
        seed_coa(a, template="personal")
        seed_coa(b, template="personal")
        bank_a = _bank_account(a, acct_no="111")
        txn_a = _txn(a, bank_a, acct_no="111")
        with pytest.raises(PermissionError, match="Cross-tenant"):
            decide(txn_a["id"], "private", 0, "6020", "x", 1, "reason", b)
        # Posting with other tenant's target account id must fail isolation
        db = get_db()
        cur = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND code='6020' LIMIT 1", (b,)
        )
        row = cur.fetchone()
        other_acc = row["id"] if isinstance(row, dict) else row[0]
        with pytest.raises(UnknownAccount, match="Invalid parameters"):
            post_transaction(txn_a, {"account_id": other_acc})
    finally:
        cleanup_tenant(a)
        cleanup_tenant(b)


def test_review_accept_and_edit_via_api():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"day4api-{uuid.uuid4().hex[:6]}"
    email = f"day4_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234", "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    uid = r.json()["id"]
    h = {"X-User-Id": str(uid)}
    try:
        seed_coa(tenant, template="personal")
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, desc="WOOLWORTHS CT")
        # Suggest via API
        r = client.post(
            "/v1/classifications/suggest",
            headers=h,
            json={"description": "WOOLWORTHS CT", "account_number": "123456"},
        )
        assert r.status_code == 200
        assert r.json()["nature"] == "private"
        # Accept without reason -> 422
        r = client.post(
            f"/v1/review-queue/{txn['id']}/accept", headers=h, json={"reason": "  "}
        )
        assert r.status_code == 422
        # Accept posts + confirms
        r = client.post(
            f"/v1/review-queue/{txn['id']}/accept",
            headers=h,
            json={"reason": "looks correct"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "confirmed"
        assert body["journal_entry"]["debits"] == body["journal_entry"]["credits"]
        # Trial balance via API
        r = client.get("/v1/journal/trial-balance", headers=h)
        assert r.status_code == 200
        assert r.json()["balanced"] is True
        # Edit description with reason -> revision + fingerprint update
        txn2 = _txn(tenant, bank_id, desc="CHECKERS 123", date="2026-10-12")
        r = client.post(
            f"/v1/review-queue/{txn2['id']}/edit",
            headers=h,
            json={"description_raw": "CHECKERS 456", "reason": "typo fix"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["updated_fields"] == ["description_raw"]
        assert len(r.json()["revisions"]) == 1
        # Cross-tenant: second user cannot accept first tenant txn
        tenant2 = f"day4api2-{uuid.uuid4().hex[:6]}"
        email2 = f"day4b_{uuid.uuid4().hex[:6]}@test.com"
        client.post(
            "/v1/auth/register",
            json={
                "email": email2,
                "password": "pass1234",
                "name": "T2",
                "tenant_id": tenant2,
            },
        )
        r2 = client.post(
            "/v1/auth/login", json={"email": email2, "password": "pass1234"}
        )
        h2 = {"X-User-Id": str(r2.json()["id"])}
        r = client.post(
            f"/v1/review-queue/{txn2['id']}/accept",
            headers=h2,
            json={"reason": "hijack"},
        )
        assert r.status_code == 403
        cleanup_tenant(tenant2)
    finally:
        cleanup_tenant(tenant)


def test_journal_post_endpoint_422_cases():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"day4j-{uuid.uuid4().hex[:6]}"
    email = f"day4j_{uuid.uuid4().hex[:6]}@test.com"
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
        # Unknown txn
        r = client.post(
            "/v1/journal/post",
            headers=h,
            json={"transaction_id": "nope", "category_id": "6020"},
        )
        assert r.status_code == 422
        # Unknown category
        r = client.post(
            "/v1/journal/post",
            headers=h,
            json={"transaction_id": txn["id"], "category_id": "NOPE"},
        )
        assert r.status_code == 422
        assert "Invalid parameters" in r.text
        # Bad trial-balance date
        r = client.get("/v1/journal/trial-balance?as_of=not-a-date", headers=h)
        assert r.status_code == 422
    finally:
        cleanup_tenant(tenant)
