"""
Reports - Excel workbook + PowerBI star-schema pack + Evidence Pack
Per homework Part 5.10: PowerBI-ready data pack fact_transactions, fact_journal, dim_date, dim_account, dim_category, dim_entity, dim_document as Excel file and CSVs
Per Appendix G Excel workbook map: Cover, Summary, Transactions Table, Journal, Trial_Balance live SUMIFS, Private_vs_Business, Flags, Source_Register, Method_Notes, Dictionary
"""
import os
import csv
import hashlib
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timezone

from .db import get_db

REPORTS_PATH = Path(os.getenv("REPORTS_PATH", "./data/reports"))
REPORTS_PATH.mkdir(parents=True, exist_ok=True)
VAULT_PATH = Path(os.getenv("VAULT_PATH", "./data/vault"))


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        import subprocess
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def generate_powerbi_pack(tenant_id: str) -> Dict:
    """
    Generate PowerBI-ready pack: Excel file with star-schema sheets + CSVs per homework Part 5.10
    Returns {file_key, sha256, csv_keys}
    """
    db = get_db()

    # Query star-schema views
    # fact_transactions
    cur = db.execute("SELECT * FROM fact_transactions WHERE tenant_id=?", (tenant_id,))
    fact_txn_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # fact_journal
    cur = db.execute("SELECT * FROM fact_journal WHERE tenant_id=?", (tenant_id,))
    fact_journal_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # dim_account
    cur = db.execute("SELECT * FROM dim_account WHERE tenant_id=?", (tenant_id,))
    dim_account_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # dim_category
    cur = db.execute("SELECT * FROM dim_category")
    dim_category_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # dim_entity
    cur = db.execute("SELECT * FROM dim_entity")
    dim_entity_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # dim_document
    cur = db.execute("SELECT * FROM dim_document WHERE tenant_id=?", (tenant_id,))
    dim_document_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # dim_date
    cur = db.execute("SELECT * FROM dim_date LIMIT 1000")
    dim_date_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # Generate Excel file with XlsxWriter
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    excel_path = REPORTS_PATH / f"powerbi_pack_{tenant_id}_{timestamp}.xlsx"
    csv_dir = REPORTS_PATH / f"powerbi_pack_{tenant_id}_{timestamp}_csvs"
    csv_dir.mkdir(exist_ok=True)

    try:
        import xlsxwriter
        wb = xlsxwriter.Workbook(str(excel_path))

        # Helper to write sheet from rows
        def write_sheet(name, rows):
            if not rows:
                ws = wb.add_worksheet(name[:31])
                ws.write(0,0, f"No data for {name}")
                return
            ws = wb.add_worksheet(name[:31])  # Excel sheet name max 31 chars
            headers = list(rows[0].keys())
            for col, h in enumerate(headers):
                ws.write(0, col, h)
            for r_idx, row in enumerate(rows, start=1):
                for c_idx, h in enumerate(headers):
                    ws.write(r_idx, c_idx, str(row.get(h, "")))

        # Cover sheet
        ws_cover = wb.add_worksheet("Cover")
        ws_cover.write(0,0, "FIN_SPY PowerBI Pack")
        ws_cover.write(1,0, f"Tenant: {tenant_id}")
        ws_cover.write(2,0, f"Generated: {timestamp} UTC")
        ws_cover.write(3,0, "Software: FIN_SPY v0.6.0")
        ws_cover.write(4,0, "Method: DB-first Extract -> persist to .db with spans bbox line_id + fingerprint -> all products read DB")

        # Data sheets
        write_sheet("fact_transactions", fact_txn_rows)
        write_sheet("fact_journal", fact_journal_rows)
        write_sheet("dim_account", dim_account_rows)
        write_sheet("dim_category", dim_category_rows)
        write_sheet("dim_entity", dim_entity_rows)
        write_sheet("dim_document", dim_document_rows)
        write_sheet("dim_date", dim_date_rows)

        # Method Notes sheet
        ws_method = wb.add_worksheet("Method_Notes")
        ws_method.write(0,0, "Method: DB-first, line-ID grounding, reconciliation gate both directions, hash-chain audit")
        ws_method.write(1,0, "Models: Muse Spark 1.3 standard NOT contributor, Wonder, Image, SAM 3.1 via Meta Model API")
        ws_method.write(2,0, "Privacy: Tenant isolation tenant_id, RLS path Supabase, POPIA compliance, retention 30 days")

        wb.close()
    except Exception as e:
        # Fallback if xlsxwriter not available: create empty file
        excel_path.write_text(f"Error generating Excel: {e}\nFact transactions: {len(fact_txn_rows)} rows")

    # Generate CSVs for PowerBI Desktop free
    def write_csv(name, rows):
        csv_path = csv_dir / f"{name}.csv"
        if not rows:
            csv_path.write_text(f"No data for {name}\n")
            return str(csv_path)
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return str(csv_path)

    csv_keys = []
    csv_keys.append(write_csv("fact_transactions", fact_txn_rows))
    csv_keys.append(write_csv("fact_journal", fact_journal_rows))
    csv_keys.append(write_csv("dim_account", dim_account_rows))
    csv_keys.append(write_csv("dim_category", dim_category_rows))
    csv_keys.append(write_csv("dim_entity", dim_entity_rows))
    csv_keys.append(write_csv("dim_document", dim_document_rows))
    csv_keys.append(write_csv("dim_date", dim_date_rows))

    # Compute SHA256
    sha256 = hashlib.sha256(excel_path.read_bytes()).hexdigest() if excel_path.exists() else ""

    return {
        "file_key": str(excel_path),
        "sha256": sha256,
        "csv_dir": str(csv_dir),
        "csv_keys": csv_keys,
        "counts": {
            "fact_transactions": len(fact_txn_rows),
            "fact_journal": len(fact_journal_rows),
            "dim_account": len(dim_account_rows),
            "dim_category": len(dim_category_rows),
            "dim_entity": len(dim_entity_rows),
            "dim_document": len(dim_document_rows),
            "dim_date": len(dim_date_rows),
        }
    }

def generate_auditor_csv(tenant_id: str) -> Dict:
    """
    Generate CSV for auditor to input in their bookkeeping package per user decision:
    Export package the auditor can use the data export to csv and input in their bookkeeping package
    For our usage we document transactions and we can view and represent the data in any way we would like to use it to enhance personal or sme businesse
    Per docs/DISCLAIMER.md: private/business only, mixed exceptional startup, respect and give info and user deals with auditor and SARS
    """
    db = get_db()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = REPORTS_PATH / f"auditor_export_{tenant_id}_{timestamp}.csv"

    # Query transactions with classifications and account info for auditor
    cur = db.execute("""
        SELECT t.id, t.txn_date as date, t.description_raw as description, t.amount_minor, t.currency, t.direction,
               t.balance_after_minor, t.fingerprint_sha256, t.status, t.account_number, t.document_id,
               c.nature, c.business_pct, c.category_id, c.rationale, c.confidence, c.decided_by, c.source,
               a.code as account_code, a.name as account_name, a.type as account_type, a.bank_name, a.branch_code,
               d.original_filename, d.sha256 as doc_sha256
        FROM transactions t
        LEFT JOIN classifications c ON t.id = c.transaction_id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN source_documents d ON t.document_id = d.id
        WHERE t.tenant_id=?
        ORDER BY t.txn_date ASC
    """, (tenant_id,))
    rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]

    # Write CSV with headers suitable for Pastel, Xero, QuickBooks, Sage import
    # Include private/business classification with business_pct for mixed exceptional startup per disclaimer
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        fieldnames = ["id","date","description","amount_minor","amount_rands","currency","direction","balance_after_minor","fingerprint","status","account_number","bank_name","branch_code","account_code","account_name","account_type","nature","business_pct","category_id","rationale","confidence","source","decided_by","document_id","original_filename","doc_sha256"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            # Convert amount_minor to Rands for auditor
            amount_rands = r.get('amount_minor',0)/100 if r.get('amount_minor') else 0
            writer.writerow({
                "id": r.get('id',''),
                "date": r.get('date',''),
                "description": r.get('description',''),
                "amount_minor": r.get('amount_minor',''),
                "amount_rands": f"{amount_rands:.2f}",
                "currency": r.get('currency','ZAR'),
                "direction": r.get('direction',''),
                "balance_after_minor": r.get('balance_after_minor',''),
                "fingerprint": r.get('fingerprint_sha256',''),
                "status": r.get('status',''),
                "account_number": r.get('account_number',''),
                "bank_name": r.get('bank_name',''),
                "branch_code": r.get('branch_code',''),
                "account_code": r.get('account_code',''),
                "account_name": r.get('account_name',''),
                "account_type": r.get('account_type',''),
                "nature": r.get('nature',''),  # private/business/mixed per disclaimer private/business only, mixed exceptional startup
                "business_pct": r.get('business_pct',''),
                "category_id": r.get('category_id',''),
                "rationale": r.get('rationale',''),
                "confidence": r.get('confidence',''),
                "source": r.get('source',''),
                "decided_by": r.get('decided_by',''),
                "document_id": r.get('document_id',''),
                "original_filename": r.get('original_filename',''),
                "doc_sha256": r.get('doc_sha256',''),
            })

    sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest() if csv_path.exists() else ""
    return {"file_key": str(csv_path), "sha256": sha256, "count": len(rows)}

def _validate_window(from_date: str | None, to_date: str | None) -> None:
    from datetime import date
    if not from_date and not to_date:
        return
    try:
        start = date.fromisoformat(from_date) if from_date else None
        end = date.fromisoformat(to_date) if to_date else None
    except ValueError:
        raise ValueError("Invalid parameters: dates must be YYYY-MM-DD")
    if start and end:
        if end < start:
            raise ValueError("Invalid parameters: to_date before from_date")
        if (end - start).days > 366:
            raise ValueError("Invalid parameters: window exceeds 12 months")


def _wb_fetch(tenant_id: str, from_date, to_date, lim: int) -> Dict:
    db = get_db()

    def dated(table_col: str):
        q, p = "", []
        if from_date:
            q += f" AND {table_col}>=?"
            p.append(from_date)
        if to_date:
            q += f" AND {table_col}<=?"
            p.append(to_date)
        return q, p

    jq, jp = dated("je.entry_date")
    cur = db.execute(
        "SELECT je.id, je.entry_date, je.memo, a.code, a.name, jl.debit_minor,"
        " jl.credit_minor FROM journal_entries je JOIN journal_lines jl"
        " ON je.id=jl.entry_id LEFT JOIN accounts a ON jl.account_id=a.id"
        " WHERE je.tenant_id=? AND je.posted=1" + jq +
        " ORDER BY je.entry_date ASC LIMIT ?", (tenant_id, *jp, lim))
    journal = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    tq, tp = dated("txn_date")
    cur = db.execute(
        "SELECT id, txn_date, description_raw, amount_minor, direction,"
        " balance_after_minor, fingerprint_sha256, status, document_id"
        " FROM transactions WHERE tenant_id=?" + tq +
        " ORDER BY txn_date DESC LIMIT ?", (tenant_id, *tp, lim))
    txns = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    cur = db.execute("SELECT COUNT(*) as n FROM journal_lines jl JOIN journal_entries je"
                     " ON jl.entry_id=je.id WHERE je.tenant_id=? AND je.posted=1" + jq,
                     (tenant_id, *jp))
    _crow = cur.fetchone()
    jl_count = _crow["n"] if isinstance(_crow, dict) else _crow[0]
    cur = db.execute("SELECT id, code, name, type FROM accounts WHERE tenant_id=?"
                     " ORDER BY code ASC", (tenant_id,))
    accounts = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    cur = db.execute(
        "SELECT c.nature, COUNT(*) as n,"
        " SUM(CASE WHEN t.direction='credit' THEN t.amount_minor ELSE 0 END) as inflow,"
        " SUM(CASE WHEN t.direction='debit' THEN t.amount_minor ELSE 0 END) as outflow"
        " FROM classifications c JOIN transactions t ON c.transaction_id=t.id"
        " WHERE t.tenant_id=?" + tq.replace("txn_date", "t.txn_date") +
        " GROUP BY c.nature", (tenant_id, *tp))
    nature_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    cur = db.execute("SELECT id, test_id, severity, result_json, created_at FROM flags"
                     " WHERE tenant_id=? ORDER BY created_at DESC LIMIT 500", (tenant_id,))
    flags = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    cur = db.execute("SELECT id, sha256, original_filename, size_bytes, status,"
                     " uploaded_at_utc FROM source_documents WHERE tenant_id=?"
                     " ORDER BY uploaded_at_utc DESC LIMIT 500", (tenant_id,))
    docs = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    return {"journal": journal, "txns": txns, "jl_count": jl_count,
            "accounts": accounts, "nature_rows": nature_rows,
            "flags": flags, "docs": docs}


def _wb_dump(ws, rows, headers, bold):
    for c, h in enumerate(headers):
        ws.write(0, c, h, bold)
    for ri, row in enumerate(rows, start=1):
        for ci, h in enumerate(headers):
            ws.write(ri, ci, row.get(h, ""))


def _wb_section(ws, start_row: int, title: str, codes):
    """Account block with live SUMIFS debit/credit per code. Returns the
    0-based row after the last item (where the caller writes its total)."""
    ws.write(start_row, 0, title)
    r = start_row + 1
    for code, name in codes:
        ws.write(r, 0, code)
        ws.write(r, 1, name)
        ws.write_formula(r, 2, f"=SUMIFS(Journal!F:F,Journal!D:D,\"{code}\")")
        ws.write_formula(r, 3, f"=SUMIFS(Journal!G:G,Journal!D:D,\"{code}\")")
        r += 1
    return r


def _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data):
    ws = wb.add_worksheet("Cover")
    ws.write(0, 0, "FIN_SPY Workbook", bold)
    ws.write(1, 0, f"Tenant: {tenant_id}")
    ws.write(2, 0, f"Period: {from_date or '...'} to {to_date or '...'} (max 12 months)")
    ws.write(3, 0, f"Generated: {ts} UTC")
    ws.write(4, 0, "Money in minor units (cents); formulas live - edit Journal, totals follow.")
    tot_d = sum(j.get("debit_minor", 0) for j in data["journal"])
    tot_c = sum(j.get("credit_minor", 0) for j in data["journal"])
    ws = wb.add_worksheet("Summary")
    for ri, (k, v) in enumerate([
        ("Period from", from_date or ""), ("Period to", to_date or ""),
        ("Journal lines", len(data["journal"])),
        ("Journal lines truncated", "yes" if data["jl_count"] > 5000 else "no"),
        ("Transactions", len(data["txns"])),
        ("Debits (minor)", tot_d), ("Credits (minor)", tot_c),
        ("Balanced", "yes" if tot_d == tot_c else "NO"),
        ("Accounts", len(data["accounts"])), ("Flags", len(data["flags"])),
        ("Documents", len(data["docs"])),
    ]):
        ws.write(ri, 0, k, bold)
        ws.write(ri, 1, v)


def _wb_txns_journal(wb, bold, data):
    ws = wb.add_worksheet("Transactions")
    _wb_dump(ws, [{"id": t.get("id", ""), "txn_date": t.get("txn_date", ""),
                   "description": t.get("description_raw", ""),
                   "amount_minor": t.get("amount_minor", 0),
                   "direction": t.get("direction", ""),
                   "balance_after": t.get("balance_after_minor", ""),
                   "fingerprint": t.get("fingerprint_sha256", ""),
                   "status": t.get("status", ""),
                   "document_id": t.get("document_id", "")} for t in data["txns"]],
             ["id", "txn_date", "description", "amount_minor", "direction",
              "balance_after", "fingerprint", "status", "document_id"], bold)
    ws = wb.add_worksheet("Journal")
    _wb_dump(ws, [{"entry_id": j.get("id", ""), "entry_date": j.get("entry_date", ""),
                   "memo": j.get("memo", ""), "account_code": j.get("code", ""),
                   "account_name": j.get("name", ""),
                   "debit": j.get("debit_minor", 0),
                   "credit": j.get("credit_minor", 0)} for j in data["journal"]],
             ["entry_id", "entry_date", "memo", "account_code", "account_name",
              "debit", "credit"], bold)


def _wb_trial(wb, bold, accounts):
    ws = wb.add_worksheet("Trial_Balance")
    for c, h in enumerate(["Code", "Name", "Type", "Debit", "Credit", "Net (D-C)"]):
        ws.write(0, c, h, bold)
    for ri, a in enumerate(accounts, start=1):
        ws.write(ri, 0, a.get("code", ""))
        ws.write(ri, 1, a.get("name", ""))
        ws.write(ri, 2, a.get("type", ""))
        xl = ri + 1  # 1-based row of this account
        ws.write_formula(ri, 3, f"=SUMIFS(Journal!F:F,Journal!D:D,Trial_Balance!A{xl})")
        ws.write_formula(ri, 4, f"=SUMIFS(Journal!G:G,Journal!D:D,Trial_Balance!A{xl})")
        ws.write_formula(ri, 5, f"=D{xl}-E{xl}")
    tr = len(accounts) + 1  # 0-based TOTAL row
    ws.write(tr, 0, "TOTAL", bold)
    ws.write_formula(tr, 3, f"=SUM(D2:D{tr})")
    ws.write_formula(tr, 4, f"=SUM(E2:E{tr})")
    ws.write_formula(tr, 5, f"=D{tr + 1}-E{tr + 1}")
    ws.write(tr + 1, 0, "Balanced?", bold)
    ws.write_formula(tr + 1, 3, f'=IF(D{tr + 1}=E{tr + 1},"yes","NO")')


def _wb_pnl(wb, bold, accounts) -> int:
    """Income statement. Returns the xl row of NET PROFIT for BS linking."""
    ws = wb.add_worksheet("Income_Statement")
    for c, h in enumerate(["Code", "Name", "Debit", "Credit"]):
        ws.write(0, c, h, bold)
    inc = [(a["code"], a["name"]) for a in accounts if a.get("type") == "income"]
    exp = [(a["code"], a["name"]) for a in accounts if a.get("type") == "expense"]
    r = _wb_section(ws, 1, "INCOME", inc)
    inc_total = r + 1  # xl row of income total (items xl 3..inc_total-1)
    ws.write(r, 0, "Income total (C-D)", bold)
    if inc:
        ws.write_formula(r, 3, f"=SUM(D3:D{inc_total - 1})-SUM(C3:C{inc_total - 1})")
    else:
        ws.write(r, 3, 0)
    r = _wb_section(ws, r + 2, "EXPENSE", exp)
    exp_total = r + 1  # xl row (items xl exp_total-len(exp)..exp_total-1)
    ws.write(r, 0, "Expense total (D-C)", bold)
    if exp:
        first = exp_total - len(exp)
        ws.write_formula(r, 2, f"=SUM(C{first}:C{exp_total - 1})-SUM(D{first}:D{exp_total - 1})")
    else:
        ws.write(r, 2, 0)
    ws.write(r + 1, 0, "NET PROFIT", bold)
    ws.write_formula(r + 1, 3, f"=D{inc_total}-C{exp_total}")
    return r + 2  # xl row of NET PROFIT


def _wb_bs(wb, bold, accounts, pnl_net_xl: int):
    ws = wb.add_worksheet("Balance_Sheet")
    for c, h in enumerate(["Code", "Name", "Debit", "Credit"]):
        ws.write(0, c, h, bold)
    ast = [(a["code"], a["name"]) for a in accounts if a.get("type") == "asset"]
    leq = [(a["code"], a["name"]) for a in accounts if a.get("type") in ("liability", "equity")]
    r = _wb_section(ws, 1, "ASSETS", ast)
    ast_total = r + 1  # xl row (items xl 3..ast_total-1)
    ws.write(r, 0, "Assets total (D-C)", bold)
    if ast:
        ws.write_formula(r, 2, f"=SUM(C3:C{ast_total - 1})-SUM(D3:D{ast_total - 1})")
    else:
        ws.write(r, 2, 0)
    r = _wb_section(ws, r + 2, "LIABILITIES + EQUITY", leq)
    leq_total = r + 1  # xl row (items xl leq_total-len(leq)..leq_total-1)
    ws.write(r, 0, "L+E total (C-D)", bold)
    if leq:
        first = leq_total - len(leq)
        ws.write_formula(r, 3, f"=SUM(D{first}:D{leq_total - 1})-SUM(C{first}:C{leq_total - 1})")
    else:
        ws.write(r, 3, 0)
    ws.write(r + 1, 0, "Current earnings (P&L)", bold)
    ws.write_formula(r + 1, 3, f"='Income_Statement'!D{pnl_net_xl}")
    ws.write(r + 2, 0, "BALANCED?", bold)
    ws.write_formula(r + 2, 2, f'=IF(C{ast_total}=D{leq_total}+D{r + 2},"yes","NO")')


def _wb_misc(wb, bold, data):
    ws = wb.add_worksheet("Private_vs_Business")
    _wb_dump(ws, [{"nature": n.get("nature", ""), "count": n.get("n", 0),
                   "inflow_minor": n.get("inflow", 0),
                   "outflow_minor": n.get("outflow", 0)}
                  for n in data["nature_rows"]],
             ["nature", "count", "inflow_minor", "outflow_minor"], bold)
    ws = wb.add_worksheet("Flags")
    _wb_dump(ws, [{"id": f.get("id", ""), "test": f.get("test_id", ""),
                   "severity": f.get("severity", ""),
                   "result": (f.get("result_json", "") or "")[:500],
                   "created": f.get("created_at", "")} for f in data["flags"]],
             ["id", "test", "severity", "result", "created"], bold)
    ws = wb.add_worksheet("Source_Register")
    _wb_dump(ws, [{"id": d.get("id", ""), "filename": d.get("original_filename", ""),
                   "sha256": d.get("sha256", ""), "size": d.get("size_bytes", ""),
                   "status": d.get("status", ""),
                   "uploaded": d.get("uploaded_at_utc", "")} for d in data["docs"]],
             ["id", "filename", "sha256", "size", "status", "uploaded"], bold)
    ws = wb.add_worksheet("Method_Notes")
    for ri, line in enumerate([
        "DB-first: Extract -> persist with line IDs + bbox -> all products read DB.",
        "Money in minor units (cents); live SUMIFS recompute from Journal.",
        "Posted entries only (posted=1). Window capped at 12 months.",
        "Mixed classification exceptional (startup/sole-prop); see DISCLAIMER.md.",
    ]):
        ws.write(ri, 0, line)
    ws = wb.add_worksheet("Dictionary")
    for ri, (col, meaning) in enumerate([
        ("minor", "Integer cents, never float."),
        ("debit/credit", "Journal legs; debits must equal credits per entry."),
        ("nature", "private | business | mixed | unknown."),
        ("business_pct", "0-100 share of business use for mixed rows."),
        ("fingerprint", "SHA256(date|amount|desc_norm) dedup key."),
    ]):
        ws.write(ri, 0, col, bold)
        ws.write(ri, 1, meaning)


def generate_excel_workbook(tenant_id: str, from_date: str | None = None,
                            to_date: str | None = None) -> Dict:
    """
    Workbook per Appendix G + P&L + Balance Sheet, bounded to a 12-month
    window so a full year pulls in one memory-safe query:
    Cover, Summary, Transactions, Journal, Trial_Balance (totals all codes,
    live SUMIFS), Income_Statement, Balance_Sheet, Private_vs_Business,
    Flags, Source_Register, Method_Notes, Dictionary.
    Money in minor ints; posted entries only (posted=1).
    """
    import xlsxwriter

    _validate_window(from_date, to_date)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    excel_path = REPORTS_PATH / f"fin_spy_workbook_{tenant_id}_{ts}.xlsx"
    data = _wb_fetch(tenant_id, from_date, to_date, 5000)
    wb = xlsxwriter.Workbook(str(excel_path))
    bold = wb.add_format({"bold": True})
    _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data)
    _wb_txns_journal(wb, bold, data)
    _wb_trial(wb, bold, data["accounts"])
    pnl_net_xl = _wb_pnl(wb, bold, data["accounts"])
    _wb_bs(wb, bold, data["accounts"], pnl_net_xl)
    _wb_misc(wb, bold, data)
    wb.close()
    return {"file_key": str(excel_path), "sha256": _sha256_file(excel_path),
            "from_date": from_date, "to_date": to_date,
            "sheets": 12, "journal_lines": len(data["journal"]),
            "truncated": data["jl_count"] > 5000}


def generate_evidence_pack(tenant_id: str, report_id: str | None = None,
                             sign: bool = False) -> Dict:
    """
    Evidence Pack ZIP per Appendix C/D: originals + reports + audit chain +
    manifest.json + manifest.sha256, all SHA256-pinned. Verifiable with
    scripts/verify_pack.py (exit 0). TSA/PAdES placeholders stay null until
    Day-7 signing lands - never faked.
    """
    import json
    import shutil
    import uuid
    import zipfile

    db = get_db()
    report_id = report_id or f"pack-{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stage = REPORTS_PATH / f"pack_{tenant_id}_{timestamp}"
    (stage / "originals").mkdir(parents=True, exist_ok=True)
    (stage / "powerbi").mkdir(parents=True, exist_ok=True)
    files: List[Dict] = []

    def add_file(src: Path, rel: str, role: str, **extra):
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        entry = {"path": rel, "sha256": _sha256_file(dst), "role": role}
        entry.update(extra)
        files.append(entry)

    # 1. originals from vault (role original, never modified)
    cur = db.execute(
        "SELECT id, sha256, original_filename, uploaded_by, uploaded_at_utc,"
        " storage_key FROM source_documents WHERE tenant_id=?", (tenant_id,))
    for r in cur.fetchall():
        d = dict(r) if not isinstance(r, dict) else r
        src = Path(d["storage_key"]) if d.get("storage_key") else VAULT_PATH / f"{d['sha256']}.pdf"
        if not src.exists():
            src = VAULT_PATH / f"{d['sha256']}.pdf"
        if src.exists():
            add_file(src, f"originals/{d['sha256']}.pdf", "original",
                     uploaded_by=str(d.get("uploaded_by", "")),
                     uploaded_at_utc=str(d.get("uploaded_at_utc", "")))

    # 2. derived reports (role report)
    pb = generate_powerbi_pack(tenant_id)
    add_file(Path(pb["file_key"]), f"powerbi/{Path(pb['file_key']).name}",
             "report", derived_from="star-schema views")
    for ck in pb.get("csv_keys", []):
        add_file(Path(ck), f"powerbi/csvs/{Path(ck).name}",
                 "report", derived_from="star-schema views")
    wb = generate_excel_workbook(tenant_id)
    add_file(Path(wb["file_key"]), Path(wb["file_key"]).name, "report",
             derived_from="transactions+journal")
    ac = generate_auditor_csv(tenant_id)
    add_file(Path(ac["file_key"]), Path(ac["file_key"]).name, "report",
             derived_from="transactions+classifications")

    # 3. audit chain export (role audit)
    cur = db.execute(
        "SELECT id, actor_id, action, object_type, object_id, payload_json,"
        " prev_hash, row_hash, at_utc FROM audit_log WHERE tenant_id=?"
        " ORDER BY id ASC", (tenant_id,))
    audit_rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    audit_path = stage / "audit.json"
    audit_path.write_text(json.dumps(audit_rows, indent=2, default=str))
    files.append({"path": "audit.json", "sha256": _sha256_file(audit_path), "role": "audit"})

    # 4. extraction runs (role extraction_raw)
    cur = db.execute(
        "SELECT er.* FROM extraction_runs er JOIN source_documents d"
        " ON er.document_id = d.id WHERE d.tenant_id=?", (tenant_id,))
    runs = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    runs_path = stage / "extraction_runs.json"
    runs_path.write_text(json.dumps(runs, indent=2, default=str))
    files.append({"path": "extraction_runs.json", "sha256": _sha256_file(runs_path),
                  "role": "extraction_raw"})

    manifest = {
        "manifest_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tenant": tenant_id,
        "report_id": report_id,
        "software": {"git_commit": _git_commit(), "pipeline_version": "1.0.0"},
        "files": files,
        "extraction_runs": [
            {"id": r.get("id"), "model_id": r.get("model_id"),
             "prompt_sha256": r.get("prompt_sha256"),
             "params": {}, "raw_output": r.get("raw_output", ""),
             "raw_sha256": r.get("raw_sha256", "")} for r in runs],
        "audit_chain": {
            "from_id": audit_rows[0]["id"] if audit_rows else None,
            "to_id": audit_rows[-1]["id"] if audit_rows else None,
            "head_hash": audit_rows[-1].get("row_hash") if audit_rows else None,
            "anchor_tsr": None,  # Day-7 TSA: null until a real token is issued
        },
    }
    signed_flag, sign_warning = False, None
    if sign:
        from .signing import build_and_sign, signing_configured
        if not signing_configured():
            sign_warning = "signing skipped: FINSPY_SIGN_CERT/FINSPY_SIGN_KEY missing"
        else:
            try:
                sout = build_and_sign(tenant_id, None, None)
                add_file(Path(sout["file_key"]), Path(sout["file_key"]).name,
                         "report", derived_from="db-summary+pades")
                signed_flag = True
                if sout["signed"].get("warning"):
                    sign_warning = sout["signed"]["warning"]
            except Exception as e:
                sign_warning = f"signing failed: {e}".strip()[:300]

    manifest_path = stage / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    (stage / "manifest.sha256").write_text(_sha256_file(manifest_path))

    zip_path = REPORTS_PATH / f"evidence-pack-{tenant_id}-{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(stage).as_posix())
    return {"file_key": str(zip_path), "sha256": _sha256_file(zip_path),
            "report_id": report_id, "manifest": manifest,
            "file_count": len(files), "signed": signed_flag,
            "sign_warning": sign_warning}
