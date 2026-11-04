"""Currency handling: exponents, symbols, minor/major conversion.

Stdlib only - no app imports, so the API env is not needed to use it.
Money rule stays: integers or Decimal, never float.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ISO 4217 zero-exponent codes. Everything else defaults to 2.
# Three-exponent codes (BHD JOD KWD OMR TND) are a follow-up.
ZERO_DECIMAL = frozenset({
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW",
    "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF",
})

CURRENCY_SYMBOLS = {
    "ZAR": "R", "USD": "$", "EUR": "\u20ac", "GBP": "\u00a3",
    "NGN": "\u20a6", "KES": "KSh", "GHS": "\u20b5", "JPY": "\u00a5",
    "CNY": "\u00a5", "INR": "\u20b9", "BRL": "R$", "CAD": "C$",
    "AUD": "A$", "CHF": "CHF", "AED": "AED",
}


def exponent(currency: str) -> int:
    """Minor-unit exponent for an ISO code. Unknown codes default to 2."""
    return 0 if (currency or "").upper() in ZERO_DECIMAL else 2


def minor_to_major(amount_minor: int, currency: str = "ZAR") -> Decimal:
    """Integer minor units -> Decimal major units. Never float."""
    return Decimal(int(amount_minor)) / (10 ** exponent(currency))


def major_to_minor(amount_major, currency: str = "ZAR") -> int:
    """Major units (str/Decimal/int) -> integer minor units, half-up."""
    return int((Decimal(str(amount_major)) * (10 ** exponent(currency))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def currency_symbol(currency: str) -> str:
    """Display symbol for an ISO code. Unknown codes fall back to the code."""
    code = (currency or "").upper()
    return CURRENCY_SYMBOLS.get(code, code or "ZAR")


def format_money(amount_minor: int, currency: str = "ZAR") -> str:
    """One deterministic display format: sign + symbol + US-grouped majors.

    "R35,231.28", "-R174.91", "$0.00", "\u00a51,000".
    Locale styling (spaces + comma decimals) is a follow-up.
    """
    code = (currency or "ZAR").upper()
    major = minor_to_major(amount_minor, code)
    sign = "-" if major < 0 else ""
    body = f"{abs(major):,.{exponent(code)}f}"
    return f"{sign}{currency_symbol(code)}{body}"
