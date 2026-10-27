"""
Test totals =/- == balance from top to bottom and bottom to top per user question
"""
from apps.worker.parsers.base import ExtractedRow
from apps.worker.reconcile import run_reconciliation_gate, check_opening_closing, check_opening_closing_reverse, check_running_balance_monotonic, check_running_balance_reverse

def make_row(date, desc, amount_minor, direction, balance_after, line_id):
    return ExtractedRow(
        line_ids=[line_id],
        date=date,
        description=desc,
        amount_minor=abs(amount_minor),
        direction=direction,
        balance_after_minor=balance_after,
        source_quote=f"{date} {desc} {amount_minor} {balance_after}"
    )

def test_totals_plus_minus_equals_balance_both_directions():
    # Opening 10000, transactions: -1000 debit, -2000 debit, +500 credit, closing 7500
    # Top to bottom: 10000 -1000 -2000 +500 = 7500
    # Bottom to top: 7500 +1000 +2000 -500 = 10000
    opening = 10000_00  # R100.00 in cents? Actually 10000_00 = 10000.00? Let's use minor: 10000_00 = 10000*100 = 1,000,000? Simpler: use cents directly
    # Use minor: opening 10000 = R100.00
    opening = 10000
    rows = [
        make_row("2026-10-25", "WOOLWORTHS", 1000, "debit", 9000, "L001"),  # 10000-1000=9000
        make_row("2026-10-26", "RENT", 2000, "debit", 7000, "L002"),       # 9000-2000=7000
        make_row("2026-10-27", "SALARY", 500, "credit", 7500, "L003"),     # 7000+500=7500
    ]
    closing = 7500

    # Top to bottom
    oc_pass, computed, msg = check_opening_closing(opening, closing, rows)
    assert oc_pass, f"Top->Bottom should pass: {msg}"
    assert computed == closing

    # Bottom to top
    oc_rev_pass, computed_opening, msg_rev = check_opening_closing_reverse(closing, opening, rows)
    assert oc_rev_pass, f"Bottom->Top should pass: {msg_rev}"
    assert computed_opening == opening

    # Running balance top->bottom
    rb_pass, breaks = check_running_balance_monotonic(rows)
    assert rb_pass, f"Running top->bottom should pass, breaks {breaks}"

    # Running balance bottom->top
    rb_rev_pass, breaks_rev = check_running_balance_reverse(rows)
    assert rb_rev_pass, f"Running bottom->top should pass, breaks {breaks_rev}"

    # Full gate
    gate = run_reconciliation_gate(opening, closing, rows)
    assert gate["overall_pass"] is True
    assert gate["opening_closing_top_bottom"]["pass"] is True
    assert gate["opening_closing_bottom_top"]["pass"] is True
    assert gate["running_balance_top_bottom"]["pass"] is True
    assert gate["running_balance_bottom_top"]["pass"] is True
    assert "top_to_bottom" in gate["totals_check"]
    assert "bottom_to_top" in gate["totals_check"]

def test_totals_fail_both_directions():
    # Opening 10000, transactions -1000 -2000 +500 = should be 7500 but we give closing 8000 (wrong)
    opening = 10000
    closing_wrong = 8000
    rows = [
        make_row("2026-10-25", "WOOLWORTHS", 1000, "debit", 9000, "L001"),
        make_row("2026-10-26", "RENT", 2000, "debit", 7000, "L002"),
        make_row("2026-10-27", "SALARY", 500, "credit", 7500, "L003"),
    ]
    # Top->bottom should fail
    oc_pass, computed, msg = check_opening_closing(opening, closing_wrong, rows)
    assert oc_pass is False, f"Should fail top->bottom with wrong closing: {msg}"
    # Bottom->top should also fail
    oc_rev_pass, computed_opening, msg_rev = check_opening_closing_reverse(closing_wrong, opening, rows)
    assert oc_rev_pass is False, f"Should fail bottom->top with wrong closing: {msg_rev}"

    gate = run_reconciliation_gate(opening, closing_wrong, rows)
    assert gate["overall_pass"] is False
    assert gate["status"] == "fail"

def test_running_balance_break_both_directions():
    # Break in middle: second row balance wrong
    opening = 10000
    rows = [
        make_row("2026-10-25", "WOOLWORTHS", 1000, "debit", 9000, "L001"),  # ok 10000-1000=9000
        make_row("2026-10-26", "RENT", 2000, "debit", 9999, "L002"),       # wrong should be 7000 but is 9999
        make_row("2026-10-27", "SALARY", 500, "credit", 7500, "L003"),     # 9999+500=10499 not 7500 also wrong
    ]
    closing = 7500

    rb_pass, breaks = check_running_balance_monotonic(rows)
    assert rb_pass is False
    assert len(breaks) >= 1

    rb_rev_pass, breaks_rev = check_running_balance_reverse(rows)
    assert rb_rev_pass is False
    assert len(breaks_rev) >= 1
