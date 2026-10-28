"""
Debug why statements does not consolidate - opening balance +/- amount == running balance/total from top to bottom and bottom to top
Per user: need to see why statements does not consolidate
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.worker.parsers.extractor import extract_text_with_bbox, deterministic_parse
from apps.worker.reconcile import run_reconciliation_gate
import tempfile
import uuid

def create_test_pdf(path: Path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        "FNB Statement - Account 123456789 - Branch 250655",
        "Period: 01 Oct 2026 to 31 Oct 2026",
        "Opening Balance: R12 340.55",
        "Date       Description                    Amount      Balance",
        "25 Oct 2026  WOOLWORTHS CT   R450,00-  R11 890,55",
        "26 Oct 2026  RENT - DEBNAM PROPERTY  R5 000,00-  R6 890,55",
        "27 Oct 2026  SALARY - ABC CORP  R15 000,00+  R21 890,55",
        "28 Oct 2026  SHELL FUEL  R800,00-  R21 090,55",
        "29 Oct 2026  VODACOM  R300,00-  R20 790,55",
        "Closing Balance: R20 790,55",
        "Page 1 of 1",
    ]
    y = 750
    for line in lines:
        page.insert_text((50, y), line, fontsize=10)
        y -= 20
    doc.save(str(path))
    doc.close()

def debug_consolidation(pdf_path: Path):
    print(f"=== Debugging consolidation for {pdf_path} ===")
    pages = extract_text_with_bbox(pdf_path)
    print(f"Pages: {len(pages)}, total lines: {sum(len(p['lines']) for p in pages)}")
    for page in pages:
        for line in page['lines']:
            print(f"  {line['line_id']} | {line['text']}")

    result = deterministic_parse(pages, bank_hint="FNB")
    print(f"\n=== Extraction Result ===")
    print(f"Statement: {result.statement}")
    print(f"Opening: {result.opening_balance_minor} Closing: {result.closing_balance_minor}")
    print(f"Rows extracted: {len(result.rows)}")
    for i, row in enumerate(result.rows):
        print(f"  Row {i} {row.line_ids} date={row.date} desc={row.description} amount={row.amount_minor} dir={row.direction} balance_after={row.balance_after_minor} quote={row.source_quote[:50]}")

    print(f"\nUnaccounted lines: {len(result.unaccounted_lines)}")
    for unacc in result.unaccounted_lines:
        print(f"  {unacc['line_id']}: {unacc['reason']}")

    print(f"\nWarnings: {result.warnings}")

    # Reconciliation gate both directions
    print(f"\n=== Reconciliation Gate Top->Bottom + Bottom->Top ===")
    gate = run_reconciliation_gate(result.opening_balance_minor, result.closing_balance_minor, result.rows)
    print(f"Overall: {gate['status']} pass={gate['overall_pass']}")
    print(f"Top->Bottom opening+sum=closing: {gate['opening_closing_top_bottom']['message']}")
    print(f"Bottom->Top closing-sum=opening: {gate['opening_closing_bottom_top']['message']}")
    print(f"Running Top->Bottom: pass={gate['running_balance_top_bottom']['pass']} breaks={gate['running_balance_top_bottom']['breaks']}")
    print(f"Running Bottom->Top: pass={gate['running_balance_bottom_top']['pass']} breaks={gate['running_balance_bottom_top']['breaks']}")
    print(f"Duplicates: {gate['duplicates']}")
    print(f"Totals check: {gate['totals_check']['top_to_bottom']} | {gate['totals_check']['bottom_to_top']}")

    # Detailed step-by-step consolidation
    print(f"\n=== Step-by-step Consolidation Top->Bottom ===")
    if result.opening_balance_minor is not None:
        running = result.opening_balance_minor
        print(f"Opening: {running/100:.2f}")
        for i, row in enumerate(result.rows):
            signed = -row.amount_minor if row.direction == "debit" else row.amount_minor
            expected = running + signed
            actual = row.balance_after_minor
            match = "OK" if actual is None or abs(expected - actual) <= 100 else f"MISMATCH expected {expected/100:.2f} vs actual {actual/100:.2f} diff {(expected-actual)/100:.2f}"
            print(f"  Row {i} {row.line_ids} {row.date} {row.description} {row.direction} {row.amount_minor/100:+.2f} => running {running/100:.2f} {signed/100:+.2f} = {expected/100:.2f} balance_after {actual/100:.2f if actual else 'None'} {match}")
            if actual is not None:
                running = actual
            else:
                running = expected
        print(f"Computed closing: {running/100:.2f} vs actual closing: {result.closing_balance_minor/100:.2f if result.closing_balance_minor else 'None'} diff {(running - (result.closing_balance_minor or 0))/100:.2f} (tolerance R1.00)")

    print(f"\n=== Step-by-step Consolidation Bottom->Top ===")
    if result.closing_balance_minor is not None:
        running = result.closing_balance_minor
        print(f"Closing: {running/100:.2f}")
        for i in range(len(result.rows)-1, -1, -1):
            row = result.rows[i]
            signed = -row.amount_minor if row.direction == "debit" else row.amount_minor
            # To get previous, subtract signed of current/next
            # Actually for reverse: prev = current - signed_next? Let's use gate logic
            # For bottom->top: expected prev = current - signed_current? No, need careful
            # Our check_running_balance_reverse does: expected_curr = next.balance_after - signed_next
            # So for this step print, we show: current row's balance should be next - signed_next
            if i < len(result.rows)-1:
                next_row = result.rows[i+1]
                signed_next = -next_row.amount_minor if next_row.direction == "debit" else next_row.amount_minor
                if next_row.balance_after_minor is not None and row.balance_after_minor is not None:
                    expected_curr = next_row.balance_after_minor - signed_next
                    match = "OK" if abs(expected_curr - row.balance_after_minor) <= 100 else f"MISMATCH"
                    print(f"  Row {i} {row.line_ids} balance {row.balance_after_minor/100:.2f} vs expected from next {next_row.balance_after_minor/100:.2f} - {signed_next/100:+.2f} = {expected_curr/100:.2f} {match}")
            print(f"  Row {i} {row.line_ids} {row.description} {row.direction} {row.amount_minor/100:+.2f} => reverse running {running/100:.2f} - {signed/100:+.2f} = {(running - signed)/100:.2f}")
            running -= signed
        print(f"Computed opening: {running/100:.2f} vs actual opening: {result.opening_balance_minor/100:.2f if result.opening_balance_minor else 'None'}")

def main():
    tmp_path = Path(tempfile.gettempdir()) / f"debug_consolidation_{uuid.uuid4().hex[:6]}.pdf"
    create_test_pdf(tmp_path)
    debug_consolidation(tmp_path)
    tmp_path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
