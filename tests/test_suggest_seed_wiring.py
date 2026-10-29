"""
Suggest->seed->post wiring: the suggester must only propose codes that exist
in the tenant's active books, carry the account name for the UI, and never
fail a fresh tenant with 'Seed COA first'.

Regression for: save failed with "code '9999' does not exist for tenant
'demo-tenant' in template 'personal'. Seed COA first" + suggester showing a
bare code with no name/selector and proposing sme_cc codes (6200/6100/...)
while the tenant works in personal books.
"""

import uuid

import pytest

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import suggest_classification
from apps.api.ledger import resolve_account
from apps.worker.parsers.registry import set_active_template


def _tenant(prefix="sugwire"):
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


def _txn(tenant, bank_id, acct_no="123456", amount=-45000,
         direction="debit", desc="SASOL FUEL", date="2026-10-10"):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number, txn_date,"
        " description_raw, amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, bank_id, acct_no, date, desc,
         amount, direction, f"fp-{uuid.uuid4().hex[:8]}", "proposed"),
    )
    db.commit()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    return dict(row) if not isinstance(row, dict) else row


def test_suggest_autoseeds_fresh_tenant_and_names_account():
    """Fresh tenant (never opened books): suggest seeds + names the account."""
    tenant = _tenant()
    try:
        sug = suggest_classification(
            "SASOL FUEL", "123456", tenant,
            amount_minor=-10000, direction="debit",
        )
        assert sug["active_template"] == "personal"
        assert sug["account_name"], "UI needs code + name, not a bare code"
        assert sug["account_type"]
        # Must resolve in the tenant's books (no 'Seed COA first' on save)
        acct = resolve_account(tenant, code=sug["category_id"])
        assert acct["name"] == sug["account_name"]
    finally:
        cleanup_tenant(tenant)


def test_suggest_unknown_parks_in_seeded_9999():
    tenant = _tenant()
    try:
        sug = suggest_classification(
            "XQZ UNKNOWN 12345", "123", tenant,
            amount_minor=-500, direction="debit",
        )
        assert sug["category_id"] == "9999"
        assert "Suspense" in (sug.get("account_name") or "")
        resolve_account(tenant, code="9999")  # seeded, no raise
    finally:
        cleanup_tenant(tenant)


@pytest.mark.parametrize("template,desc,raw", [
    ("personal", "SASOL FUEL", "6200"),
    ("personal", "OFFICE RENT", "6100"),
    ("personal", "SUPPLIER SERVICE FEE", "6600"),
    ("personal", "ESKOM POWER", "6400"),
    ("personal", "WOOLWORTHS FOOD", "6020"),
    ("personal", "SUPPLIER STEEL", "6000"),
    ("sme_cc", "WOOLWORTHS FOOD", "6020"),
    ("sme_cc", "SASOL FUEL", "6200"),
    ("mixed_sole_prop", "OFFICE RENT", "6100"),
    ("mixed_sole_prop", "ESKOM POWER", "6400"),
])
def test_suggest_code_always_exists_in_active_template(template, desc, raw):
    """Every suggested code must resolve in the active books (suggester wired
    to the same COA the ledger posts to)."""
    tenant = _tenant()
    try:
        set_active_template(tenant, template)
        sug = suggest_classification(
            desc, "123", tenant, amount_minor=-10000, direction="debit"
        )
        acct = resolve_account(tenant, code=sug["category_id"])
        assert acct["template"] == template
        if sug["category_id"] != raw:
            assert sug.get("mapped_from") == raw
    finally:
        cleanup_tenant(tenant)


def test_suggest_salary_inflow_maps_to_income_not_expense():
    tenant = _tenant()
    try:
        sug = suggest_classification(
            "SALARY ACME LTD", "123", tenant,
            amount_minor=100000, direction="credit",
        )
        assert sug["category_id"] == "4000"
        assert sug["account_type"] == "income"
    finally:
        cleanup_tenant(tenant)


def test_stale_rule_category_remaps_to_active_template():
    """A merchant rule learned under sme_cc (6100 Rent) must not propose a
    code missing from personal books after the user switches books."""
    from apps.api.vendor import create_vendor_rule

    tenant = _tenant()
    try:
        set_active_template(tenant, "sme_cc")
        db = get_db()
        cur = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND code='6100' LIMIT 1",
            (tenant,),
        )
        row = cur.fetchone()
        acc_id = row["id"] if isinstance(row, dict) else row[0]
        create_vendor_rule(
            tenant, "RENTALPROP", "123456", acc_id, "6100",
            "business", 100, auto_book=False, decided_by=None,
        )
        set_active_template(tenant, "personal")
        sug = suggest_classification("RENTALPROP MONTHLY", "123456", tenant)
        assert sug["source"] == "rule"
        # 6100 does not exist in personal -> remapped to a valid code
        resolve_account(tenant, code=sug["category_id"])
        assert sug["category_id"] != "6100"
    finally:
        cleanup_tenant(tenant)


def test_accept_works_on_fresh_tenant_via_api():
    """Upload -> suggest -> accept on a tenant that never opened books:
    no 'Seed COA first', journal posts, trial balance stays wired."""
    from fastapi.testclient import TestClient

    from apps.api.main import app
    from apps.api.ledger import trial_balance

    client = TestClient(app)
    init_db()
    tenant = f"sugapi-{uuid.uuid4().hex[:6]}"
    email = f"sug_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234",
              "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id)
        r = client.post(
            f"/v1/review-queue/{txn['id']}/accept",
            headers=h,
            json={"reason": "looks like fuel"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "confirmed"
        tb = trial_balance(tenant)
        assert tb["balanced"] is True
        codes = {ln["code"] for ln in tb["lines"]
                 if ln["debits"] or ln["credits"]}
        assert body["classification"]["category_id"] in codes
    finally:
        cleanup_tenant(tenant)


def test_accounts_endpoint_lists_active_coa_with_names():
    from fastapi.testclient import TestClient

    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"sugacc-{uuid.uuid4().hex[:6]}"
    email = f"sugacc_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234",
              "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login",
                    json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        r = client.get("/v1/accounts", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["active_template"] == "personal"
        opts = {a["code"]: a for a in body["accounts"]}
        assert "9999" in opts and "Suspense" in opts["9999"]["name"]
        assert "6020" in opts
        assert all(a["name"] and a["type"] for a in body["accounts"])
    finally:
        cleanup_tenant(tenant)
