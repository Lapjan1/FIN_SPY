"""Regenerate the synthetic column-emitted FNB probe PDF (no PII).

Real FNB-class writers emit text column-by-column with yearless
day-month rows; this probe reproduces that shape (all dates, then
descriptions, amounts, balances) with arithmetically chained rows so
live re-extracts prove regrouping + chaining without touching real
statements. Output stays gitignored per policy (data/samples/*.pdf).
"""

from pathlib import Path

import fitz

ROWS = [
    ("04 Jul", "SHOP A", "206.69-", "4,793.31Cr"),
    ("05 Jul", "SHOP B", "184.50-", "4,608.81Cr"),
    ("06 Jul", "FUEL C", "200.00-", "4,408.81Cr"),
    ("07 Jul", "SALARY D", "2,000.00+", "6,408.81Cr"),
    ("08 Jul", "SHOP E", "785.00-", "5,623.81Cr"),
    ("09 Jul", "SHOP F", "100.00-", "5,523.81Cr"),
]


def main() -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 72
    page.insert_text((40, y), "First National Bank - FNB Statement")
    y += 22
    page.insert_text((40, y), "Statement Period : 1 July 2023 to 31 July 2023")
    y += 22
    page.insert_text((40, y), "Account Number 62345678901 Branch Code 250655")
    y += 22
    page.insert_text((40, y), "Opening Balance: R5 000.00")
    y += 30
    top = y
    for col, x in ((0, 40), (1, 110), (2, 300), (3, 420)):
        yy = top
        for r in ROWS:
            page.insert_text((x, yy), r[col])
            yy += 22
    y = top + len(ROWS) * 22 + 8
    page.insert_text((40, y), "Closing Balance: R5 523.81")
    out = Path("data/samples/fnb_column_shape.pdf")
    doc.save(out)
    return out


if __name__ == "__main__":
    print(f"saved {main()}")
