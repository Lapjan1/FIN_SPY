"""
Reports slice by bank account: excel / auditor-csv / powerbi accept
account_number and return only that account's rows. Evidence pack and
signed PDF stay whole-tenant (forensic/legal bundles must be complete).
"""

import csv
import uuid
from pathlib import Path

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.classify import decide
from apps.api.ledger import post_transaction
from apps.api.reports import (generate_excel_workbook, generate_auditor_csv,
                              generate_powerbi_pack)
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


def test_excel_filters_to_account():
    import openpyxl

    init_db()
    tenant = f"repacct-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_excel_workbook(tenant, account_number="111")
        wb = openpyxl.load_workbook(out["file_key"])
        ws = wb["Journal"]
        codes = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            codes.add(row[3])
        assert codes == {"6030", "1000"}, codes
    finally:
        cleanup_tenant(tenant)


def test_auditor_csv_filters_to_account():
    init_db()
    tenant = f"repacct2-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_auditor_csv(tenant, account_number="222")
        assert out["count"] == 1
        with open(out["file_key"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["account_number"] == "222"
    finally:
        cleanup_tenant(tenant)


def test_powerbi_filters_to_account():
    init_db()
    tenant = f"repacct3-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_powerbi_pack(tenant, account_number="111")
        csv_path = Path(out["csv_dir"]) / "fact_transactions.csv"
        with csv_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["account_number"] == "111"
    finally:
        cleanup_tenant(tenant)
