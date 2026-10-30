"""Excel Transactions sheet carries account + classification columns so a
user can see why each row posts where it does."""

import uuid

import openpyxl

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import decide
from apps.api.ledger import post_transaction
from apps.api.reports import generate_excel_workbook
from apps.worker.parsers.registry import seed_coa


def _seed(tenant):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    seed_coa(tenant, template="personal", db=db)
    for acct, cat in (("111", "6030"), ("222", "6040")):
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-{acct}", tenant, "1000",
             f"Bank {acct}", "asset", acct, "personal"),
        )
        txn_id = f"txn-{tenant}-{acct}"
        db.execute(
            "INSERT INTO transactions (id, tenant_id, account_id,"
            " account_number, txn_date, description_raw, amount_minor,"
            " direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (txn_id, tenant, f"bank-{tenant}-{acct}", acct,
             "2026-10-10", f"SHOP {acct}", -5000, "debit",
             f"fp-{tenant}-{acct}", "proposed"),
        )
        db.commit()
        cur = db.execute("SELECT * FROM transactions WHERE id=?",
                         (txn_id,))
        row = cur.fetchone()
        txn = dict(row) if not isinstance(row, dict) else row
        cls = decide(txn_id, "business", 100, cat, "seed", None,
                     "seed", tenant)
        post_transaction(txn, {"id": cls["id"], "category_id": cat,
                              "nature": "business", "business_pct": 100})


def test_excel_transactions_show_classification():
    init_db()
    tenant = f"xlcls-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_excel_workbook(tenant)
        wb = openpyxl.load_workbook(out["file_key"])
        ws = wb["Transactions"]
        headers = [c.value for c in ws[1]]
        for col in ("account_number", "document", "nature", "category",
                    "rationale", "status"):
            assert col in headers, headers
        cats = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            asdict = dict(zip(headers, row))
            cats.add(asdict["category"])
            assert asdict["account_number"] in ("111", "222")
            assert asdict["nature"] == "business"
            assert asdict["status"] in ("proposed", "confirmed")
        assert cats == {"6030", "6040"}, cats
    finally:
        cleanup_tenant(tenant)


def test_excel_unknown_scope_does_not_crash():
    init_db()
    tenant = f"xlunk-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_excel_workbook(tenant, account_number="__unknown")
        wb = openpyxl.load_workbook(out["file_key"])
        ws = wb["Transactions"]
        assert ws.max_row == 1  # header only, both seeds are known
    finally:
        cleanup_tenant(tenant)
