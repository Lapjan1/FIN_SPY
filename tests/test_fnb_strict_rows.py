"""FNB strict row evidence: date digits and lone numbers must never become rows.

Live 2025-05 FNB file emitted fiction rows from a dateline header (day/year
digits parsed as amount/balance) and from a one-money rate paragraph. A bank
row needs date + amount + balance; anything less is noise for the generic
engine or human review. All fixtures synthetic, shaped like the live audit.
"""
from apps.worker.parsers.fnb import parse_fnb_lines


def _pages(*texts):
    return [{
        "page_no": 1, "width": 595, "height": 842,
        "lines": [
            {"line_id": f"L{i + 1:03d}", "bbox": [0, 0, 100, 10],
             "text": t, "text_hash": "x"}
            for i, t in enumerate(texts)
        ],
    }]


def test_dateline_header_with_no_money_is_never_a_row():
    # Shape of live L059: words, mid-line date, words, zero money tokens.
    # The loose matcher ate the day/year digits as amount/balance.
    pages = _pages("SUMMARY OF ACCOUNTSHELD 15 May 2025 END OF HEADER BLOCK NOW")
    result = parse_fnb_lines(pages)
    assert result.rows == []
    assert {u["line_id"] for u in result.unaccounted_lines} == {"L001"}


def test_single_money_prose_line_is_never_a_row():
    # Shape of live L119: date + one bare money token in a sentence.
    pages = _pages(
        "Interest rate review 01 May 2025 prime lending rate 11.75 percent per annum fixed")
    result = parse_fnb_lines(pages)
    assert result.rows == []
    assert {u["line_id"] for u in result.unaccounted_lines} == {"L001"}


def test_valid_two_token_row_survives():
    pages = _pages("25 Oct 2026 WOOLWORTHS R450,00- R11 890,55")
    result = parse_fnb_lines(pages)
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.amount_minor == 45000
    assert row.direction == "debit"
    assert row.balance_after_minor == 1189055
    assert row.date == "2026-10-25"


def test_opening_balance_ignores_trailing_year():
    # Same loose matcher flaw in balance detection: the year must not win.
    pages = _pages("Opening Balance R12 340,55 as at 31 May 2025")
    result = parse_fnb_lines(pages)
    assert result.opening_balance_minor == 1234055
