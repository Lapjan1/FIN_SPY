"""
Base parser interface per docs - DB-first, line-ID grounding.
Reference extractor with 25+ adaptors can be READ for design, never copied per AGENTS.md.
SA formats: R prefix, space thousands, 1 234,56 comma, (450) negative, Cr/Dr suffix, dates 2026/10/25, 25 Oct, 25-10-2026
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
from decimal import Decimal

@dataclass
class Span:
    line_id: str
    bbox: List[float]  # x0,y0,x1,y1
    text: str
    text_sha256: str
    page_no: int

@dataclass
class ExtractedRow:
    line_ids: List[str]
    date: str  # YYYY-MM-DD
    description: str
    amount_minor: int  # cents, Decimal maths
    direction: str  # debit|credit
    balance_after_minor: Optional[int]
    source_quote: str  # exact match validation

@dataclass
class ExtractionResult:
    statement: Dict
    rows: List[ExtractedRow]
    unaccounted_lines: List[Dict]
    warnings: List[str]
    opening_balance_minor: Optional[int]
    closing_balance_minor: Optional[int]

def parse_sa_amount(raw: str) -> int:
    """
    Parse SA amount string to minor units (cents) using Decimal, never float.
    Handles: R1 234,56 / 1,234.56 / (450.00) / 450.00 Cr / 450- / 450 Dr
    Returns int cents.
    """
    # TODO: implement with Decimal, for scaffold return 0
    # Real impl strips R, spaces, handles comma/period, parentheses, Cr/Dr, trailing minus
    import re
    from decimal import Decimal, InvalidOperation
    s = raw.strip()
    negative = False
    if s.startswith('(') and s.endswith(')'):
        negative = True
        s = s[1:-1]
    if s.endswith('-') or s.endswith('Dr') or s.endswith('DR'):
        negative = True
        s = s.rstrip('-').rstrip('Dr').rstrip('DR').strip()
    if s.endswith('Cr') or s.endswith('CR'):
        s = s.rstrip('Cr').rstrip('CR').strip()
    s = s.replace('R','').replace('r','').replace(' ','').strip()
    # Handle SA comma decimal: 1 234,56 -> 1234.56 ; if both comma and period, assume comma thousands? Simplified:
    if ',' in s and '.' in s:
        # Use last separator as decimal
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.','').replace(',','.')
        else:
            s = s.replace(',','')
    elif ',' in s and '.' not in s:
        s = s.replace(',','.')
    try:
        dec = Decimal(s)
        if negative:
            dec = -dec
        # Convert to minor (cents) - *100
        return int((dec * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        raise ValueError(f"Cannot parse amount: {raw}")

def fingerprint_txn(date: str, amount_minor: int, desc_norm: str) -> str:
    import hashlib
    canonical = f"{date}|{amount_minor}|{desc_norm.lower().strip()}"
    return hashlib.sha256(canonical.encode()).hexdigest()
