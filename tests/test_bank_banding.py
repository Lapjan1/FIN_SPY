"""Per-bank header banding: FNB/ABSA/STDB vocabularies from research.

FNB + ABSA head tables with Date/Description/Amount/Balance classes (FNB
live-proven, ABSA per FNBP synthetic fixture). STDB's cheque "Date
Description ..." tail is unconfirmed, so balance words are not required.
Banding is order-free (zones only, never document position): PDF extraction
runs bottom-first while text paths run top-first, so position proves
nothing. All geometry synthetic.
"""
from apps.worker.parsers.absa import parse_absa_lines
from apps.worker.parsers.fnb import parse_fnb_lines
from apps.worker.parsers.stdb import parse_stdb_lines


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
    return [{"page_no": 1, "width": 595, "height": 842,
             "lines": list(lines)}]


def _hdr(lid, text, date_x0=36, bal_x0=470, y0=700):
    words = []
    x = 10
    for w in text.split(" "):
        if w.lower().startswith("date"):
            x0 = date_x0
        elif w.lower().startswith("balance"):
            x0 = bal_x0
        else:
            x0 = x
        words.append((w, x0, x0 + len(w) * 6))
        x = x0 + len(w) * 6 + 12
    return _wl(lid, text, words, y0=y0)


def _crow(lid, day, desc, amount, balance, dx0=36, balx0=470):
    # Columnar row: date words at dx0, balance token at balx0.
    text = f"{day} {desc} {amount} {balance}"
    parts = text.split(" ")
    words = []
    x = dx0
    for i, w in enumerate(parts):
        if i >= len(parts) - 1:
            x = balx0
        elif i == len(parts) - 2:
            x = 400
        words.append((w, x, x + max(len(w) * 6, 20)))
        x += len(w) * 6 + 8
    return _wl(lid, text, words)


def test_stdb_cheque_header_zones_without_balance_word():
    # Cheque tail unconfirmed by research: date + desc words suffice.
    # Order-free: the in-column decoy sits above the header yet is kept;
    # only the out-of-zone row is dropped.
    pages = _pages(
        _crow("L001", "2026-10-01", "PRE A", "100.00", "900.00"),
        _hdr("L002", "Date Description Debit Credit"),
        _crow("L003", "2026-10-25", "SHOP A", "100.00", "900.00"),
        _crow("L004", "2026-10-26", "PAY B", "50.00", "950.00"),
        _crow("L005", "2026-10-27", "SHOP C", "200.00", "750.00"),
        _crow("L006", "2026-10-28", "ODD D", "250.00", "500.00", dx0=300),
    )
    result = parse_stdb_lines(pages)
    assert [r.line_ids[0] for r in result.rows] == ["L001", "L003", "L004",
                                                   "L005"]


def test_stdb_footer_legend_ignored():
    pages = _pages(
        _hdr("L001", "Date Description Debit Credit", y0=100),
        _crow("L002", "2026-10-25", "SHOP A", "100.00", "900.00"),
        _crow("L003", "2026-10-26", "PAY B", "50.00", "950.00"),
    )
    result = parse_stdb_lines(pages)
    assert [r.line_ids[0] for r in result.rows] == ["L002", "L003"]


def test_stdb_single_token_homeloan_row_kept():
    # Home-loan shape carries balance-only rows; the single token stays,
    # valued as-is (not as the date's digits, the old loose behavior).
    pages = _pages(
        _wl("L001", "Transaction details"),
        _wl("L002", "2026-10-04 LOAN X 950.00"),
    )
    result = parse_stdb_lines(pages)
    assert len(result.rows) == 1
    assert result.rows[0].amount_minor == 95000
    assert result.rows[0].balance_after_minor is None


def test_absa_history_header_and_zones():
    pages = _pages(
        _wl("L001", "Transaction history"),
        _hdr("L002", "Date Description Amount Balance"),
        _crow("L003", "25/10/2026", "SHOP A", "(450.00)", "(12 340.55)"),
        _crow("L004", "26/10/2026", "PAY B", "(50.00)", "(12 290.55)"),
        _crow("L005", "27/10/2026", "SHOP C", "(200.00)", "(12 090.55)"),
        _crow("L006", "28/10/2026", "ODD D", "(250.00)", "(11 840.55)",
              balx0=600),
    )
    result = parse_absa_lines(pages)
    assert [r.line_ids[0] for r in result.rows] == ["L003", "L004", "L005"]
    assert result.rows[0].direction == "debit"


def test_absa_single_token_prose_is_noise():
    pages = _pages(
        _wl("L001", "Transaction history"),
        _wl("L002", "25/10/2026 FEE NOTE PRIME RATE 11.75 PERCENT"),
    )
    result = parse_absa_lines(pages)
    assert result.rows == []


def test_fnb_header_zones():
    pages = _pages(
        _hdr("L001", "Date Description Amount Balance"),
        _crow("L002", "25 Oct 2026", "SHOP A", "R450,00-", "R11 890,55"),
        _crow("L003", "26 Oct 2026", "PAY B", "R50,00-", "R11 840,55"),
        _crow("L004", "27 Oct 2026", "SHOP C", "R200,00-", "R11 640,55"),
        _crow("L005", "28 Oct 2026", "ODD D", "R250,00-", "R11 390,55",
              balx0=600),
    )
    result = parse_fnb_lines(pages)
    assert [r.line_ids[0] for r in result.rows] == ["L002", "L003", "L004"]
