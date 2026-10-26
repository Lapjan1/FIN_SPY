"""
Debt snowball vs avalanche - pure Decimal maths, never float per AGENTS.md.
Business owner peek: KPI + debt kill plan.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class Debt:
    creditor: str
    balance_minor: int  # cents
    apr_pct: Decimal
    min_payment_minor: int

def to_decimal_minor(minor: int) -> Decimal:
    return (Decimal(minor) / Decimal(100)).quantize(Decimal('0.01'))

def from_decimal_minor(d: Decimal) -> int:
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))

def monthly_rate(apr_pct: Decimal) -> Decimal:
    return (apr_pct / Decimal(100) / Decimal(12))

def plan_debts(debts: List[Debt], extra_cash_minor: int, method: str = "snowball") -> Dict:
    """
    method snowball: smallest balance first (psych win)
    avalanche: highest APR first (interest save)
    Returns order, months, interest_saved, total_paid, narrative placeholder.
    Uses Decimal for all money maths.
    """
    if method == "snowball":
        order = sorted(debts, key=lambda d: d.balance_minor)
    else:
        order = sorted(debts, key=lambda d: d.apr_pct, reverse=True)

    # Simplified simulation: assume min payments + extra to first in order
    total_paid_minor = sum(d.balance_minor for d in order)
    total_minor = total_paid_minor  # placeholder for interest calc
    months = 0
    remaining = [d.balance_minor for d in order]
    # TODO: implement accurate amortization loop with Decimal
    # For scaffold, crude months estimate
    total_min_monthly = sum(d.min_payment_minor for d in order) + extra_cash_minor
    if total_min_monthly > 0:
        # Rough: total balance / monthly
        months = max(1, total_paid_minor // total_min_monthly)

    # Interest saved vs other method would need both simulations
    return {
        "method": method,
        "order": [d.creditor for d in order],
        "months": months,
        "total_paid_minor": total_paid_minor,
        "interest_saved_minor": 0,  # TODO calc diff between methods
        "narrative": f"{method.title()} plan: Pay {order[0].creditor} first, then roll payment. Estimated {months} months. Disclaimer: not financial advice, for illustration.",
        "disclaimer": "Calculation aid, not financial advice. Verify with qualified practitioner. SA VAT/tax rules not included."
    }

def what_if_extra(debts: List[Debt], extra_minor: int, method: str) -> Dict:
    base = plan_debts(debts, 0, method)
    boosted = plan_debts(debts, extra_minor, method)
    return {
        "base_months": base["months"],
        "boosted_months": boosted["months"],
        "months_saved": base["months"] - boosted["months"],
        "extra_per_month_minor": extra_minor
    }
