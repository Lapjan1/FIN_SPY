"""Header column banding: table headers define x-zones for Date and Balance.

Live FNB files head each page with a Date/Description/Amount/Balance line;
rows beneath it must sit in those columns. A candidate whose date or balance
lands outside the header's x-bands is boilerplate, not a row. Order-free by
design (PDF extraction runs bottom-first, text paths top-first): geometry
only, never document position. Footer legends carrying header words are
rejected by the top-half gate. Geometry here is hand-placed synthetic.
"""
from apps.worker.parsers.generic import detect_table_header, parse_generic_lines

PAGE_H = 842


def _wl(lid, text, words=None, y0=0):
    if words is not None:
        joined = " ".join(w for w, _, _ in words)
        assert joined == text, f"words must rebuild text: {joined!r}"
    line = {"line_id": lid, "bbox": [0, y0, 600, y0 + 10],
            "text": text, "text_hash": "x"}
    if words is not None:
        line["words"] = [{"text": w, "x0": x0, "x1": x1}
                         for w, x0, x1 in words]
    return line


def _pages(*lines):
    return [{"page_no": 1, "width": 595, "height": PAGE_H,
             "lines": list(lines)}]


HEADER = _wl("L001", "Date Description Amount Balance", [
    ("Date", 36, 62), ("Description", 120, 205),
    ("Amount", 400, 452), ("Balance", 470, 528),
], y0=700)


def _row_ln(lid, day, desc, amount, balance, dx0=36, balx0=470):
    # desc is two words ("SHOP A"); amount/balance placed in-column by default.
    # Row y plays no role (order-free); only the header's y matters.
    d0, d1 = desc.split(" ")
    text = f"{day} Oct 2026 {desc} {amount} {balance}"
    return _wl(lid, text, [
        (day, dx0, dx0 + 14), ("Oct", dx0 + 16, dx0 + 34),
        ("2026", dx0 + 36, dx0 + 61), (d0, 120, 150), (d1, 152, 160),
        (amount, 400, 445), (balance, balx0, balx0 + 45),
    ])


def test_detect_header_zones():
    found = detect_table_header(_pages(HEADER))
    assert found is not None
    assert found["line_id"] == "L001"
    assert found["date_zone"] == (36, 62)
    assert found["balance_zone"] == (470, 528)


def test_money_bearing_line_is_never_a_header():
    line = _wl("L001", "Date Description Balance R500,00 total", y0=700)
    assert detect_table_header(_pages(line)) is None


def test_footer_legend_is_never_a_header():
    # Same words as a header, but sitting in the page bottom half: the live
    # FNB file carries exactly this footer under each table.
    line = _wl("L001", "Date Description Amount Balance", [
        ("Date", 36, 62), ("Description", 120, 205),
        ("Amount", 400, 452), ("Balance", 470, 528),
    ], y0=100)
    assert detect_table_header(_pages(line)) is None


def test_header_variant_words():
    line = _wl("L001", "Transaction Date Details Debit Credit Balance", [
        ("Transaction", 10, 70), ("Date", 72, 96), ("Details", 120, 170),
        ("Debit", 400, 440), ("Credit", 445, 490), ("Balance", 500, 560),
    ], y0=700)
    found = detect_table_header(_pages(line))
    assert found is not None
    assert found["date_zone"] == (72, 96)
    assert found["balance_zone"] == (500, 560)


def test_out_of_zone_rows_dropped():
    pages = _pages(
        HEADER,
        _wl("L002", "Opening Balance: R1 000,00"),
        _row_ln("L003", "25", "SHOP A", "100.00", "900.00"),
        _row_ln("L004", "26", "PAY B", "50.00", "950.00"),
        _row_ln("L005", "27", "SHOP C", "200.00", "750.00"),
        # Chains arithmetically (750.00 - 250.00 = 500.00) but its balance
        # sits far right of the Balance column -> boilerplate, not a row.
        _row_ln("L006", "28", "FEE D", "250.00", "500.00", balx0=600),
        # Chains too, but its date sits mid-line (wrapped-header shape).
        _row_ln("L007", "28", "ODD E", "250.00", "500.00", dx0=300),
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert [r.line_ids[0] for r in result.rows] == ["L003", "L004", "L005"]
    assert [r.direction for r in result.rows] == ["debit", "credit", "debit"]
    unacc = {u["line_id"] for u in result.unaccounted_lines}
    assert {"L006", "L007"} <= unacc


def test_zones_skipped_when_layout_flows():
    # Same header, but balances wander (prose-like PDF, Ubuntu shape):
    # no columnar table exists, so geometry must not reject anything.
    pages = _pages(
        HEADER,
        _wl("L002", "Opening Balance: R1 000,00"),
        _row_ln("L003", "25", "SHOP A", "100.00", "900.00", balx0=150),
        _row_ln("L004", "26", "PAY B", "50.00", "950.00", balx0=250),
        _row_ln("L005", "27", "SHOP C", "200.00", "750.00",
                dx0=300, balx0=350),
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert [r.line_ids[0] for r in result.rows] == ["L003", "L004", "L005"]


def test_banding_skipped_without_word_geometry():
    # Same texts as the zone fixture but no words: status-quo pin, the
    # chaining outlier is kept (4 rows) exactly as before banding.
    texts = [
        "Date Description Amount Balance",
        "Opening Balance: R1 000,00",
        "25 Oct 2026 SHOP A 100.00 900.00",
        "26 Oct 2026 PAY B 50.00 950.00",
        "27 Oct 2026 SHOP C 200.00 750.00",
        "28 Oct 2026 FEE D 250.00 500.00",
        "28 Oct 2026 ODD E 250.00 500.00",
    ]
    pages = _pages(*[_wl(f"L{i + 1:03d}", t, y0=700 if i == 0 else 0)
                     for i, t in enumerate(texts)])
    result = parse_generic_lines(pages)
    assert result is not None
    assert [r.line_ids[0] for r in result.rows] == ["L003", "L004", "L005", "L006"]


def test_banding_skipped_without_header():
    pages = _pages(
        _wl("L001", "Opening Balance: R1 000,00"),
        _row_ln("L002", "25", "SHOP A", "100.00", "900.00"),
        _row_ln("L003", "26", "PAY B", "50.00", "950.00"),
        _row_ln("L004", "27", "SHOP C", "200.00", "750.00"),
    )
    result = parse_generic_lines(pages)
    assert result is not None
    assert len(result.rows) == 3
