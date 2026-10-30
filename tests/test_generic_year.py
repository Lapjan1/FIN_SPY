"""Generic year inference: SA statements (FNB-class) print day-month
rows while the year lives on the Statement Period/Date line. Without
inference the whole statement scores zero candidates."""

from apps.worker.parsers.generic import (
    normalize_generic_date, parse_generic_lines)


def _pages(*texts):
    return [{"page_no": 1,
             "lines": [{"line_id": f"L{i + 1:03d}", "text": t}
                       for i, t in enumerate(texts)]}]


def test_yearless_row_uses_period_year():
    pages = _pages(
        "Statement Period : 1 July 2023 to 1 August 2023",
        "04 Jul SHOP A 206.69 3,193.31Cr",
        "05 Jul SHOP B 184.50 3,008.81Cr",
        "06 Jul SHOP C 200.00 2,808.81Cr",
        "07 Jul SHOP D 785.00 2,023.81Cr",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    # Chaining needs a previous balance, so the first row drops.
    assert [r.date for r in result.rows] == [
        "2023-07-05", "2023-07-06", "2023-07-07"]


def test_no_period_no_yearless_rows():
    pages = _pages(
        "04 Jul SHOP A 206.69 3,193.31Cr",
        "05 Jul SHOP B 184.50 3,008.81Cr",
        "06 Jul SHOP C 200.00 2,808.81Cr",
    )
    assert parse_generic_lines(pages) is None


def test_december_rollover():
    pages = _pages(
        "Statement Period : 15 December 2023 to 15 January 2024",
        "28 Dec SHOP A 100.00 9,900.00Cr",
        "29 Dec SHOP B 100.00 9,800.00Cr",
        "30 Dec SHOP C 100.00 9,700.00Cr",
        "05 Jan SHOP D 100.00 9,600.00Cr",
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert [r.date for r in result.rows] == [
        "2023-12-29", "2023-12-30", "2024-01-05"]


def test_year_bearing_still_wins():
    assert (normalize_generic_date("25 Oct 2026 SHOP 10.00 20.00")
            == "2026-10-25")
