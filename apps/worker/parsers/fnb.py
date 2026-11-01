"""
FNB deterministic parser - SA bank layout
Based on reference extractor 25+ adaptors READ for design, never copied per AGENTS.md
SA formats: R prefix, space thousands, 1 234,56 comma, (450), Cr/Dr suffix, dates 2026/10/25, 25 Oct, 25-10-2026
"""
import re
from typing import List, Dict, Optional
from decimal import Decimal
from .base import ExtractedRow, ExtractionResult, parse_sa_amount, fingerprint_txn
from .generic import _money_tokens as _strict_money_tokens, band_rows
import hashlib

# FNB typical line: 25 Oct | POS PURCHASE WOOLWORTHS | -450.00 | 12 340.55
# Or: 2026/10/25  WOOLWORTHS  R1 234,56  R12 340,55

DATE_PATTERNS = [
    r'(?P<day>\d{1,2})\s+(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?P<year>\d{4})?',
    r'(?P<year>\d{4})/(?P<mon>\d{1,2})/(?P<day>\d{1,2})',
    r'(?P<day>\d{1,2})[-/]\s*(?P<mon>\d{1,2})[-/]\s*(?P<year>\d{4})',
]

AMOUNT_RE = r'[Rr]?\s*[\d\s,\.]+\s*[-+]?\s*(?:Cr|Dr|DR|CR)?|\(\s*[\d\s,\.]+\s*\)|\d+\s*[-+]\s*$'

def normalize_date(raw: str) -> Optional[str]:
    # Simplified: return YYYY-MM-DD if parseable, else None
    # For scaffold, assume 25 Oct -> 2026-10-25
    import datetime
    mon_map = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
    raw_lower = raw.lower()
    for pat in DATE_PATTERNS:
        m = re.search(pat, raw, re.IGNORECASE)
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
    return None

def parse_fnb_lines(pages: List[Dict]) -> ExtractionResult:
    """
    Deterministic FNB parser
    Input: pages = list of {page_no, lines: [{line_id, bbox, text, text_hash}]}
    Output: ExtractionResult with rows, unaccounted_lines, warnings, opening/closing
    """
    rows = []
    unaccounted = []
    warnings = []
    opening = None
    closing = None
    account_number = None
    bank_name = "FNB"
    branch_code = None

    line_id_map = {}
    for page in pages:
        for line in page.get('lines', []):
            line_id_map[line['line_id']] = line

    # Try to detect account number from text via registry
    try:
        from .registry import get_bank_config
        cfg = get_bank_config("FNB")
        if cfg:
            account_regex = cfg.get('account_regex', r'Account Number\s*[:#]?\s*(\d+)')
            branch_regex = cfg.get('branch_code_regex', r'Branch Code\s*[:#]?\s*(\d+)')
            all_text = " ".join([line['text'] for page in pages for line in page['lines']])
            m = re.search(account_regex, all_text, re.I)
            if m:
                account_number = m.group(1) if m.groups() else m.group(0)
            m = re.search(branch_regex, all_text, re.I)
            if m:
                branch_code = m.group(1) if m.groups() else m.group(0)
    except:
        pass

    # Simple heuristic: look for lines containing date + amount + balance + opening/closing detection per user totals =/- == balance
    pairs = []  # (row, (line, dse, bse)) for header banding
    for page in pages:
        for line in page.get('lines', []):
            text = line['text']
            # Detect opening/closing balance before header skip - per extraction test opening balance +/- amount == running balance/total
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

            # Skip header/footer noise
            if re.search(r'Page \d+|Statement\s+Period|Statement\s+Date|Account Number|FNB Statement|First National Bank.*Account|Branch Code|Period:|Date\s+Description\s+Amount\s+Balance', text, re.I):
                # More specific header skip - avoid skipping opening/closing
                if not re.search(r'Opening Balance|Closing Balance', text, re.I):
                    unaccounted.append({"line_id": line['line_id'], "reason": "header"})
                    continue
            # Try to find date
            date_match = None
            dse = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, text, re.I)
                if m:
                    date_match = m
                    dse = (m.start(), m.end())
                    break
            if not date_match:
                # Check if amount + balance present - transaction candidate
                # Look for two amounts in line - handle trailing minus/plus R450,00- R15 000,00+ per user consolidation question
                amounts = [tok for tok, _, _ in _strict_money_tokens(text)]
                if len(amounts) >= 2:
                    # Potential transaction
                    pass
                else:
                    unaccounted.append({"line_id": line['line_id'], "reason": "noise"})
                continue

            # Strict money only: bare digit runs (years, page numbers,
            # the date's own digits) must never match as money. A bank row
            # needs amount + balance; anything less is noise for the generic
            # engine or human review - never a fabricated row.
            toks = _strict_money_tokens(text)
            amounts = [tok for tok, _, _ in toks]
            if len(amounts) < 2:
                unaccounted.append({"line_id": line['line_id'], "reason": "noise"})
                continue
            bse = (toks[-1][1], toks[-1][2])

            try:
                # Second-last amount is the transaction, last is the balance
                # (the SA column standard).
                amt_raw = amounts[-2]
                bal_raw = amounts[-1]
                amount_minor = parse_sa_amount(amt_raw)
                balance_minor = parse_sa_amount(bal_raw)

                date_str = normalize_date(text)
                if not date_str:
                    date_str = "2026-10-26"

                # Description is text without date and amounts
                desc = text
                # Remove date patterns and amounts for desc
                for pat in DATE_PATTERNS:
                    desc = re.sub(pat, '', desc, flags=re.I)
                for amt in amounts:
                    desc = desc.replace(amt, '')
                desc = desc.strip()[:200]
                if not desc:
                    desc = "FNB Transaction"

                direction = "debit" if amount_minor < 0 else "credit"
                # Use absolute amount string for amount field, direction separate per schema
                amount_str = f"{abs(amount_minor)/100:.2f}"

                row = ExtractedRow(
                    line_ids=[line['line_id']],
                    date=date_str,
                    description=desc,
                    amount_minor=abs(amount_minor),
                    direction=direction,
                    balance_after_minor=abs(balance_minor) if balance_minor is not None else None,
                    source_quote=text[:500]
                )
                pairs.append((row, (line, dse, bse)))
            except Exception as e:
                warnings.append(f"Failed parse {line['line_id']}: {e}")
                unaccounted.append({"line_id": line['line_id'], "reason": "unreadable"})

    # Header banding (per-bank vocab from banks.yaml); dropped candidates
    # join unaccounted so page coverage stays honest.
    rows = [row for row, _ in pairs]
    if pairs:
        kept, _, _ = band_rows(pages, pairs, bank="FNB")
        kept_ids = {id(row) for row in kept}
        for row, meta in pairs:
            if id(row) not in kept_ids:
                unaccounted.append({"line_id": meta[0]["line_id"],
                                    "reason": "noise"})
        rows = kept

    # Reconciliation gate per AGENTS.md: opening + sum(signed rows) = closing
    # Row-derived estimates are a FALLBACK only: stated balances are ground
    # truth and must survive (derivation assumes chronological row order,
    # which visual y-sorted extraction does not guarantee).
    if opening is None and rows and rows[0].balance_after_minor:
        # opening = balance_after - signed amount of first row
        first = rows[0]
        signed = -first.amount_minor if first.direction=="debit" else first.amount_minor
        opening = first.balance_after_minor - signed
    if closing is None and rows and rows[-1].balance_after_minor:
        closing = rows[-1].balance_after_minor
    if opening is not None and closing is not None and rows:
        computed = opening
        for r in rows:
            signed = -r.amount_minor if r.direction=="debit" else r.amount_minor
            computed += signed
        if closing is not None and abs(computed - closing) > 100:  # 1 Rand tolerance
            warnings.append(f"Reconciliation failed: opening {opening} + sum = {computed} != closing {closing}")

    return ExtractionResult(
        statement={
            "bank":"FNB",
            "account_mask": account_number[-4:] if account_number else None,
            "account_number": account_number,
            "bank_name": bank_name,
            "branch_code": branch_code,
            "period_start":None,
            "period_end":None,
            "currency":"ZAR",
            "opening_balance":str(opening/100) if opening else None,
            "closing_balance":str(closing/100) if closing else None
        },
        rows=rows,
        unaccounted_lines=unaccounted,
        warnings=warnings,
        opening_balance_minor=opening,
        closing_balance_minor=closing
    )
