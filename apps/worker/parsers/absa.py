"""
Absa Bank deterministic parser - SA bank layout
Based on config/banks.yaml deviations: parentheses negative (450.00), space thousands dot decimal, DD/MM/YYYY common
"""
import re
from typing import List, Dict
from .base import ExtractedRow, ExtractionResult, parse_sa_amount
from .generic import _money_tokens as _strict_money_tokens, band_rows

DATE_PATTERNS = [
    r'(?P<day>\d{1,2})/(?P<mon>\d{1,2})/(?P<year>\d{4})',  # DD/MM/YYYY common for Absa
    r'(?P<year>\d{4})/(?P<mon>\d{1,2})/(?P<day>\d{1,2})',
    r'(?P<day>\d{1,2})\s+(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
]

def normalize_date_absa(raw: str) -> str:
    import datetime
    mon_map = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
    for pat in DATE_PATTERNS:
        m = re.search(pat, raw, re.I)
        if m:
            try:
                d = m.groupdict()
                day = int(d.get('day',1))
                mon_raw = d.get('mon','')
                if mon_raw.isdigit():
                    mon = int(mon_raw)
                else:
                    mon = mon_map.get(mon_raw[:3].lower(), 10)
                year = int(d.get('year') or 2026)
                return f"{year:04d}-{mon:02d}-{day:02d}"
            except:
                continue
    return "2026-10-26"

def parse_absa_lines(pages: List[Dict]) -> ExtractionResult:
    rows = []
    unaccounted = []
    warnings = []
    opening = None
    closing = None

    pairs = []  # (row, (line, dse, bse)) for header banding
    for page in pages:
        for line in page.get('lines', []):
            text = line['text']

            if re.search(r'Opening Balance', text, re.I):
                amounts = [tok for tok, _, _ in _strict_money_tokens(text)]
                if amounts:
                    try:
                        opening = parse_sa_amount(amounts[-1])
                        unaccounted.append({"line_id": line['line_id'], "reason": "opening_balance"})
                        continue
                    except:
                        pass
            if re.search(r'Closing Balance', text, re.I):
                amounts = [tok for tok, _, _ in _strict_money_tokens(text)]
                if amounts:
                    try:
                        closing = parse_sa_amount(amounts[-1])
                        unaccounted.append({"line_id": line['line_id'], "reason": "closing_balance"})
                        continue
                    except:
                        pass

            if re.search(r'Page \d+|Statement\s+Period|Statement\s+Date|Account Number|Absa|Branch Code|Period:', text, re.I):
                if not re.search(r'Opening Balance|Closing Balance', text, re.I):
                    unaccounted.append({"line_id": line['line_id'], "reason": "header"})
                    continue

            date_match = None
            dse = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, text, re.I)
                if m:
                    date_match = True
                    dse = (m.start(), m.end())
                    break
            if not date_match:
                unaccounted.append({"line_id": line['line_id'], "reason": "noise"})
                continue

            toks = _strict_money_tokens(text)
            amounts = [tok for tok, _, _ in toks]
            if len(amounts) < 2:
                unaccounted.append({"line_id": line['line_id'], "reason": "noise"})
                continue

            try:
                amt_raw = amounts[-2]
                bal_raw = amounts[-1]
                amount_minor = parse_sa_amount(amt_raw)
                balance_minor = parse_sa_amount(bal_raw)
                bse = (toks[-1][1], toks[-1][2])

                date_str = normalize_date_absa(text)
                desc = text
                for pat in DATE_PATTERNS:
                    desc = re.sub(pat, '', desc, flags=re.I)
                for amt in amounts:
                    desc = desc.replace(amt, '')
                desc = desc.strip()[:200] or "ABSA Transaction"

                direction = "debit" if amount_minor < 0 else "credit"

                pairs.append((ExtractedRow(
                    line_ids=[line['line_id']],
                    date=date_str,
                    description=desc,
                    amount_minor=abs(amount_minor),
                    direction=direction,
                    balance_after_minor=abs(balance_minor) if balance_minor else None,
                    source_quote=text[:500]
                ), (line, dse, bse)))
            except Exception as e:
                warnings.append(f"Failed parse {line['line_id']}: {e}")
                unaccounted.append({"line_id": line['line_id'], "reason": "unreadable"})

    # Header banding (per-bank vocab from banks.yaml); dropped candidates
    # join unaccounted so page coverage stays honest.
    rows = [row for row, _ in pairs]
    if pairs:
        kept, _, _ = band_rows(pages, pairs, bank="ABSA")
        kept_ids = {id(row) for row in kept}
        for row, meta in pairs:
            if id(row) not in kept_ids:
                unaccounted.append({"line_id": meta[0]["line_id"],
                                    "reason": "noise"})
        rows = kept

    return ExtractionResult(
        statement={"bank":"ABSA","account_mask":None,"period_start":None,"period_end":None,"currency":"ZAR","opening_balance":str(opening/100) if opening else None,"closing_balance":str(closing/100) if closing else None},
        rows=rows,
        unaccounted_lines=unaccounted,
        warnings=warnings,
        opening_balance_minor=opening,
        closing_balance_minor=closing
    )
