"""
Reconciliation gate per AGENTS.md + docs/FLOWS.md + homework Part 5.6
Opening + sum(signed rows) = closing, running balance monotonic
Blocks court-report inclusion until human resolves, status exception noted workflow
"""
from typing import List, Tuple, Dict
from .parsers.base import ExtractedRow

def check_opening_closing(opening_minor: int, closing_minor: int, rows: List[ExtractedRow], tolerance_minor: int = 100) -> Tuple[bool, int, str]:
    """
    Check opening + sum(signed rows) = closing within tolerance 1 Rand = 100 cents
    Returns (pass, computed_closing_minor, message)
    """
    if opening_minor is None or closing_minor is None:
        return True, None, "Opening or closing None - skip gate per Appendix A reconciliation na"

    computed = opening_minor
    for r in rows:
        signed = -r.amount_minor if r.direction == "debit" else r.amount_minor
        computed += signed

    diff = abs(computed - closing_minor)
    if diff <= tolerance_minor:
        return True, computed, f"Pass: opening {opening_minor} + sum {computed-opening_minor} = computed {computed} vs closing {closing_minor} diff {diff} within tolerance {tolerance_minor}"
    else:
        return False, computed, f"Fail: opening {opening_minor} + sum {computed-opening_minor} = computed {computed} != closing {closing_minor} diff {diff} > tolerance {tolerance_minor}"

def check_running_balance_monotonic(rows: List[ExtractedRow]) -> Tuple[bool, List[str]]:
    """
    Check running balance monotonic per row if balance_after present - TOP TO BOTTOM
    Prev balance + signed = current balance per AGENTS.md forensic
    Returns (pass, list of break messages)
    """
    breaks = []
    for i, row in enumerate(rows):
        if row.balance_after_minor is None:
            continue
        if i == 0:
            continue
        prev = rows[i-1]
        if prev.balance_after_minor is None:
            continue
        signed = -row.amount_minor if row.direction == "debit" else row.amount_minor
        expected = prev.balance_after_minor + signed
        diff = abs(expected - row.balance_after_minor)
        if diff > 100:  # 1 Rand tolerance
            breaks.append(f"Row {i} {row.line_ids} balance break top->bottom: prev {prev.balance_after_minor} + signed {signed} = expected {expected} vs actual {row.balance_after_minor} diff {diff}")

    return (len(breaks) == 0), breaks

def check_running_balance_reverse(rows: List[ExtractedRow]) -> Tuple[bool, List[str]]:
    """
    Check running balance BOTTOM TO TOP per user question: totals =/- == balance from top to bottom and from bottom to top
    Current balance = next balance - signed_next
    Returns (pass, breaks)
    """
    breaks = []
    # Iterate from bottom to top-1
    for i in range(len(rows)-1, 0, -1):
        curr = rows[i-1]
        next_row = rows[i]
        if curr.balance_after_minor is None or next_row.balance_after_minor is None:
            continue
        signed_next = -next_row.amount_minor if next_row.direction == "debit" else next_row.amount_minor
        expected_curr = next_row.balance_after_minor - signed_next
        diff = abs(expected_curr - curr.balance_after_minor)
        if diff > 100:
            breaks.append(f"Row {i-1} {curr.line_ids} balance break bottom->top: next {next_row.balance_after_minor} - signed_next {signed_next} = expected {expected_curr} vs actual {curr.balance_after_minor} diff {diff}")

    return (len(breaks) == 0), breaks

def check_opening_closing_reverse(closing_minor: int, opening_minor: int, rows: List[ExtractedRow], tolerance_minor: int = 100) -> Tuple[bool, int, str]:
    """
    Check closing - sum(signed rows) = opening - BOTTOM TO TOP per user question
    """
    if opening_minor is None or closing_minor is None:
        return True, None, "Opening or closing None - skip reverse gate"

    computed_opening = closing_minor
    for r in reversed(rows):
        signed = -r.amount_minor if r.direction == "debit" else r.amount_minor
        computed_opening -= signed

    diff = abs(computed_opening - opening_minor)
    if diff <= tolerance_minor:
        return True, computed_opening, f"Pass reverse bottom->top: closing {closing_minor} - sum {closing_minor-computed_opening} = computed opening {computed_opening} vs actual opening {opening_minor} diff {diff}"
    else:
        return False, computed_opening, f"Fail reverse bottom->top: closing {closing_minor} - sum = computed opening {computed_opening} != actual opening {opening_minor} diff {diff} > tolerance {tolerance_minor}"

def check_duplicate_fingerprints(rows: List[ExtractedRow]) -> Tuple[bool, List[Dict]]:
    """
    Check for exact duplicate fingerprints per AGENTS.md fingerprint SHA256(date|amount|desc_norm)
    """
    from .parsers.base import fingerprint_txn
    seen = {}
    dups = []
    for row in rows:
        fp = fingerprint_txn(row.date, row.amount_minor, row.description)
        if fp in seen:
            dups.append({"type": "exact_duplicate", "line_ids": row.line_ids, "dup_of": seen[fp], "fingerprint": fp})
        else:
            seen[fp] = row.line_ids
    return (len(dups) == 0), dups

def run_reconciliation_gate(opening_minor: int, closing_minor: int, rows: List[ExtractedRow]) -> Dict:
    """
    Run all gates top-to-bottom and bottom-to-top per user question: totals =/- == balance from top to bottom and from bottom to top
    Per docs/PLAN.md Done Means: Given same pdf uploaded twice, fingerprint detects exact duplicate, second upload status duplicate but preserved
    """
    results = {}

    # Opening/closing top->bottom: opening + sum = closing
    oc_pass, oc_computed, oc_msg = check_opening_closing(opening_minor, closing_minor, rows)
    results["opening_closing_top_bottom"] = {"pass": oc_pass, "computed": oc_computed, "message": oc_msg, "direction": "top->bottom: opening + sum = closing"}

    # Opening/closing bottom->top: closing - sum = opening
    oc_rev_pass, oc_rev_computed, oc_rev_msg = check_opening_closing_reverse(closing_minor, opening_minor, rows)
    results["opening_closing_bottom_top"] = {"pass": oc_rev_pass, "computed": oc_rev_computed, "message": oc_rev_msg, "direction": "bottom->top: closing - sum = opening"}

    # Running balance top->bottom: prev + signed = current
    rb_pass, rb_breaks = check_running_balance_monotonic(rows)
    results["running_balance_top_bottom"] = {"pass": rb_pass, "breaks": rb_breaks, "direction": "top->bottom"}

    # Running balance bottom->top: current = next - signed_next
    rb_rev_pass, rb_rev_breaks = check_running_balance_reverse(rows)
    results["running_balance_bottom_top"] = {"pass": rb_rev_pass, "breaks": rb_rev_breaks, "direction": "bottom->top"}

    # Duplicates
    dup_pass, dup_list = check_duplicate_fingerprints(rows)
    results["duplicates"] = {"pass": dup_pass, "duplicates": dup_list}

    # Overall - all four balance checks + duplicates must pass
    overall_pass = oc_pass and oc_rev_pass and rb_pass and rb_rev_pass and dup_pass
    results["overall_pass"] = overall_pass
    results["status"] = "pass" if overall_pass else "fail"
    results["totals_check"] = {
        "top_to_bottom": f"opening {opening_minor} + sum = closing {closing_minor} pass={oc_pass}",
        "bottom_to_top": f"closing {closing_minor} - sum = opening {opening_minor} pass={oc_rev_pass}",
        "explanation": "Totals +/- == balance from top to bottom and from bottom to top per user question - both directions must match within 1 Rand tolerance"
    }

    return results
