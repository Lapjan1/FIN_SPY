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
# Spaces inside a token are allowed only as thousands separators (a space
# NOT followed by 3-digits-then-separator ends the token), so adjacent
# bare amounts never fuse into one invalid token. R must not start
# mid-word (SPAR must not donate its R to the amount).
_MID = r"(?:[\d,\.]|\s(?=\d{3}(?:\s\d{3})*[,\.]))*"
_MONEY_RE = re.compile(
    r"\(\s*R?\s*\d" + _MID + r"[,\.]\d{2}\s*\)"  # (1 234,56)
    r"|(?<![A-Za-z])R\s*\d" + _MID + r"[,\.]\d{2}\s*[-+]?\s*(?:[Cc][Rr]|[Dd][Rr])?"
    r"|\d" + _MID + r"[,\.]\d{2}\s*[-+]?\s*(?:[Cc][Rr]|[Dd][Rr])?"
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


def normalize_generic_date(text: str, period_year=None,
                           period_end_month=None) -> Optional[str]:
    """First SA date in text as YYYY-MM-DD, else None.

    Year-bearing forms win; yearless day-month rows take the statement
    period year (Dec rows in a January-ending period roll back a year).
    """
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
            return f"{year_i:04d}-{mon_i:02d}-{day_i:02d}"
        except (ValueError, KeyError):
            continue
    m = _YEARLESS_RE.search(text)
    if m:
        try:
            day_i = int(m.group(1))
            mon_i = _MONTHS[m.group(2)[:3].lower()]
            year_i = _infer_year(mon_i, period_year, period_end_month)
            if year_i is not None and 1 <= day_i <= 31:
                return f"{year_i:04d}-{mon_i:02d}-{day_i:02d}"
        except (ValueError, KeyError):
            pass
    return None


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
    for _, line in flat:
        text = line.get("text", "")
        low = text.lower()
        if "opening balance" in low or "closing balance" in low:
            continue
        date = normalize_generic_date(text, period_year,
                                      period_end_month)
        if date is None:
            continue
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
    if chained >= min_rows and total_cands > 0 \
            and chained / total_cands >= coverage:
        print(f"generic: lines={total_lines} cands={total_cands} "
              f"chained={chained} -> generic")
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
          f"chained={chained} below bar -> LLM fallback")
    return None
