"""68-vs-61 recall: pair-pick, order-free chaining, fp+balance.

User row contract: a date starts a row; row = signed amount + total;
amounts sum-check against balances; dates non-decreasing top-bottom.
Bugs (all reproduced on statement PII-kept-out): B1 lossy fp dedup
(same-day R110 repeats eaten), B2 3-token positional misread
([50.00, 258.86Cr, 4.40] -> amount 258.86 / balance 4.40), B3
ref+amount fusion ("56 300.00Cr" -> R56,300), B4 exact sequential
chaining drops rows at line-order jumps, B5 lowercase dr/cr rejected.
"""
import hashlib
import uuid

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.worker.parsers.base import (
    ExtractionResult, ExtractedRow, fingerprint_txn, parse_sa_amount)
from apps.worker.parsers.extractor import persist_to_db, deterministic_parse
from apps.worker.parsers.generic import _money_tokens, parse_generic_lines
from apps.worker.parsers.registry import get_bank_config
from apps.worker.reconcile import run_reconciliation_gate


def _pages(*texts):
    return [{"page_no": 1, "height": 800,
             "lines": [{"line_id": f"L{i + 1:03d}", "text": t,
                        "bbox": [0, i * 10, 500, i * 10 + 8]}
                       for i, t in enumerate(texts)]}]


PERIOD = "Statement Period : 1 July 2023 to 1 August 2023"


def test_g1a_three_token_line_picks_chaining_pair():
    pages = _pages(
        PERIOD,
        "Opening Balance 208.86",
        "26 Jul SHOP A 50.00 258.86Cr 4.40",
        "26 Jul SHOP B 25.00 233.86",
        "26 Jul SHOP C 10.00 223.86",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    got = [(r.amount_minor, r.direction, r.balance_after_minor)
           for r in result.rows]
    assert got == [(5000, "credit", 25886), (2500, "debit", 23386),
                   (1000, "debit", 22386)]


def test_g1b_ref_amount_fusion_splits_when_balance_disproves():
    pages = _pages(
        PERIOD,
        "Opening Balance 133.86",
        "28 Jul SHOP C 56 300.00Cr 433.86Cr",
        "28 Jul SHOP D 33.86 400.00",
        "28 Jul SHOP E 50.00 350.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert result.rows[0].amount_minor == 30000
    assert result.rows[0].direction == "credit"


def test_g2a_jump_row_chains_out_of_line_order():
    pages = _pages(
        PERIOD,
        "Opening Balance 1000.00",
        "01 Jul SHOP A 100.00 900.00",
        "03 Jul SHOP B 200.00 650.00",
        "02 Jul SHOP J 50.00 850.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert [r.date for r in result.rows] == [
        "2023-07-01", "2023-07-02", "2023-07-03"]
    assert [u["reason"] for u in result.unaccounted_lines
            if u["reason"] == "unchained"] == []


def test_g2b_date_break_refused_from_chain_and_flagged():
    pages = _pages(
        PERIOD,
        "Opening Balance 1000.00",
        "01 Jul SHOP A 100.00 900.00",
        "02 Jul SHOP B 100.00 800.00",
        "03 Jul SHOP C 100.00 700.00",
        "01 Jul TRAP 100.00 600.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert len(result.rows) == 3
    assert "L006" in [u["line_id"] for u in result.unaccounted_lines
                      if u["reason"] == "unchained"]
    assert any("Date order break" in w for w in result.warnings)


def test_g3a_fingerprint_includes_balance():
    assert fingerprint_txn("2023-07-24", 11000, "DEBIT ORDER", 88386) != \
        fingerprint_txn("2023-07-24", 11000, "DEBIT ORDER", 77386)
    assert fingerprint_txn("2023-07-24", 11000, "DEBIT ORDER", 88386) == \
        fingerprint_txn("2023-07-24", 11000, "  debit order  ", 88386)


def _seed_doc(tenant, doc, run):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256,"
               " size_bytes, storage_key, status) VALUES (?,?,?,?,?,?)",
               (doc, tenant, f"sha-{doc}", 10, f"k-{doc}", "queued"))
    db.execute("INSERT INTO extraction_runs (id, document_id) VALUES (?,?)",
               (run, doc))
    db.commit()


def _result(rows, account="111"):
    return ExtractionResult(
        statement={"bank": "GENERIC", "account_number": account,
                   "period_start": None, "period_end": None,
                   "currency": "ZAR", "opening_balance": None,
                   "closing_balance": None},
        rows=rows, unaccounted_lines=[], warnings=[],
        opening_balance_minor=None, closing_balance_minor=None)


def _rep_row(line_id, balance):
    return ExtractedRow(
        line_ids=[line_id], date="2023-07-24",
        description="DEBIT ORDER", amount_minor=11000,
        direction="debit", balance_after_minor=balance,
        source_quote=f"2023-07-24 DEBIT ORDER {balance}")


def _txn_count(tenant):
    db = get_db()
    cur = db.execute("SELECT COUNT(*) AS c FROM transactions WHERE tenant_id=?",
                     (tenant,))
    row = cur.fetchone()
    return row["c"] if isinstance(row, dict) else row[0]


def test_g3bc_same_day_repeats_persist_but_reextract_dedups():
    init_db()
    tag = uuid.uuid4().hex[:6]
    tenant = f"chain-{tag}"
    doc, run1, run2 = f"doc-{tag}", f"run-1-{tag}", f"run-2-{tag}"
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256,"
               " size_bytes, storage_key, status) VALUES (?,?,?,?,?,?)",
               (doc, tenant, f"sha-{doc}", 10, f"k-{doc}", "queued"))
    for run in (run1, run2):
        db.execute("INSERT INTO extraction_runs (id, document_id)"
                   " VALUES (?,?)", (run, doc))
    db.commit()
    try:
        rows = [_rep_row("L073", 88386), _rep_row("L074", 77386)]
        out1 = persist_to_db(_result(rows), doc, tenant, run1)
        assert (out1["persisted"], out1["skipped_existing"]) == (2, 0)
        assert _txn_count(tenant) == 2
        out2 = persist_to_db(_result(rows), doc, tenant, run2)
        assert (out2["persisted"], out2["skipped_existing"]) == (0, 2)
        assert _txn_count(tenant) == 2
    finally:
        cleanup_tenant(tenant)


def test_g3d_migration_recomputes_fingerprints_idempotently():
    from apps.api.db import migrate_fingerprints_add_balance
    init_db()
    tag = uuid.uuid4().hex[:6]
    tenant = f"mig-{tag}"
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    old = hashlib.sha256("2023-07-24|11000|debit order".encode()).hexdigest()
    db.execute("INSERT INTO transactions (id, tenant_id, txn_date,"
               " description_raw, amount_minor, direction,"
               " balance_after_minor, fingerprint_sha256, status)"
               " VALUES (?,?,?,?,?,?,?,?,?)",
               (f"txn-{tag}", tenant, "2023-07-24", "DEBIT ORDER", 11000,
                "debit", 88386, old, "confirmed"))
    db.commit()
    try:
        db.execute("DELETE FROM schema_migrations WHERE name='fp_add_balance'")
        db.commit()
    except Exception:
        pass  # first run: table/marker absent, migration creates it
    try:
        out = migrate_fingerprints_add_balance()
        assert out["migrated"] >= 1
        cur = db.execute("SELECT fingerprint_sha256 AS fp FROM transactions"
                         " WHERE id=?", (f"txn-{tag}",))
        row = cur.fetchone()
        fp = row["fp"] if isinstance(row, dict) else row[0]
        assert fp == fingerprint_txn("2023-07-24", 11000, "DEBIT ORDER",
                                     88386)
        again = migrate_fingerprints_add_balance()
        assert again["migrated"] == 0
    finally:
        cleanup_tenant(tenant)


def test_g4_lowercase_suffix_parses():
    assert parse_sa_amount("450dr") == -45000
    assert parse_sa_amount("3,193.31cr") == 319331
    assert parse_sa_amount("450DR") == -45000
    assert [t for t, _, _ in _money_tokens("SHOP 1,234.56dr BAL")] != []


def _brow(line_id, date, amount, direction, balance):
    return ExtractedRow(
        line_ids=[line_id], date=date, description="X",
        amount_minor=amount, direction=direction,
        balance_after_minor=balance, source_quote="X")


def test_g5a_date_order_check():
    from apps.worker.reconcile import check_date_order
    ok, breaks = check_date_order([
        _brow("L001", "2023-07-01", 100, "debit", 900),
        _brow("L002", "2023-07-01", 100, "debit", 800),
        _brow("L003", "2023-07-02", 100, "debit", 700),
    ])
    assert (ok, breaks) == (True, [])
    ok, breaks = check_date_order([
        _brow("L001", "2023-07-05", 100, "debit", 900),
        _brow("L002", "2023-07-01", 100, "debit", 800),
    ])
    assert ok is False
    assert "L002" in str(breaks)


def test_g6a_overdraft_stretch_chains_signed_and_gate_passes():
    pages = _pages(
        PERIOD,
        "Opening Balance 100.00",
        "05 Jul FNB App Payment To Abi Sam 150.00 50.00",
        "05 Jul FNB App Prepaid Airtime 0618 30.00 80.00",
        "06 Jul FNB App Payment From Donor 200.00Cr 120.00Cr",
        "06 Jul SHOP D 20.00 100.00",
        "Closing Balance 100.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    got = [(r.amount_minor, r.direction, r.balance_after_minor)
           for r in result.rows]
    assert got == [(15000, "debit", -5000), (3000, "debit", -8000),
                   (20000, "credit", 12000), (2000, "debit", 10000)]
    gate = run_reconciliation_gate(result.opening_balance_minor,
                                   result.closing_balance_minor, result.rows)
    assert gate["overall_pass"] is True


def test_g6b_resign_blocked_on_hint_conflict():
    pages = _pages(
        PERIOD,
        "Opening Balance 100.00",
        "05 Jul FNB App Payment From Abi Sam 150.00 50.00",
        "05 Jul SHOP B 30.00 80.00",
        "06 Jul SHOP C 10.00 70.00",
        "06 Jul SHOP D 20.00 50.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert "L003" in [u["line_id"] for u in result.unaccounted_lines
                      if u["reason"] == "unchained"]
    assert any("refused by direction hint" in w for w in result.warnings)


def test_g6c_plain_link_stands_but_conflict_warns():
    pages = _pages(
        PERIOD,
        "Opening Balance 100.00",
        "05 Jul FNB App Payment To Abi Sam 50.00 150.00",
        "05 Jul SHOP B 30.00 120.00",
        "06 Jul SHOP C 20.00 100.00",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert result.rows[0].direction == "credit"
    assert any("Direction hint conflict" in w and "L003" in w
               for w in result.warnings)


def test_g5b_gate_reports_date_order_without_failing():
    rows = [
        _brow("L001", "2023-07-05", 10000, "debit", 90000),
        _brow("L002", "2023-07-01", 10000, "debit", 80000),
        _brow("L003", "2023-07-06", 10000, "debit", 70000),
    ]
    gate = run_reconciliation_gate(100000, 70000, rows)
    assert gate["date_order"]["pass"] is False
    assert gate["overall_pass"] is True


# G7: FNB bare-Dr rule (user mandate 2026-11-02). No +/- on FNB;
# `Cr` = credit (+), bare = debit (Dr never shown). FNB-scoped:
# other banks keep plain positives.

def _g7a_pages():
    return _pages(
        PERIOD,
        "Opening Balance 1 000.00",
        "05 Jul SHOP A 100.00 900.00",
        "05 Jul SHOP B 50.00 850.00",
        "06 Jul SHOP C 200.00 1 050.00",
        "Closing Balance 1 050.00",
    )


def test_g7a_fnb_bare_balances_chain_as_dr():
    result = parse_generic_lines(_g7a_pages(), bank="FNB")
    assert result is not None
    assert result.opening_balance_minor == -100000
    assert result.closing_balance_minor == -105000
    got = [(r.amount_minor, r.direction, r.balance_after_minor)
           for r in result.rows]
    assert got == [(10000, "credit", -90000),
                   (5000, "credit", -85000),
                   (20000, "debit", -105000)]
    gate = run_reconciliation_gate(result.opening_balance_minor,
                                   result.closing_balance_minor, result.rows)
    assert gate["overall_pass"] is True


def test_g7a2_fnb_bare_head_seed_without_opening():
    pages = _pages(
        PERIOD,
        "05 Jul SHOP A 100.00 900.00",
        "05 Jul SHOP B 50.00 850.00",
        "06 Jul SHOP C 200.00 1 050.00",
    )
    result = parse_generic_lines(pages, bank="FNB", min_rows=1)
    assert result is not None
    got = [(r.amount_minor, r.direction, r.balance_after_minor)
           for r in result.rows]
    assert got == [(5000, "credit", -85000),
                   (20000, "debit", -105000)]
    assert "L002" in [u["line_id"] for u in result.unaccounted_lines
                      if u["reason"] == "unchained"]


def _g7b_legacy_pages():
    return _pages(
        PERIOD,
        "Opening Balance 1 000.00",
        "05 Jul SHOP A 100.00 900.00",
        "05 Jul SHOP B 50.00 850.00",
        "06 Jul SHOP C 200.00 650.00",
        "Closing Balance 650.00",
    )


def test_g7b_bare_stays_positive_off_fnb():
    want = [(10000, "debit", 90000),
            (5000, "debit", 85000),
            (20000, "debit", 65000)]
    for bank in (None, "STDB"):
        result = parse_generic_lines(_g7b_legacy_pages(), bank=bank)
        assert result is not None
        got = [(r.amount_minor, r.direction, r.balance_after_minor)
               for r in result.rows]
        assert got == want, bank
        gate = run_reconciliation_gate(
            result.opening_balance_minor, result.closing_balance_minor,
            result.rows)
        assert gate["overall_pass"] is True, bank


def test_g7c_detected_fnb_threads_rule_end_to_end():
    pages = _pages(
        "First National Bank Statement Account 62123456789",
        "Opening Balance: R1 000,00",
        "25 Oct 2025 SHOP A 100.00 900.00",
        "26 Oct 2025 SHOP B 50.00 850.00",
        "27 Oct 2025 SHOP C 200.00 1 050.00",
        "Closing Balance: R1 050,00",
    )
    result = deterministic_parse(pages)
    assert result is not None
    assert result.statement["bank"] == "GENERIC"
    assert [r.direction for r in result.rows] == ["credit", "credit",
                                                  "debit"]
    assert [r.amount_minor for r in result.rows] == [10000, 5000, 20000]


def test_g7d_config_declares_fnb_bare_dr_only():
    fnb = (get_bank_config("FNB") or {}).get("deviations", {})
    assert fnb.get("bare_means_dr") is True
    for bank in ("STDB", "ABSA", "Nedbank", "Capitec"):
        dev = (get_bank_config(bank) or {}).get("deviations", {})
        assert not dev.get("bare_means_dr"), bank
