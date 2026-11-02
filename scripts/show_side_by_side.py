"""
Show statement and extraction side by side - per user request: Can I see the statement and the extraction side by side?
Generates synthetic bank statement PDF, extracts with line-ID grounding, creates HTML with two columns: left statement with bbox, right extraction rows.
"""
import sys
from pathlib import Path
# Add project root to path for apps imports
sys.path.insert(0, str(Path(__file__).parent.parent))
import hashlib
import tempfile
import uuid

def create_statement_pdf(path: Path):
    try:
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)  # A4
        # FNB statement - realistic: Cr = credit, bare = debit, no +/-
        lines = [
            "FNB Statement - Account 123456789 - Branch 250655",
            "Period: 01 Oct 2026 to 31 Oct 2026",
            "Opening Balance: R12 340,55Cr",
            "Date       Description                    Amount      Balance",
            "25 Oct 2026  WOOLWORTHS CT   R450,00  R11 890,55Cr",
            "26 Oct 2026  RENT - DEBNAM PROPERTY  R5 000,00  R6 890,55Cr",
            "27 Oct 2026  SALARY - ABC CORP  R15 000,00Cr  R21 890,55Cr",
            "28 Oct 2026  SHELL FUEL  R800,00  R21 090,55Cr",
            "29 Oct 2026  VODACOM  R300,00  R20 790,55Cr",
            "Closing Balance: R20 790,55Cr",
            "Page 1 of 1",
        ]
        # PyMuPDF uses a top-left origin (reportlab below is
        # bottom-left): start near the top, step downward.
        y = 92
        for line in lines:
            page.insert_text((50, y), line, fontsize=10)
            y += 20
        doc.save(str(path))
        doc.close()
        return True
    except Exception as e:
        print(f"PyMuPDF failed: {e}, trying reportlab")
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            c = canvas.Canvas(str(path), pagesize=A4)
            # FNB statement - realistic: Cr = credit, bare = debit, no +/-
            lines = [
                "FNB Statement - Account 123456789 - Branch 250655",
                "Period: 01 Oct 2026 to 31 Oct 2026",
                "Opening Balance: R12 340,55Cr",
                "Date       Description                    Amount      Balance",
                "25 Oct 2026  WOOLWORTHS CT   R450,00  R11 890,55Cr",
                "26 Oct 2026  RENT - DEBNAM PROPERTY  R5 000,00  R6 890,55Cr",
                "27 Oct 2026  SALARY - ABC CORP  R15 000,00Cr  R21 890,55Cr",
                "28 Oct 2026  SHELL FUEL  R800,00  R21 090,55Cr",
                "29 Oct 2026  VODACOM  R300,00  R20 790,55Cr",
                "Closing Balance: R20 790,55Cr",
                "Page 1 of 1",
            ]
            y = 750
            for line in lines:
                c.drawString(50, y, line)
                y -= 20
            c.save()
            return True
        except Exception as e2:
            print(f"Both failed: {e} {e2}")
            return False

def extract_and_show(pdf_path: Path):
    from apps.worker.parsers.extractor import extract_text_with_bbox, deterministic_parse, llm_fallback
    from apps.worker.reconcile import run_reconciliation_gate
    from apps.worker.parsers.classifier import is_bank_statement

    pages = extract_text_with_bbox(pdf_path)
    # Classify if bank statement
    all_text = " ".join([line['text'] for page in pages for line in page['lines']])
    is_bank, conf, reasons = is_bank_statement(all_text, pdf_path.name, "application/pdf")

    result = deterministic_parse(pages, bank_hint="FNB")
    if result is None or len(result.rows) == 0:
        result = llm_fallback(pages, model_id="muse-spark-1.1")

    gate = run_reconciliation_gate(result.opening_balance_minor, result.closing_balance_minor, result.rows)

    return pages, result, gate, (is_bank, conf, reasons)

def generate_html(pages, result, gate, classification, output_path: Path, pdf_path: Path):
    is_bank, conf, reasons = classification
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>FIN_SPY - Statement and Extraction Side by Side</title>
<style>
body {{ font-family: monospace; margin: 0; padding: 20px; background: #0f172a; color: #e2e8f0; }}
.container {{ display: flex; gap: 20px; }}
.left, .right {{ flex: 1; border: 1px solid #1e293b; border-radius: 8px; padding: 15px; background: #1e293b; height: 90vh; overflow-y: auto; }}
h2 {{ color: #38bdf8; }}
.line {{ margin: 2px 0; padding: 2px 5px; border-left: 3px solid transparent; }}
.line:hover {{ background: #2d3748; border-left-color: #38bdf8; }}
.line-id {{ color: #fbbf24; font-weight: bold; }}
.bbox {{ color: #94a3b8; font-size: 0.8em; }}
.transaction {{ border: 1px solid #334155; margin: 10px 0; padding: 10px; border-radius: 5px; background: #0f172a; }}
.transaction:hover {{ border-color: #38bdf8; }}
.debit {{ color: #f87171; }}
.credit {{ color: #4ade80; }}
.pass {{ color: #4ade80; }}
.fail {{ color: #f87171; }}
.tamper {{ background: #7f1d1d; padding: 5px; border-radius: 3px; }}
</style>
</head>
<body>
<h1>FIN_SPY - Statement and Extraction Side by Side</h1>
<p>PDF: {pdf_path.name} | Is Bank Statement: {is_bank} Confidence: {conf:.0%} | Reasons: {', '.join(reasons[:3])}</p>
<div class="container">
<div class="left">
<h2>📄 Original Statement (Left) - Line-ID Grounding</h2>
<p>Every line has Lxxx ID + bbox for traceability per AGENTS.md</p>
"""
    for page in pages:
        html += f"<h3>Page {page['page_no']} - {page['width']}x{page['height']}</h3>"
        for line in page['lines']:
            bbox_str = f"[{line['bbox'][0]:.0f},{line['bbox'][1]:.0f},{line['bbox'][2]:.0f},{line['bbox'][3]:.0f}]"
            html += f"<div class='line'><span class='line-id'>{line['line_id']}</span> <span class='bbox'>{bbox_str}</span> {line['text']}</div>\n"

    html += f"""
</div>
<div class="right">
<h2>🔍 Extraction (Right) - DB-first</h2>
<p>Statement: {result.statement}</p>
<p>Opening: {result.opening_balance_minor} Closing: {result.closing_balance_minor} Warnings: {result.warnings}</p>

<h3>Reconciliation Gate - Totals +/- == Balance Top->Bottom + Bottom->Top</h3>
<div class="{'pass' if gate['overall_pass'] else 'fail'}">
  <p><strong>Overall:</strong> {gate['status']} - {'PASS' if gate['overall_pass'] else 'FAIL'}</p>
  <p>Top->Bottom: {gate['opening_closing_top_bottom']['message']}</p>
  <p>Bottom->Top: {gate['opening_closing_bottom_top']['message']}</p>
  <p>Running Top->Bottom: {'PASS' if gate['running_balance_top_bottom']['pass'] else 'FAIL'} {gate['running_balance_top_bottom']['breaks']}</p>
  <p>Running Bottom->Top: {'PASS' if gate['running_balance_bottom_top']['pass'] else 'FAIL'} {gate['running_balance_bottom_top']['breaks']}</p>
  <p>Duplicates: {'PASS' if gate['duplicates']['pass'] else 'FAIL'} {gate['duplicates']['duplicates']}</p>
  <p>Totals Check: {gate['totals_check']['top_to_bottom']} | {gate['totals_check']['bottom_to_top']}</p>
  <p><em>{gate['totals_check']['explanation']}</em></p>
</div>

<h3>Extracted Transactions - Each cites line_ids + source_quote</h3>
"""

    for i, row in enumerate(result.rows):
        direction_class = "debit" if row.direction == "debit" else "credit"
        html += f"""
<div class='transaction'>
  <div><span class='line-id'>{', '.join(row.line_ids)}</span> <strong>{row.date}</strong> {row.description} <span class='{direction_class}'>R{row.amount_minor/100:.2f} {row.direction}</span> Balance: R{(row.balance_after_minor or 0)/100:.2f}</div>
  <div class='bbox'>Source Quote: "{row.source_quote}"</div>
  <div>Fingerprint: {__import__('hashlib').sha256(f"{row.date}|{row.amount_minor}|{row.description}".encode()).hexdigest()[:16]}... (SHA256 date|amount|desc_norm per AGENTS.md)</div>
</div>
"""

    html += f"""
<h3>Unaccounted Lines</h3>
<ul>
"""
    for unacc in result.unaccounted_lines:
        html += f"<li>{unacc['line_id']}: {unacc['reason']}</li>\n"
    html += "</ul>"

    html += """
</div>
</div>
<p style="margin-top:20px; font-size:0.8em; color:#94a3b8;">Per AGENTS.md: DB-first Extract -> persist to .db with spans page bbox line_id + fingerprint -> all products read DB. Every transaction traceable to exact bbox on original per SourceViewer component. Reconciliation gate blocks court-report inclusion until human resolves per docs/PLAN.md. Built with Meta Muse Spark/Wonder/Image/SAM 3.1</p>
</body>
</html>
"""
    output_path.write_text(html, encoding='utf-8')
    return output_path

def main():
    tmp_dir = Path(tempfile.gettempdir()) / f"fin_spy_side_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(exist_ok=True)
    pdf_path = tmp_dir / "statement.pdf"
    html_path = Path("data/samples/side_by_side.html")
    html_path.parent.mkdir(parents=True, exist_ok=True)

    if not create_statement_pdf(pdf_path):
        print("Failed to create PDF")
        return

    pages, result, gate, classification = extract_and_show(pdf_path)

    html_out = generate_html(pages, result, gate, classification, html_path, pdf_path)
    print(f"Side by side HTML generated: {html_out}")
    print(f"PDF: {pdf_path}")
    print(f"Pages: {len(pages)}, Lines: {sum(len(p['lines']) for p in pages)}, Rows extracted: {len(result.rows)}")
    print(f"Reconciliation overall: {gate['overall_pass']} status {gate['status']}")
    print(f"Bank statement: {classification[0]} confidence {classification[1]:.0%}")

    # Also copy PDF to samples for viewing
    dest_pdf = Path("data/samples/synthetic_statement.pdf")
    import shutil
    shutil.copy(pdf_path, dest_pdf)
    print(f"Sample PDF copied to: {dest_pdf}")

if __name__ == "__main__":
    import tempfile, uuid
    main()
