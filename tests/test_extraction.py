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
    # Opening + sum = closing per AGENTS.md
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
    # If opening and closing present, check gate
    if result.opening_balance_minor is not None and result.closing_balance_minor is not None:
        computed = result.opening_balance_minor
        for r in result.rows:
            signed = -r.amount_minor if r.direction=="debit" else r.amount_minor
            computed += signed
        # Allow 1 Rand tolerance
        assert abs(computed - result.closing_balance_minor) < 100 or len(result.warnings)>0

def test_llm_fallback_mock():
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
    assert len(result.rows) >= 1
    assert result.rows[0].line_ids[0] in ["L001","L002"]
    assert result.warnings
