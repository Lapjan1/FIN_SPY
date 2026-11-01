"""
Bank-agnostic generic extractor (P0-A0).
SA-wide date/amount/balance line patterns plus running-balance chaining.
Sits between the bank-specific parsers and the LLM last resort: only
balance-validated (chained) rows are returned, everything else stays
unaccounted for the LLM or human review. Never invents rows.
Limits (v1): yearless day-month rows take the Statement Period/Date year (Dec/Jan rollover only); needs a balance column to chain
against; single-line rows only (no continuations); amount-then-balance
column order (the SA standard).
"""
import re
from typing import List, Dict, Optional, Tuple

from .base import ExtractedRow, ExtractionResult, parse_sa_amount

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

_DATE_RES = [
    ("dmy_mon", re.compile(
        r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s*,?\s*(\d{4})\b", re.I)),
    ("mdy_mon", re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
        r"(\d{1,2}),\s*(\d{4})\b", re.I)),
    ("ymd", re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b")),
    ("dmy_num", re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")),
]

# Money must show cents, parens, or a sign/suffix word - bare integers
# (years, page numbers, account numbers) must never match as money.
# Thousands spaces come in strict 3s with a 1-3 digit lead ("1 234,56");
# a 4+ digit lead ("2700 250.00", "2025 123 456,78") is a reference/year
# run glued to an amount and must split, never fuse into a monster token.
# Unspaced runs ("1234,56", "3,213.81") parse as-is via last-separator-wins.
# R must not start mid-word (SPAR must not donate its R to the amount),
# and no token may start glued to a digit on its left.
_INT = r"(?:\d{1,3}(?: \d{3})+|[\d,\.]*\d)"
_TAIL = r"\s*[-+]?\s*(?:[Cc][Rr]|[Dd][Rr])?"
_MONEY_RE = re.compile(
    r"\(\s*R?\s*" + _INT + r"[,\.]\d{2}\s*\)"  # (1 234,56)
    + r"|(?<![A-Za-z\d])R\s*" + _INT + r"[,\.]\d{2}" + _TAIL
    + r"|(?<!\d)" + _INT + r"[,\.]\d{2}" + _TAIL
)


_YEARLESS_RE = re.compile(
    r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b",
    re.I)
_PERIOD_RE = re.compile(
    r"statement\s+(period|date)\s*:?.*?(\d{4})", re.I)


def _period_context(pages: List[Dict]):
    """(year, end_month) from the Statement Period/Date line, else (None, None)."""
    for p in pages:
        for line in p.get("lines", []):
            text = line.get("text", "")
            m = _PERIOD_RE.search(text)
            if not m:
                continue
            years = [int(y) for y in re.findall(r"\d{4}", text)]
            year = years[-1] if years else int(m.group(2))
            months = [_MONTHS[w.lower()[:3]] for w in re.findall(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*",
                text, re.I) if w.lower()[:3] in _MONTHS]
            return year, (months[-1] if months else None)
    return None, None


def _infer_year(row_month: int, period_year, period_end_month):
    if period_year is None:
        return None
    if period_end_month == 1 and row_month == 12:
        return period_year - 1
    return period_year


# Header column banding: top-half table headers (Date ... Balance) define
# the x-bands the Date and Balance columns must sit in. A candidate outside
# the bands is boilerplate - never a row. Order-free (no idx logic: PDF
# extraction runs bottom-first, text paths top-first); skipped silently when
# the header is absent or lines carry no word geometry (CSV/TXT, synthetic).
_HEADER_DATE = ("date",)
_HEADER_DESC = ("description", "details", "narrative")
_HEADER_MONEY = ("amount", "debit", "credit")
_HEADER_BAL = ("balance",)
_ZONE_TOLERANCE_PT = 12.0


def _clean_word(word: str) -> str:
    return word.strip("().,:;").lower()


def _word_hits_class(word: str, classes) -> bool:
    cleaned = _clean_word(word)
    return any(cleaned == k or cleaned.startswith(k) for k in classes)


def _header_words_hit(words, date_c, desc_c, money_c, bal_c, require) -> bool:
    hits = {
        "date": any(_word_hits_class(w, date_c) for w in words),
        "balance": any(_word_hits_class(w, bal_c) for w in words),
        "mid": any(_word_hits_class(w, desc_c + money_c) for w in words),
    }
    return all(hits.get(r, False) for r in require)


def _header_zones(wboxes, date_c, bal_c):
    zones = {"date_zone": None, "balance_zone": None}
    for w in wboxes:
        if _word_hits_class(w.get("text", ""), date_c):
            zones["date_zone"] = (w["x0"], w["x1"])
            break  # leftmost date word: the Date column
    for w in reversed(wboxes):
        if _word_hits_class(w.get("text", ""), bal_c):
            zones["balance_zone"] = (w["x0"], w["x1"])
            break  # rightmost balance word: the Balance column
    return zones


def detect_table_header(pages: List[Dict], vocab=None) -> Optional[Dict]:
    """First top-half money-free line with the required header word classes.

    Returns {"line_id", "date_zone", "balance_zone"} with x (x0, x1) zones,
    or None. Zones are None when the header line carries no word geometry.
    vocab overrides word classes + require list (per-bank, from banks.yaml).
    The top-half gate (line y0 above page midline) rejects footer legends
    carrying header words; it is order-free (no idx logic: PDF extraction
    runs bottom-first, text paths top-first). Skipped when bbox or page
    height is missing (fail-open: zones need words anyway).
    """
    vocab = vocab or {}
    date_c = tuple(vocab.get("date_words", _HEADER_DATE))
    desc_c = tuple(vocab.get("desc_words", _HEADER_DESC))
    money_c = tuple(vocab.get("money_words", _HEADER_MONEY))
    bal_c = tuple(vocab.get("balance_words", _HEADER_BAL))
    require = set(vocab.get("require", ["date", "balance", "mid"]))
    for page in pages:
        height = page.get("height")
        for line in page.get("lines", []):
            text = line.get("text", "")
            words = [w.get("text", "") for w in line.get("words", [])] or text.split()
            if not _header_words_hit(words, date_c, desc_c, money_c,
                                     bal_c, require):
                continue
            if _money_tokens(text):
                continue  # summary lines carry money; headers never do
            bbox = line.get("bbox") or []
            if len(bbox) == 4 and height:
                if bbox[1] <= height / 2:
                    continue  # footer legend, not a table header
            zones = _header_zones(line.get("words") or [],
                                        date_c, bal_c)
            return {"line_id": line.get("line_id"), **zones}
    return None


def normalize_generic_date_span(text: str, period_year=None,
                                period_end_month=None):
    """normalize_generic_date plus the match char span, or None."""
    for kind, rx in _DATE_RES:
        m = rx.search(text)
        if not m:
            continue
        try:
            if kind == "dmy_mon":
                day, mon, year = m.group(1), m.group(2), m.group(3)
            elif kind == "mdy_mon":
                mon, day, year = m.group(1), m.group(2), m.group(3)
            elif kind == "ymd":
                year, mon, day = m.group(1), m.group(2), m.group(3)
            else:
                day, mon, year = m.group(1), m.group(2), m.group(3)
            mon_i = int(mon) if mon.isdigit() else _MONTHS[mon[:3].lower()]
            day_i, year_i = int(day), int(year)
            if not (1 <= mon_i <= 12 and 1 <= day_i <= 31):
                continue
            return f"{year_i:04d}-{mon_i:02d}-{day_i:02d}", m.start(), m.end()
        except (ValueError, KeyError):
            continue
    m = _YEARLESS_RE.search(text)
    if m:
        try:
            day_i = int(m.group(1))
            mon_i = _MONTHS[m.group(2)[:3].lower()]
            year_i = _infer_year(mon_i, period_year, period_end_month)
            if year_i is not None and 1 <= day_i <= 31:
                return f"{year_i:04d}-{mon_i:02d}-{day_i:02d}", m.start(), m.end()
        except (ValueError, KeyError):
            pass
    return None


def normalize_generic_date(text: str, period_year=None,
                           period_end_month=None) -> Optional[str]:
    """First SA date in text as YYYY-MM-DD, else None.

    Year-bearing forms win; yearless day-month rows take the statement
    period year (Dec rows in a January-ending period roll back a year).
    """
    hit = normalize_generic_date_span(text, period_year, period_end_month)
    return hit[0] if hit else None


def _word_spans(words: List[Dict]):
    """[(start, end, x0, x1)] assuming single-space joins (extractor shape)."""
    spans = []
    pos = 0
    for w in words:
        token = w.get("text", "")
        spans.append((pos, pos + len(token), w.get("x0", 0.0), w.get("x1", 0.0)))
        pos += len(token) + 1
    return spans


def _word_at(spans, pos):
    for start, end, x0, x1 in spans:
        if start <= pos < end:
            return (x0, x1)
    return None


def _overlaps(a, b, tol=_ZONE_TOLERANCE_PT):
    return a[0] <= b[1] + tol and b[0] <= a[1] + tol


def _row_in_bands(line: Dict, header: Dict, dse, bse) -> bool:
    """Date + balance tokens sit in the header's x-bands (geometry only).

    dse/bse are (start, end) char spans or None; missing evidence on any
    side never rejects (single-token rows check date only).
    """
    words = line.get("words")
    if not words:
        return True
    spans = _word_spans(words)
    if header.get("date_zone") and dse is not None:
        dstart, dend = dse
        date_w = (_word_at(spans, (dstart + dend) // 2)
                  or _word_at(spans, dstart))
        if date_w and not _overlaps(date_w, header["date_zone"]):
            return False
    if header.get("balance_zone") and bse is not None:
        bstart, bend = bse
        bal_w = (_word_at(spans, (bstart + bend) // 2)
                 or _word_at(spans, bstart))
        if bal_w and not _overlaps(bal_w, header["balance_zone"]):
            return False
    return True


def _money_tokens(text: str) -> List[Tuple[str, int, int]]:
    """(token, start, end) spans that parse as SA money, left to right."""
    out = []
    for m in _MONEY_RE.finditer(text):
        tok = m.group(0).strip()
        if not tok:
            continue
        try:
            parse_sa_amount(tok)
        except ValueError:
            continue
        out.append((tok, m.start(), m.end()))
    return out


def _strip_spans(text: str, spans: List[Tuple[int, int]]) -> str:
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " + text[end:]
    return " ".join(text.split())


def _first_money(text: str) -> Optional[int]:
    toks = _money_tokens(text)
    if not toks:
        return None
    try:
        return abs(parse_sa_amount(toks[0][0]))
    except ValueError:
        return None


# Columnarity gate: x-zones only bind when balances sit in a right-aligned
# column (median right edge +-15pt holds >=70% of candidates). Flowing
# prose-like PDFs (Ubuntu shape) skip geometry; the positional rule (rows
# below the header) still applies whenever a header is found.
_COLUMNAR_MIN_N = 3
_COLUMNAR_FRAC = 0.7
_COLUMNAR_HALF_PT = 15.0


def _balance_right_edges(metas) -> List[float]:
    edges = []
    for line, _, bse in metas:
        if bse is None:
            continue
        words = line.get("words")
        if not words:
            continue
        spans = _word_spans(words)
        bstart, bend = bse
        hit = (_word_at(spans, (bstart + bend) // 2)
               or _word_at(spans, bstart))
        if hit:
            edges.append(hit[1])
    return edges


def _is_columnar(metas) -> bool:
    edges = sorted(_balance_right_edges(metas))
    if len(edges) < _COLUMNAR_MIN_N:
        return False
    median = edges[len(edges) // 2]
    inside = sum(1 for x in edges
                 if abs(x - median) <= _COLUMNAR_HALF_PT)
    return inside / len(edges) >= _COLUMNAR_FRAC


def _header_vocab(bank: Optional[str]):
    """Table-header vocab from banks.yaml; None (defaults) when unknown."""
    if bank:
        try:
            from .registry import get_bank_config
            spec = (get_bank_config(bank) or {}).get("table_header") or {}
            if spec:
                return {
                    "date_words": spec.get("date_words", ["date"]),
                    "desc_words": spec.get("desc_words", ["description"]),
                    "money_words": spec.get("money_words", ["amount"]),
                    "balance_words": spec.get("balance_words", ["balance"]),
                    "require": spec.get("require", ["date", "balance", "mid"]),
                }
        except Exception:
            pass
    return None


def band_rows(pages: List[Dict], pairs: List,
              bank: Optional[str] = None):
    """Filter (payload, (line, dse, bse)) pairs by header x-zones.

    Order-free: no idx logic anywhere (PDF extraction runs bottom-first,
    text paths top-first). Returns (kept, header, columnar); without a
    detected header everything is kept and chaining decides.
    """
    header = detect_table_header(pages, vocab=_header_vocab(bank))
    payloads = [p for p, _ in pairs]
    if header is None:
        return payloads, None, False
    columnar = _is_columnar([m for _, m in pairs])
    if not columnar:
        return payloads, header, False
    kept = [p for p, m in pairs
            if _row_in_bands(m[0], header, m[1], m[2])]
    return kept, header, True


def parse_generic_lines(pages: List[Dict], min_rows: int = 3,
                        coverage: float = 0.5) -> Optional[ExtractionResult]:
    """Generic extraction with running-balance chaining.

    Returns None below bar (caller falls through to the LLM last resort).
    Prints counts-only diagnostics like the bank-gated path.
    """
    total_lines = sum(len(p.get("lines", [])) for p in pages)
    flat = [(p.get("page_no", 1), line)
            for p in pages for line in p.get("lines", [])]
    period_year, period_end_month = _period_context(pages)

    opening = closing = None
    account_number = None
    for _, line in flat:
        text = line.get("text", "")
        low = text.lower()
        if opening is None and ("opening balance" in low
                                or "balance forward" in low
                                or "balance brought" in low):
            opening = _first_money(text)
        if "closing balance" in low or "balance carried" in low:
            closing = _first_money(text)
        if account_number is None and "account" in low:
            m = re.search(r"\b(\d[\d ]{7,12}\d)\b", text)
            if m:
                account_number = m.group(1).replace(" ", "")

    candidates = []
    metas = []  # (line, dse, bse) parallel to candidates
    for _, line in flat:
        text = line.get("text", "")
        low = text.lower()
        if "opening balance" in low or "closing balance" in low:
            continue
        hit = normalize_generic_date_span(text, period_year,
                                          period_end_month)
        if hit is None:
            continue
        date, dstart, dend = hit
        toks = _money_tokens(text)
        if len(toks) < 2:
            continue  # v1 needs amount + balance to chain
        try:
            amount = abs(parse_sa_amount(toks[-2][0]))
            balance = parse_sa_amount(toks[-1][0])
        except ValueError:
            continue
        spans = [(toks[-2][1], toks[-2][2]), (toks[-1][1], toks[-1][2])]
        for _, rx in _DATE_RES:
            dm = rx.search(text)
            if dm:
                spans.append((dm.start(), dm.end()))
                break
        desc = _strip_spans(text, spans) or "Unknown"
        candidates.append({
            "line_id": line["line_id"], "date": date, "desc": desc,
            "amount": amount, "balance": balance,
            "quote": line.get("text", "")[:200],
        })
        metas.append((line, (dstart, dend),
                      (toks[-1][1], toks[-1][2])))

    # Header banding: x-zones on columnar tables only (order-free).
    candidates, header, columnar = band_rows(
        pages, list(zip(candidates, metas)))

    rows = []
    kept = 0
    prev_bal: Optional[int] = None
    for i, cand in enumerate(candidates):
        base = None
        if i == 0 and opening is not None:
            base = opening
        elif prev_bal is not None:
            base = prev_bal
        direction = None
        if base is not None:
            if base - cand["amount"] == cand["balance"]:
                direction = "debit"
            elif base + cand["amount"] == cand["balance"]:
                direction = "credit"
        if direction is not None:
            kept += 1
            rows.append(ExtractedRow(
                line_ids=[cand["line_id"]],
                date=cand["date"],
                description=cand["desc"],
                amount_minor=cand["amount"],
                direction=direction,
                balance_after_minor=cand["balance"],
                source_quote=cand["quote"],
            ))
        if cand["balance"] is not None:
            prev_bal = cand["balance"]

    chained, total_cands = kept, len(candidates)
    if header is None:
        hdr = "hdr=-"
    else:
        hdr = f"hdr={header['line_id']}/{'col' if columnar else 'flow'}"
    if chained >= min_rows and total_cands > 0 \
            and chained / total_cands >= coverage:
        print(f"generic: lines={total_lines} cands={total_cands} "
              f"chained={chained} {hdr} -> generic")
        row_ids = {r.line_ids[0] for r in rows}
        unaccounted = [
            {"line_id": line["line_id"], "reason": "noise"}
            for _, line in flat if line["line_id"] not in row_ids
        ]
        return ExtractionResult(
            statement={"bank": "GENERIC", "account_number": account_number,
                       "period_start": None, "period_end": None,
                       "currency": "ZAR", "opening_balance": None,
                       "closing_balance": None},
            rows=rows,
            unaccounted_lines=unaccounted,
            warnings=[],
            opening_balance_minor=opening,
            closing_balance_minor=closing,
        )
    print(f"generic: lines={total_lines} cands={total_cands} "
          f"chained={chained} {hdr} below bar -> LLM fallback")
    return None
