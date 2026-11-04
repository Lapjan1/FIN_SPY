"""Currency handling: exponents + symbols on totals.

money.py is stdlib-only so this suite runs without the API env.
Wiring tests assert the consumers call it (menu-test precedent).
"""
from decimal import Decimal
from pathlib import Path

from apps.api import money


def test_exponent_defaults_two_zero_set_zero():
    assert money.exponent("ZAR") == 2
    assert money.exponent("USD") == 2
    assert money.exponent("JPY") == 0
    assert money.exponent("KRW") == 0
    assert money.exponent("XXQ") == 2  # unknown codes default, never crash


def test_minor_to_major_returns_decimal_never_float():
    assert money.minor_to_major(3523128, "ZAR") == Decimal("35231.28")
    assert money.minor_to_major(1000, "JPY") == Decimal("1000")
    assert money.minor_to_major(-17491, "ZAR") == Decimal("-174.91")
    out = money.minor_to_major(1, "USD")
    assert isinstance(out, Decimal) and not isinstance(out, float)


def test_major_to_minor_round_trip():
    assert money.major_to_minor("35231.28", "ZAR") == 3523128
    assert money.major_to_minor("1000", "JPY") == 1000
    assert money.major_to_minor(Decimal("19.99"), "EUR") == 1999
    for minor, ccy in [(1, "ZAR"), (100, "USD"), (999, "JPY"), (5, "KRW")]:
        assert money.major_to_minor(money.minor_to_major(minor, ccy), ccy) == minor


def test_currency_symbol_falls_back_to_code():
    assert money.currency_symbol("ZAR") == "R"
    assert money.currency_symbol("USD") == "$"
    assert money.currency_symbol("EUR") == "\u20ac"
    assert money.currency_symbol("GBP") == "\u00a3"
    assert money.currency_symbol("JPY") == "\u00a5"
    assert money.currency_symbol("XXQ") == "XXQ"


def test_format_money_symbol_grouped_sign_first():
    assert money.format_money(3523128, "ZAR") == "R35,231.28"
    assert money.format_money(1000, "JPY") == "\u00a51,000"
    assert money.format_money(-17491, "ZAR") == "-R174.91"
    assert money.format_money(0, "USD") == "$0.00"


def test_auditor_csv_uses_money_module():
    src = Path("apps/api/reports.py").read_text()
    assert "minor_to_major" in src
    assert "amount_display" in src


def test_excel_labels_derive_from_currency():
    src = Path("apps/api/reports.py").read_text()
    assert "currency_symbol" in src


def test_dashboard_summary_carries_currency():
    src = Path("apps/api/main.py").read_text()
    at = src.index('@app.get("/v1/dashboard/summary")')
    assert '"currency"' in src[at:at + 4000]
