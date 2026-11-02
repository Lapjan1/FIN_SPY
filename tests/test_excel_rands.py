"""Workbook money matches the webapp: rands with 2dp, never raw cents.

Regression: books page shows R100.00 (formatRands divides minor by 100)
while the Excel workbook wrote the raw 10000 minor int into Journal /
Transactions / Trial_Balance cells.
"""
import uuid

import openpyxl

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.reports import generate_excel_workbook


def _seed(tenant):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
    acc = {}
    for code, name, typ in (("1000", "Bank", "asset"),
                            ("4000", "Salary", "income")):
        aid = f"acc-{code}-{uuid.uuid4().hex[:6]}"
        db.execute("INSERT INTO accounts (id, tenant_id, code, name, type)"
                   " VALUES (?,?,?,?,?)",
                   (aid, tenant, code, name, typ))
        acc[code] = aid
    eid = f"je-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO journal_entries (id, tenant_id, entry_date, memo,"
               " posted) VALUES (?,?,?,?,?)",
               (eid, tenant, "2026-03-01", "salary", 0))
    for code, dr, cr in (("1000", 10000, 0), ("4000", 0, 10000)):
        db.execute("INSERT INTO journal_lines (id, entry_id, account_id,"
                   " debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                   (f"jl-{uuid.uuid4().hex[:8]}", eid, acc[code], dr, cr))
    db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (eid,))
    db.execute(
        "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
        " amount_minor, direction, balance_after_minor,"
        " fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?)",
        (f"txn-{uuid.uuid4().hex[:8]}", tenant, "2026-03-15", "SALARY",
         10000, "credit", 10000, f"xr-{uuid.uuid4().hex[:8]}", "confirmed"))
    db.commit()


def test_workbook_money_in_rands_not_cents():
    init_db()
    tenant = f"xlr-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_excel_workbook(tenant)
        wb = openpyxl.load_workbook(out["file_key"])
        # Journal legs: R100.00 stored as 10000 minor must read 100
        jvals = [[c.value for c in row] for row in
                 wb["Journal"].iter_rows(min_row=2, values_only=False)]
        assert len(jvals) == 2
        assert sorted(r[5] for r in jvals) == [0, 100]
        assert sorted(r[6] for r in jvals) == [0, 100]
        # Transactions amount + balance in rands, headers say so
        theaders = [c.value for c in wb["Transactions"][1]]
        assert "amount" in theaders, theaders
        assert "amount_minor" not in theaders, theaders
        trow = {h: v for h, v in
                zip(theaders, [c.value for c in wb["Transactions"][2]])}
        assert trow["amount"] == 100
        assert trow["balance_after"] == 100
        # Summary totals in rands
        summ = {wb["Summary"].cell(row=r, column=1).value:
                wb["Summary"].cell(row=r, column=2).value for r in range(1, 12)}
        assert summ["Debits (R)"] == 100
        assert summ["Credits (R)"] == 100
        assert summ["Balanced"] == "yes"
        # Trial balance still live formulas over the Journal legs
        tb = wb["Trial_Balance"]
        assert str(tb.cell(row=2, column=4).value).startswith("=SUMIFS(")
        # Cover must not claim minor units anymore
        cover = " ".join(str(c.value or "") for row in
                         wb["Cover"].iter_rows(min_col=1, max_col=1)
                         for c in row)
        assert "minor units (cents)" not in cover
    finally:
        cleanup_tenant(tenant)
