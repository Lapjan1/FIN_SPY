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
    Check running balance monotonic per row if balance_after present
    Returns (pass, list of break messages)
    """
    breaks = []
    for i, row in enumerate(rows):
        if row.balance_after_minor is None:
            continue
        # Compute expected balance from previous + current row
        # For simplicity, check if balance_after is plausible - should be within some range?
        # Real check: previous balance + signed amount = current balance
        if i == 0:
            continue
        prev = rows[i-1]
        if prev.balance_after_minor is None:
            continue
        signed = -row.amount_minor if row.direction == "debit" else row.amount_minor
        expected = prev.balance_after_minor + signed
        diff = abs(expected - row.balance_after_minor)
        if diff > 100:  # 1 Rand tolerance
            breaks.append(f"Row {i} {row.line_ids} balance break: prev {prev.balance_after_minor} + signed {signed} = expected {expected} vs actual {row.balance_after_minor} diff {diff}")

    return (len(breaks) == 0), breaks

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
    Run all gates, returns dict with pass/fail and details
    Per docs/PLAN.md Done Means: Given same pdf uploaded twice, fingerprint detects exact duplicate, second upload status duplicate but preserved
    """
    results = {}

    # Opening/closing
    oc_pass, oc_computed, oc_msg = check_opening_closing(opening_minor, closing_minor, rows)
    results["opening_closing"] = {"pass": oc_pass, "computed": oc_computed, "message": oc_msg}

    # Running balance
    rb_pass, rb_breaks = check_running_balance_monotonic(rows)
    results["running_balance"] = {"pass": rb_pass, "breaks": rb_breaks}

    # Duplicates
    dup_pass, dup_list = check_duplicate_fingerprints(rows)
    results["duplicates"] = {"pass": dup_pass, "duplicates": dup_list}

    # Overall
    overall_pass = oc_pass and rb_pass and dup_pass
    results["overall_pass"] = overall_pass
    results["status"] = "pass" if overall_pass else "fail"

    return results
