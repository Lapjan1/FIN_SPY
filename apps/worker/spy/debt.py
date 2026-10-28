"""
Debt snowball vs avalanche - pure Decimal maths, never float per AGENTS.md.
Business owner peek: KPI + debt kill plan.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict
from dataclasses import dataclass

MAX_MONTHS = 600  # 50y cap: break runaway negative-amortization loops


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


def _order(debts: List[Debt], method: str) -> List[Debt]:
    if method == "snowball":
        return sorted(debts, key=lambda d: d.balance_minor)
    return sorted(debts, key=lambda d: d.apr_pct, reverse=True)


def _simulate(order: List[Debt], extra_cash_minor: int) -> Dict:
    """Month-by-month payoff: accrue interest, pay mins, extra to first unpaid.

    All balances in minor ints; monthly interest rounded HALF_UP to the cent.
    """
    bals = [d.balance_minor for d in order]
    total_interest = 0
    total_paid = 0
    months = 0
    no_progress = 0
    while any(b > 0 for b in bals) and months < MAX_MONTHS:
        months += 1
        prev_total = sum(b for b in bals if b > 0)
        paid, interest = _run_month(order, bals, extra_cash_minor)
        total_paid += paid
        total_interest += interest
        # Negative amortization guard: 3 months without balance decrease
        # while debt remains -> payments never clear it (also caps runaway
        # growth before Decimal precision can overflow on absurd APR)
        total = sum(b for b in bals if b > 0)
        if total >= prev_total and total > 0:
            no_progress += 1
            if no_progress >= 3:
                break
        else:
            no_progress = 0
    stuck = any(b > 0 for b in bals)
    return {"months": months, "total_paid_minor": total_paid,
            "total_interest_minor": total_interest, "stuck": stuck}


def _run_month(order: List[Debt], bals: List[int], extra_cash_minor: int):
    """One payoff month: accrue interest, pay minimums, extra to first unpaid.

    Mutates bals. Returns (paid_minor, interest_minor).
    """
    interest_sum = 0
    paid = 0
    for i, d in enumerate(order):
        if bals[i] <= 0:
            continue
        interest = from_decimal_minor(
            to_decimal_minor(bals[i]) * monthly_rate(Decimal(d.apr_pct)))
        bals[i] += interest
        interest_sum += interest
    for i, d in enumerate(order):
        if bals[i] <= 0:
            continue
        pay = min(d.min_payment_minor, bals[i])
        bals[i] -= pay
        paid += pay
    extra = extra_cash_minor
    for i in range(len(order)):
        if extra <= 0:
            break
        if bals[i] <= 0:
            continue
        pay = min(extra, bals[i])
        bals[i] -= pay
        paid += pay
        extra -= pay
    return paid, interest_sum


def plan_debts(debts: List[Debt], extra_cash_minor: int, method: str = "snowball") -> Dict:
    """
    method snowball: smallest balance first (psych win)
    avalanche: highest APR first (interest save)
    interest_saved_minor: this method's interest vs the OTHER method
    (avalanche >= 0 by construction; snowball <= 0). Decimal maths throughout.
    """
    if method not in ("snowball", "avalanche"):
        raise ValueError(f"Invalid parameters: method must be snowball|avalanche, got {method!r}")
    if extra_cash_minor < 0:
        raise ValueError("Invalid parameters: extra_cash_per_month_minor must be >= 0")
    order = _order(debts, method)
    if not order:
        return {"method": method, "order": [], "months": 0,
                "total_paid_minor": 0, "total_interest_minor": 0,
                "interest_saved_minor": 0, "warnings": [],
                "narrative": "No debts supplied.",
                "disclaimer": _disclaimer()}
    sim = _simulate(order, extra_cash_minor)
    other = _simulate(_order(debts, "avalanche" if method == "snowball" else "snowball"),
                      extra_cash_minor)
    warnings = []
    if sim["stuck"]:
        warnings.append("Payments do not cover monthly interest on at least one debt; balances never clear. Increase payments.")
    first = order[0].creditor
    return {
        "method": method,
        "order": [d.creditor for d in order],
        "months": sim["months"],
        "total_paid_minor": sim["total_paid_minor"],
        "total_interest_minor": sim["total_interest_minor"],
        "interest_saved_minor": other["total_interest_minor"] - sim["total_interest_minor"],
        "warnings": warnings,
        "narrative": f"{method.title()} plan: Pay {first} first, then roll payment. Estimated {sim['months']} months, total interest R{to_decimal_minor(sim['total_interest_minor'])}. Disclaimer: not financial advice, for illustration.",
        "disclaimer": _disclaimer(),
    }


def _disclaimer() -> str:
    return ("Calculation aid, not financial advice. Verify with qualified "
            "practitioner. SA VAT/tax rules not included.")


def what_if_extra(debts: List[Debt], extra_minor: int, method: str) -> Dict:
    base = plan_debts(debts, 0, method)
    boosted = plan_debts(debts, extra_minor, method)
    return {
        "base_months": base["months"],
        "boosted_months": boosted["months"],
        "months_saved": base["months"] - boosted["months"],
        "base_interest_minor": base["total_interest_minor"],
        "boosted_interest_minor": boosted["total_interest_minor"],
        "interest_saved_minor": base["total_interest_minor"] - boosted["total_interest_minor"],
        "extra_per_month_minor": extra_minor,
    }
