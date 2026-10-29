"""
Bank-agnostic generic extractor (P0-A0): SA-wide date/amount/balance line
patterns + running-balance chaining, routed between the bank parsers and
the LLM last resort. Fixture is hand-written synthetic ("Ubuntu Bank") with
hand-computed running balances - every field asserted, nothing generated.
"""

import pytest

from apps.worker.parsers.extractor import deterministic_parse, llm_fallback

LINES = [
    "Ubuntu Bank Statement Account 987654321",
    "Period: Oct 2026",
    "Opening Balance: R5 000,00",
    "Date Description Amount Balance",
    "2026-10-01 SHOPRITE CHECKERS R100,00- R4 900,00",
    "2026-10-02 PICK N PAY (250.00) 4,650.00",
    "2026-10-03 SALARY ACME R1 000,00+ R5 650,00",
    "2026-10-04 UBER TRIP 75.50 5,574.50",
    "2026-10-05 NETFLIX 200,00 5374,50",
    "2026-10-06 INTEREST R300.00Cr R5 674,50",
    "2026-10-07 WOOLWORTHS FOOD (50.25) 5,624.25",
    "2026-10-08 RENT LANDLORD R1 000,00- R4 624,25",
    "2026-10-09 APP PAYMENT 24.25 4600.00",
    "2026-10-10 FREELANCE PAY R500,00+ R5 100,00",
    "2026-10-11 CLOTHING MRP R99,99- R5 000,01",
    "2026-10-12 BANK CHARGE (0.01) 5,000.00",
    "2026-10-13 CAR PAYMENT R1 500,00- R3 500,00",
    "2026-10-14 BONUS PAYOUT 2500,00+ R6 000,00",
    "2026-10-15 BOND REPAYMENT (6,000.00) 0.00",
    "2026-10-16 CASH DEPOSIT R100,00+ R100,00",
    "2026-10-17 COFFEE SHOP 33.33 66.67",
    "2026-10-18 PARKING (66.67) (0.00)",
    "2026-10-19 DIVIDEND R1 234,56+ R1 234,56",
    "2026-10-20 GROCERIES SPAR 234,56- R1 000,00",
    "Page 1 of 1",
    "Closing Balance: R1 000,00",
]

# (date, description, amount_minor, direction, balance_minor)
EXPECTED = [
    ("2026-10-01", "SHOPRITE CHECKERS", 10000, "debit", 490000),
    ("2026-10-02", "PICK N PAY", 25000, "debit", 465000),
    ("2026-10-03", "SALARY ACME", 100000, "credit", 565000),
    ("2026-10-04", "UBER TRIP", 7550, "debit", 557450),
    ("2026-10-05", "NETFLIX", 20000, "debit", 537450),
    ("2026-10-06", "INTEREST", 30000, "credit", 567450),
    ("2026-10-07", "WOOLWORTHS FOOD", 5025, "debit", 562425),
    ("2026-10-08", "RENT LANDLORD", 100000, "debit", 462425),
    ("2026-10-09", "APP PAYMENT", 2425, "debit", 460000),
    ("2026-10-10", "FREELANCE PAY", 50000, "credit", 510000),
    ("2026-10-11", "CLOTHING MRP", 9999, "debit", 500001),
    ("2026-10-12", "BANK CHARGE", 1, "debit", 500000),
    ("2026-10-13", "CAR PAYMENT", 150000, "debit", 350000),
    ("2026-10-14", "BONUS PAYOUT", 250000, "credit", 600000),
    ("2026-10-15", "BOND REPAYMENT", 600000, "debit", 0),
    ("2026-10-16", "CASH DEPOSIT", 10000, "credit", 10000),
    ("2026-10-17", "COFFEE SHOP", 3333, "debit", 6667),
    ("2026-10-18", "PARKING", 6667, "debit", 0),
    ("2026-10-19", "DIVIDEND", 123456, "credit", 123456),
    ("2026-10-20", "GROCERIES SPAR", 23456, "debit", 100000),
]


def _pages():
    lines = [
        {"line_id": f"L{i + 1:03d}", "bbox": [0, 0, 100, 10],
         "text": t, "text_hash": f"h{i}"}
        for i, t in enumerate(LINES)
    ]
    return [{"page_no": 1, "width": 595, "height": 842, "lines": lines}]


def test_generic_engine_full_recall():
    from apps.worker.parsers.generic import parse_generic_lines

    result = parse_generic_lines(_pages())
    assert result is not None
    assert len(result.rows) == 20, f"recall {len(result.rows)}/20, need >=19"
    for row, (date, desc, amt, direction, bal) in zip(result.rows, EXPECTED):
        assert (row.date, row.description, row.amount_minor,
                row.direction, row.balance_after_minor) == (
                    date, desc, amt, direction, bal)
    assert result.opening_balance_minor == 500000
    assert result.closing_balance_minor == 100000
    assert result.statement.get("account_number") == "987654321"


def test_generic_sits_between_bank_parsers_and_llm(capsys):
    from apps.worker.parsers.generic import parse_generic_lines

    assert deterministic_parse(_pages(), "FNB") is None  # no bank parser
    result = parse_generic_lines(_pages())
    assert result is not None and len(result.rows) == 20
    out = capsys.readouterr().out
    assert "generic:" in out and "LLM fallback" not in out.split(
        "generic:")[-1].split("\n")[0]


def test_llm_failure_persists_zero_rows(monkeypatch):
    import apps.worker.parsers.extractor as ext

    def _boom(*a, **k):
        raise Exception("boom")

    monkeypatch.setattr(ext.MetaClient, "complete", _boom)
    result = llm_fallback(_pages(), tenant_id="t-generic-fail")
    assert result.rows == []
    assert any("fail" in w.lower() for w in result.warnings)


def test_generic_date_formats():
    from apps.worker.parsers.generic import normalize_generic_date

    assert normalize_generic_date("25 Oct 2026 xxx") == "2026-10-25"
    assert normalize_generic_date("2026/10/25 xxx") == "2026-10-25"
    assert normalize_generic_date("25/10/2026 xxx") == "2026-10-25"
    assert normalize_generic_date("2026-10-25 xxx") == "2026-10-25"
    assert normalize_generic_date("Oct 25, 2026 xxx") == "2026-10-25"
    assert normalize_generic_date("25-10-2026 xxx") == "2026-10-25"
    assert normalize_generic_date("no date here 12345") is None


def test_mystery_pdf_end_to_end_no_llm(tmp_path, monkeypatch):
    import apps.worker.parsers.extractor as ext

    pymupdf = pytest.importorskip("pymupdf")
    pdf = tmp_path / "ubuntu.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    y = 780
    for t in LINES:
        page.insert_text((40, y), t)
        y -= 22
    doc.save(str(pdf))
    doc.close()

    def _no_llm(*a, **k):
        raise AssertionError("LLM must not run when generic wins")

    monkeypatch.setattr(ext, "llm_fallback", _no_llm)
    result = ext.extract_document(pdf, bank_hint="FNB")
    assert len(result.rows) == 20
