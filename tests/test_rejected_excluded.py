"""
Rejected (voided/fiction) rows must never pollute products: dashboard, spy,
excel, auditor-csv, powerbi, signed-pdf and chat totals all exclude
status='rejected'. Forensic bundles (evidence pack, POPIA) intentionally keep
everything and are NOT covered here.

Also: auditor-csv must emit one row per transaction even when several
classification revisions exist (latest decision wins).
"""

import csv
import uuid

from apps.api.auth import create_user
from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.main import dashboard_summary, spy_run
from apps.api.reports import (generate_auditor_csv, generate_excel_workbook,
                              generate_powerbi_pack)
from apps.api.signing import build_report_pdf
from apps.worker.spy.chat import load_txns


def _user(prefix="rejexcl"):
    """Direct user + tenant (no TestClient: sandboxed shells forbid the
    socketpair TestClient needs - WinError 10013)."""
    init_db()
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    uid = create_user(email, "pass1234", "T", tenant)
    return uid, tenant


def _txn(tenant, date, amount, direction, desc, status="confirmed"):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
        " amount_minor, direction, fingerprint_sha256, status)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (txn_id, tenant, date, desc, amount,
         direction, f"fp-{uuid.uuid4().hex[:8]}", status),
    )
    db.commit()
    return txn_id


def test_dashboard_excludes_rejected():
    uid, tenant = _user()
    try:
        _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION MONSTER",
             status="rejected")
        body = dashboard_summary(None, None, None, None, uid)
        assert body["inflow_minor"] == 10000, body
        assert body["totals"]["txn_count"] == 1, body["totals"]
    finally:
        cleanup_tenant(tenant)


def test_spy_excludes_rejected():
    uid, tenant = _user()
    try:
        _txn(tenant, "2026-10-05", 5000, "debit", "SHOP", status="rejected")
        body = spy_run(uid)
        assert body["txn_count"] == 0, body
    finally:
        cleanup_tenant(tenant)


def test_auditor_csv_excludes_rejected_and_dedups_decisions():
    init_db()
    tenant = f"rejcsv-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        good = _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        bad = _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION",
                   status="rejected")
        for i, nature in enumerate(("private", "business")):
            db.execute(
                "INSERT INTO classifications (id, tenant_id, transaction_id,"
                " nature, business_pct, category_id, rationale, decided_by,"
                " source, decided_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"cls-{uuid.uuid4().hex[:6]}", tenant, good, nature, 100,
                 "4010", "r", "t", "test", f"2026-10-0{7 + i}T00:00:00"))
        db.commit()
        out = generate_auditor_csv(tenant)
        with open(out["file_key"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ids = [r["id"] for r in rows]
        assert bad not in ids, ids
        assert ids.count(good) == 1, ids
    finally:
        cleanup_tenant(tenant)


def test_excel_excludes_rejected():
    import openpyxl

    init_db()
    tenant = f"rejxl-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        good = _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        bad = _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION",
                   status="rejected")
        out = generate_excel_workbook(tenant)
        wb = openpyxl.load_workbook(out["file_key"])
        ws = wb["Transactions"]
        ids = [row[0] for row in ws.iter_rows(min_row=2, values_only=True)]
        assert bad not in ids, ids
        assert good in ids, ids
    finally:
        cleanup_tenant(tenant)


def test_powerbi_excludes_rejected():
    init_db()
    tenant = f"rejpbi-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        bad = _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION",
                   status="rejected")
        pack = generate_powerbi_pack(tenant)
        assert pack["counts"]["fact_transactions"] == 1, pack["counts"]
        with open(pack["csv_keys"][0], newline="",
                  encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ids = [r["id"] for r in rows]
        assert bad not in ids, ids
    finally:
        cleanup_tenant(tenant)


def test_signed_pdf_totals_exclude_rejected(tmp_path):
    init_db()
    tenant = f"rejpdf-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION",
             status="rejected")
        out = build_report_pdf(tenant, None, None, tmp_path / "s.pdf", None)
        assert out["txn_count"] == 1, out
    finally:
        cleanup_tenant(tenant)


def test_chat_load_excludes_rejected():
    init_db()
    tenant = f"rejchat-{uuid.uuid4().hex[:6]}"
    try:
        db = get_db()
        db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
                   (tenant, "t"))
        _txn(tenant, "2026-10-05", 10000, "credit", "SALARY")
        bad = _txn(tenant, "2026-10-06", 9788230000, "credit", "FICTION",
                   status="rejected")
        ids = [t["id"] for t in load_txns(tenant)]
        assert bad not in ids, ids
        assert len(ids) == 1, ids
    finally:
        cleanup_tenant(tenant)
