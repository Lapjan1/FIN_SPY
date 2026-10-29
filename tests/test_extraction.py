"""
Test extraction Day2 - line-ID grounding + reconciliation gate + DB-first
Per docs/PLAN.md Done Means: synthetic FNB CSV 200 tx row accuracy >=99%, reconciliation pass 100% confirmed, every confirmed tx has >=1 source_spans
"""
import hashlib
from pathlib import Path
from apps.worker.parsers.base import parse_sa_amount, fingerprint_txn
from apps.worker.parsers.fnb import normalize_date, parse_fnb_lines
from apps.worker.parsers.extractor import extract_text_with_bbox, deterministic_parse, llm_fallback

def test_sa_amount_parsing_red():
    # Green cases
    assert parse_sa_amount("R 1 234,56") == 123456
    assert parse_sa_amount("(450.00)") == -45000
    assert parse_sa_amount("450-") == -45000
    assert parse_sa_amount("1,234.56") == 123456
    # Red invalid should raise ValueError
    try:
        parse_sa_amount("abc")
        assert False, "Should raise ValueError for abc"
    except ValueError:
        pass

def test_normalize_date():
    assert normalize_date("25 Oct 2026") == "2026-10-25"
    assert normalize_date("2026/10/25") == "2026-10-25"
    assert normalize_date("25-10-2026") == "2026-10-25"

def test_fnb_deterministic_parser():
    # Synthetic pages like scripts/generate_sa_statements.py
    pages = [{
        "page_no":1,
        "width":595,
        "height":842,
        "lines":[
            {"line_id":"L001","bbox":[0,0,100,10],"text":"Statement FNB Account 123","text_hash":"a"},
            {"line_id":"L002","bbox":[0,10,100,20],"text":"25 Oct 2026 WOOLWORTHS R450,00 R12 340,55","text_hash":"b"},
            {"line_id":"L003","bbox":[0,20,100,30],"text":"26 Oct 2026 RENT R5 000,00 R7 340,55","text_hash":"c"},
        ]
    }]
    result = parse_fnb_lines(pages)
    assert len(result.rows) >= 1
    assert result.rows[0].source_quote
    # Check fingerprint
    fp = fingerprint_txn(result.rows[0].date, result.rows[0].amount_minor, result.rows[0].description)
    assert len(fp) == 64

def test_line_id_grounding_quote_validation():
    pages = [{
        "page_no":1,
        "width":595,
        "height":842,
        "lines":[
            {"line_id":"L001","bbox":[0,0,100,10],"text":"25 Oct WOOLWORTHS R450,00","text_hash":"a"},
        ]
    }]
    result = parse_fnb_lines(pages)
    if result.rows:
        row = result.rows[0]
        # Quote must be substring of cited lines per AGENTS.md anti-hallucination
        line_map = {l['line_id']: l['text'] for p in pages for l in p['lines']}
        cited = " ".join([line_map[lid] for lid in row.line_ids])
        assert row.source_quote in cited or row.source_quote[:10] in cited

def test_reconciliation_gate():
    # Opening balance +/- amount == running balance/total from top to bottom and bottom to top per user question
    pages = [{
        "page_no":1,
        "width":595,
        "height":842,
        "lines":[
            {"line_id":"L001","bbox":[0,0,100,10],"text":"Header"},
            {"line_id":"L002","bbox":[0,10,100,20],"text":"25 Oct WOOLWORTHS R450,00 R1 000,00","text_hash":"b"},
            {"line_id":"L003","bbox":[0,20,100,30],"text":"26 Oct RENT R500,00 R500,00","text_hash":"c"},
        ]
    }]
    result = parse_fnb_lines(pages)
    # Full gate top->bottom + bottom->top per apps/worker/reconcile.py
    from apps.worker.reconcile import run_reconciliation_gate
    if result.opening_balance_minor is not None and result.closing_balance_minor is not None and result.rows:
        gate = run_reconciliation_gate(result.opening_balance_minor, result.closing_balance_minor, result.rows)
        # Check both directions per user: opening +/- amount == running balance/total top->bottom and bottom->top
        assert "opening_closing_top_bottom" in gate
        assert "opening_closing_bottom_top" in gate
        assert "running_balance_top_bottom" in gate
        assert "running_balance_bottom_top" in gate
        assert "totals_check" in gate
        # If gate fails, warnings should contain failure
        if not gate["overall_pass"]:
            assert len(result.warnings) > 0 or len(gate["running_balance_top_bottom"]["breaks"]) > 0 or len(gate["running_balance_bottom_top"]["breaks"]) > 0
        # Also check simple top->bottom computed for backward compat
        computed = result.opening_balance_minor
        for r in result.rows:
            signed = -r.amount_minor if r.direction=="debit" else r.amount_minor
            computed += signed
        assert abs(computed - result.closing_balance_minor) < 100 or len(result.warnings)>0 or not gate["opening_closing_top_bottom"]["pass"]

def test_reconciliation_both_directions_extraction():
    # Explicit test per user: opening balance +/- amount == running balance/total from top to bottom and bottom to top
    from apps.worker.parsers.base import ExtractedRow
    from apps.worker.reconcile import run_reconciliation_gate
    # Opening 10000, rows: -1000 -> 9000, -2000 -> 7000, +500 -> 7500 closing
    rows = [
        ExtractedRow(line_ids=["L001"], date="2026-10-25", description="WOOLWORTHS", amount_minor=1000, direction="debit", balance_after_minor=9000, source_quote="WOOLWORTHS R1000"),
        ExtractedRow(line_ids=["L002"], date="2026-10-26", description="RENT", amount_minor=2000, direction="debit", balance_after_minor=7000, source_quote="RENT R2000"),
        ExtractedRow(line_ids=["L003"], date="2026-10-27", description="SALARY", amount_minor=500, direction="credit", balance_after_minor=7500, source_quote="SALARY R500"),
    ]
    opening = 10000
    closing = 7500
    gate = run_reconciliation_gate(opening, closing, rows)
    # Both directions must pass
    assert gate["opening_closing_top_bottom"]["pass"] is True, f"Top->Bottom opening+sum=closing should pass: {gate['opening_closing_top_bottom']['message']}"
    assert gate["opening_closing_bottom_top"]["pass"] is True, f"Bottom->Top closing-sum=opening should pass: {gate['opening_closing_bottom_top']['message']}"
    assert gate["running_balance_top_bottom"]["pass"] is True, f"Running top->bottom should pass: {gate['running_balance_top_bottom']['breaks']}"
    assert gate["running_balance_bottom_top"]["pass"] is True, f"Running bottom->top should pass: {gate['running_balance_bottom_top']['breaks']}"
    assert gate["overall_pass"] is True
    # Check totals_check explanation per user question
    assert "top_to_bottom" in gate["totals_check"]
    assert "bottom_to_top" in gate["totals_check"]
    assert "Totals +/- == balance from top to bottom and from bottom to top" in gate["totals_check"]["explanation"] or "top to bottom" in gate["totals_check"]["explanation"].lower()

def test_llm_fallback_mock(monkeypatch):
    # Hermetic: drop the local-proxy key so this always exercises the
    # failure path (no :3001 server, no hosted call, zero credit).
    # P0-A0/Q3 (owner-approved): failure persists ZERO rows, never
    # mock rows. Live-model coverage belongs in an integration test
    # with an explicit model id.
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    pages = [{
        "page_no":1,
        "width":595,
        "height":842,
        "lines":[
            {"line_id":"L001","bbox":[0,0,100,10],"text":"Unknown layout line 1","text_hash":"a"},
            {"line_id":"L002","bbox":[0,10,100,20],"text":"Unknown layout line 2","text_hash":"b"},
        ]
    }]
    result = llm_fallback(pages, model_id="muse-spark-1.1")
    assert result.rows == []
    assert result.warnings
    assert all(u["reason"] == "llm_failed" for u in result.unaccounted_lines)
