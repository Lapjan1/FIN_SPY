"""Money tokenizer grammar: thousands spaces come in strict 3s, never fuse.

Live 2025-05 FNB file glued reference numbers to amounts ("2700 250.00"
became one R270k token) because the space branch never checked the leading
side. Valid SA grouping is 1-3 leading digits then exact 3s ("1 234,56");
anything else splits. All fixtures synthetic shapes, never live digits.
"""
from apps.worker.parsers.generic import _money_tokens


def _toks(text):
    return [tok for tok, _, _ in _money_tokens(text)]


def test_ref_number_plus_amount_never_fuse():
    assert _toks("TRACE 12345678901 800.00 1,113.86Cr") == ["800.00", "1,113.86Cr"]


def test_four_digit_leading_group_splits():
    assert _toks("2025 123 456,78") == ["123 456,78"]


def test_short_ref_plus_amount_splits():
    assert _toks("2700 250.00 558.86Cr") == ["250.00", "558.86Cr"]


def test_valid_space_thousands_intact():
    assert _toks("R1 234,56 BAL R12 340,55") == ["R1 234,56", "R12 340,55"]
    assert _toks("(6,000.00) 4,793.31Cr") == ["(6,000.00)", "4,793.31Cr"]
    assert _toks("75.50 5,574.50") == ["75.50", "5,574.50"]


def test_dates_and_years_never_tokenize():
    assert _toks("2026-10-01 Statement 2025 Page 12") == []
