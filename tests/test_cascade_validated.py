"""Validated-beats-unvalidated cascade: FNB self-inconsistency falls through.

FNB proposes unsigned rows with sign-fallback directions and no chaining,
so when its own reconciliation fails the deterministic stage must try the
generic engine: chained rows win, and FNB stands only when generic cannot
chain (recall fallback for unordered layouts). Never worse than status quo.
"""
from apps.worker.parsers.extractor import deterministic_parse


def _pages(*texts):
    return [{
        "page_no": 1, "width": 595, "height": 842,
        "lines": [
            {"line_id": f"L{i + 1:03d}", "bbox": [0, 0, 100, 10],
             "text": t, "text_hash": "x"}
            for i, t in enumerate(texts)
        ],
    }]


def test_fnb_recon_fail_generic_chains_wins():
    pages = _pages(
        "First National Bank Statement Account 62123456789",
        "Opening Balance: R1 000,00",
        "25 Oct 2026 SHOP A 100.00 900.00",
        "26 Oct 2026 PAY B 50.00 950.00",
        "27 Oct 2026 SHOP C 200.00 750.00",
        "Closing Balance: R750,00",
    )
    result = deterministic_parse(pages, bank_hint="FNB")
    assert result is not None
    assert result.statement["bank"] == "GENERIC"
    assert len(result.rows) == 3
    assert [r.direction for r in result.rows] == ["debit", "credit", "debit"]
    assert [r.amount_minor for r in result.rows] == [10000, 5000, 20000]


def test_fnb_stands_when_generic_cannot_chain():
    pages = _pages(
        "First National Bank Statement Account 62123456789",
        "25 Oct 2026 SHOP A 10.00 100.00",
        "26 Oct 2026 PAY B 10.00 999.99",
        "27 Oct 2026 SHOP C 10.00 50.00",
    )
    result = deterministic_parse(pages, bank_hint="FNB")
    assert result is not None
    assert result.statement["bank"] == "FNB"  # recall fallback, not None
    assert len(result.rows) == 3
