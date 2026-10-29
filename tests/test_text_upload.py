"""
Text uploads (CSV/TXT/OFX) must extract like PDFs: the intake accepts them,
so the worker needs a text reader. Live gap: a CSV hit the PDF-only
pmupdf/pdfplumber path and died with RuntimeError (0 rows, exception).
"""

from pathlib import Path

from apps.worker.parsers.extractor import extract_text_lines, extract_document
from apps.worker.parsers.generic import parse_generic_lines

CSV = """date,desc,amount,balance
2026-08-01,OPENING FILLER,0.00,10000.00
2026-08-02,SARS FUEL,-298.94,9701.06
2026-08-03,UBER TRIP,-37.36,9663.70
2026-08-04,SALARY ACME,5000.00,14663.70
2026-08-05,WOOLWORTHS FOOD,-412.10,14251.60
"""


def _csv(tmp_path):
    p = tmp_path / "stmt.csv"
    p.write_text(CSV, encoding="utf-8")
    return p


def test_text_reader_pages_shape(tmp_path):
    p = _csv(tmp_path)
    pages = extract_text_lines(p)
    assert len(pages) == 1
    lines = pages[0]["lines"]
    assert len(lines) == 6  # header + 5 rows, no blanks dropped wrongly
    assert lines[0]["line_id"] == "L001"
    assert "SARS" in lines[2]["text"]
    assert all("text_hash" in ln for ln in lines)


def test_generic_chains_csv_lines(tmp_path):
    p = _csv(tmp_path)
    pages = extract_text_lines(p)
    result = parse_generic_lines(pages)
    assert result is not None
    assert len(result.rows) >= 3
    by_desc = {r.description: r for r in result.rows}
    assert by_desc["SARS FUEL"].direction == "debit"
    assert by_desc["SALARY ACME"].direction == "credit"


def test_extract_document_dispatches_csv(tmp_path, monkeypatch):
    p = _csv(tmp_path)
    monkeypatch.setattr(
        "apps.worker.parsers.extractor.llm_fallback",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("LLM must not run when generic chains")),
    )
    result = extract_document(Path(p), bank_hint="FNB")
    assert len(result.rows) >= 3
