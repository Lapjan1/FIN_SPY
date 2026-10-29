"""
Day-7 Excel: 12-sheet bounded workbook (P&L + balance sheet + totals-all-codes
trial balance), 12-month window cap, posted-only, live SUMIFS formulas.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.reports import generate_excel_workbook


def _seed(tenant):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, tenant))
    acc = {}
    for code, name, typ in (("1000", "Bank", "asset"),
                            ("4000", "Salary", "income"),
                            ("6000", "Groceries", "expense")):
        aid = f"acc-{code}-{uuid.uuid4().hex[:6]}"
        db.execute("INSERT INTO accounts (id, tenant_id, code, name, type)"
                   " VALUES (?,?,?,?,?)",
                   (aid, tenant, code, name, typ))
        acc[code] = aid
    db.commit()
    entries = [("2026-03-01", 1, [("1000", 500000, 0), ("4000", 0, 500000)]),
               ("2026-04-01", 1, [("6000", 50000, 0), ("1000", 0, 50000)]),
               ("2026-05-01", 0, [("6000", 99999, 0), ("1000", 0, 99999)])]
    for i, (date, posted, legs) in enumerate(entries):
        eid = f"je-{i}-{uuid.uuid4().hex[:6]}"
        db.execute("INSERT INTO journal_entries (id, tenant_id, entry_date, memo,"
                   " posted) VALUES (?,?,?,?,?)",
                   (eid, tenant, date, f"entry {i}", 0))
        for code, dr, cr in legs:
            db.execute("INSERT INTO journal_lines (id, entry_id, account_id,"
                       " debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                       (f"jl-{uuid.uuid4().hex[:8]}", eid, acc[code], dr, cr))
        if posted:
            db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (eid,))
    for txn_date in ("2026-03-15", "2025-01-10"):
        db.execute(
            "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (f"txn-{uuid.uuid4().hex[:8]}", tenant, txn_date, "SEED",
             1000, "debit", f"xl-{uuid.uuid4().hex[:8]}", "confirmed"))
    db.commit()


def _wb(path):
    import openpyxl
    return openpyxl.load_workbook(path)


def test_workbook_12_sheets_posted_only_windowed():
    init_db()
    tenant = f"xl7-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        out = generate_excel_workbook(tenant, "2026-01-01", "2026-12-31")
        assert out["sheets"] == 12
        wb = _wb(out["file_key"])
        expect = ["Cover", "Summary", "Transactions", "Journal", "Trial_Balance",
                  "Income_Statement", "Balance_Sheet", "Private_vs_Business",
                  "Flags", "Source_Register", "Method_Notes", "Dictionary"]
        assert wb.sheetnames == expect
        # Journal: posted only (2 entries x 2 legs, unposted 99999 excluded)
        jvals = [[c.value for c in row] for row in
                 wb["Journal"].iter_rows(min_row=2, values_only=False)]
        assert len(jvals) == 4
        assert all(99999 not in r for r in jvals)
        # Transactions: 2025 row outside window excluded
        tdates = [r[1].value for r in wb["Transactions"].iter_rows(min_row=2)]
        assert tdates == ["2026-03-15"]
        # Trial balance: all 3 codes + live SUMIFS
        tb = wb["Trial_Balance"]
        codes = [tb.cell(row=r, column=1).value for r in (2, 3, 4)]
        assert codes == ["1000", "4000", "6000"]
        assert str(tb.cell(row=2, column=4).value).startswith("=SUMIFS(")
        # P&L net links income minus expense; BS links P&L net
        pnl = wb["Income_Statement"]
        net_cells = [c.value for row in pnl.iter_rows() for c in row
                     if isinstance(c.value, str) and c.value.startswith("=D")]
        assert net_cells, "P&L must carry a net formula"
        bs = wb["Balance_Sheet"]
        links = [c.value for row in bs.iter_rows() for c in row
                 if isinstance(c.value, str) and "Income_Statement" in c.value]
        assert len(links) == 1, "balance sheet must link P&L net earnings"
        # Summary balanced + counts
        summ = {wb["Summary"].cell(row=r, column=1).value:
                wb["Summary"].cell(row=r, column=2).value for r in range(1, 12)}
        assert summ["Balanced"] == "yes"
        assert summ["Journal lines"] == 4
    finally:
        cleanup_tenant(tenant)


def test_window_validation():
    init_db()
    tenant = f"xl7w-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant)
        with pytest.raises(ValueError, match="12 months"):
            generate_excel_workbook(tenant, "2025-01-01", "2026-06-01")
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            generate_excel_workbook(tenant, "2026-13-01", None)
        with pytest.raises(ValueError, match="before from_date"):
            generate_excel_workbook(tenant, "2026-06-01", "2026-01-01")
        ok = generate_excel_workbook(tenant, "2026-01-01", "2026-12-31")
        assert ok["from_date"] == "2026-01-01"
    finally:
        cleanup_tenant(tenant)


def test_excel_endpoint_window_422():
    client = TestClient(app)
    init_db()
    tenant = f"xl7e-{uuid.uuid4().hex[:6]}"
    email = f"{tenant}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        r = client.get("/v1/reports/excel?from_date=2025-01-01&to_date=2026-06-01",
                       headers=h)
        assert r.status_code == 422
        r = client.get("/v1/reports/excel?from_date=2026-01-01&to_date=2026-12-31",
                       headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats")
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        assert len(wb.sheetnames) == 12
    finally:
        cleanup_tenant(tenant)
