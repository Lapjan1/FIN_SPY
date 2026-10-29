"""
Bank-gated parser selection: only the detected bank's parser may claim a doc.

Regression for: 3-page FNB statement where Absa's loose DD/MM/YYYY + number
patterns claimed 96 garbage rows (FNB itself found 4), the wrong win then
crashed downstream and the doc came back exception + 0 rows. Cross-bank
misfires must fall through to the LLM fallback, never persist as garbage.
"""

from apps.worker.parsers.extractor import deterministic_parse


def _pages():
    lines = [
        {"line_id": "L001", "bbox": [0, 0, 100, 10],
         "text": "First National Bank Statement Account 62123456789",
         "text_hash": "a"},
    ]
    # Absa bait: DD/MM/YYYY + parenthesised amounts, which the FNB parser's
    # "DD Mon YYYY / YYYY/MM/DD / DD-MM-YYYY" dates do not match.
    for i in range(15):
        lid = f"L{i + 2:03d}"
        lines.append(
            {"line_id": lid, "bbox": [0, 0, 100, 10],
             "text": f"25/10/2026 PICK N PAY GEORGE (450.00) (12 340.55)",
             "text_hash": lid}
        )
    lines.append(
        {"line_id": "L017", "bbox": [0, 0, 100, 10],
         "text": "Closing Balance (11 890.55)", "text_hash": "z"}
    )
    return [{"page_no": 1, "width": 595, "height": 842, "lines": lines}]


def test_cross_bank_misfire_falls_through_to_llm(capsys):
    result = deterministic_parse(_pages(), bank_hint="FNB")
    out = capsys.readouterr().out
    assert result is None, "Absa must not claim an FNB doc - route to LLM"
    assert "bank=FNB" in out
    assert "LLM fallback" in out


def test_absa_doc_still_claimed_by_absa():
    lines = [
        {"line_id": "L001", "bbox": [0, 0, 100, 10],
         "text": "Absa Bank Statement Account 4056789012", "text_hash": "a"},
    ]
    for i in range(15):
        lid = f"L{i + 2:03d}"
        lines.append(
            {"line_id": lid, "bbox": [0, 0, 100, 10],
             "text": f"25/10/2026 SHOPRITE CHECKERS (450.00) (12 340.55)",
             "text_hash": lid}
        )
    pages = [{"page_no": 1, "width": 595, "height": 842, "lines": lines}]
    result = deterministic_parse(pages, bank_hint="FNB")
    assert result is not None
    assert len(result.rows) >= 10
