"""
Vendor auto-book must behave like a human accept: balanced journal PLUS a
rule-sourced classification, confirmed status, and audit rows. Before the
fix it posted orphan journals (visible in Journal, invisible to
Private-vs-Business, unfixable from any screen).
"""

import uuid

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.vendor import create_vendor_rule, auto_book_journal_for_rule
from apps.worker.parsers.registry import seed_coa


def _setup(prefix="vab"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    init_db()
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    seed_coa(tenant, template="personal", db=db)
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type,"
        " account_number, template) VALUES (?,?,?,?,?,?,?)",
        (f"bank-{tenant}-111", tenant, "1000", "Bank 111", "asset",
         "111", "personal"),
    )
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number,"
        " txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (txn_id, tenant, f"bank-{tenant}-111", "111", "2026-10-10",
         "SASOL FUEL", -10000, "debit", f"fp-{uuid.uuid4().hex[:8]}",
         "proposed"),
    )
    db.commit()
    cur = db.execute("SELECT id, code FROM accounts WHERE tenant_id=?"
                     " AND code=? AND account_number IS NULL",
                     (tenant, "6030"))
    row = cur.fetchone()
    target_id = row["id"] if isinstance(row, dict) else row[0]
    rule_id = create_vendor_rule(tenant, "sasol", "111", target_id,
                                 "6030", "business", 100, True, None)
    cur = db.execute("SELECT * FROM vendor_rules WHERE id=?", (rule_id,))
    row = cur.fetchone()
    rule = dict(row) if not isinstance(row, dict) else row
    return tenant, txn_id, rule


def test_auto_book_classifies_confirms_audits():
    tenant, txn_id, rule = _setup()
    db = get_db()
    try:
        assert auto_book_journal_for_rule(txn_id, rule) is True
        cur = db.execute("SELECT * FROM classifications"
                         " WHERE transaction_id=?", (txn_id,))
        rows = cur.fetchall()
        assert len(rows) == 1
        cls = dict(rows[0]) if not isinstance(rows[0], dict) else rows[0]
        assert cls["source"] == "rule"
        assert cls["category_id"] == "6030"
        assert cls["nature"] == "business"
        cur = db.execute("SELECT status FROM transactions WHERE id=?",
                         (txn_id,))
        row = cur.fetchone()
        assert (row["status"] if isinstance(row, dict) else row[0]) \
            == "confirmed"
        cur = db.execute("SELECT action FROM audit_log WHERE tenant_id=?",
                         (tenant,))
        actions = {(r["action"] if isinstance(r, dict) else r[0])
                   for r in cur.fetchall()}
        assert "classification.rule_auto_book" in actions
        assert "journal.auto_book" in actions
    finally:
        cleanup_tenant(tenant)


def test_auto_book_without_target_changes_nothing():
    tenant, txn_id, rule = _setup()
    db = get_db()
    try:
        rule["target_account_id"] = None
        assert auto_book_journal_for_rule(txn_id, rule) is False
        cur = db.execute("SELECT status FROM transactions WHERE id=?",
                         (txn_id,))
        row = cur.fetchone()
        assert (row["status"] if isinstance(row, dict) else row[0]) \
            == "proposed"
    finally:
        cleanup_tenant(tenant)
