"""
Bank statement classifier - can our intake know when PDF or any file is a bank statement?
Per user question: First things first - intake detection

Based on homework Part 5.6 SA specifics + forensic tests F-050 PDF anomalies
"""
import re
from typing import Dict, List, Tuple
from pathlib import Path

BANK_KEYWORDS = [
    "FNB", "First National Bank", "Standard Bank", "STDB", "Absa", "Nedbank", "Capitec",
    "Bank Statement", "Statement", "Account Number", "Account No", "Branch Code",
    "Opening Balance", "Closing Balance", "Balance", "Transaction", "Date", "Description", "Amount",
    "Credit", "Debit", "ZAR", "Rand", "R ", "Cheque", "Savings", "Current Account"
]

SA_BANK_PATTERNS = [
    r'FNB|First National Bank',
    r'Standard Bank|STDB',
    r'ABSA',
    r'Nedbank',
    r'Capitec',
    r'Account (Number|No)\s*[:#]?\s*\d+',
    r'Branch Code\s*[:#]?\s*\d+',
    r'Opening Balance|Closing Balance',
    r'Statement.*Period|Period.*Statement',
]

NON_BANK_INDICATORS = [
    r'^%PDF',  # PDF header, but not bank
    r'Invoice|Receipt|Quote|Order|Purchase Order',
    r'\.jpg$|\.jpeg$|\.png$|\.gif$|\.bmp$',
    r'Image|Picture|Photo',
]

def is_bank_statement(text: str, filename: str = "", mime: str = "") -> Tuple[bool, float, List[str]]:
    """
    Determine if file is likely a bank statement
    Returns (is_bank_statement, confidence 0-1, reasons)
    """
    reasons = []
    score = 0
    max_score = 0

    text_lower = text.lower()
    filename_lower = filename.lower()

    # Check mime and extension - PDFs and CSVs more likely bank statements
    if mime in ("application/pdf", "text/csv", "application/vnd.ms-excel") or filename_lower.endswith(('.pdf','.csv','.ofx')):
        score += 1
        reasons.append(f"mime/extension {mime}/{filename} likely bank statement")
    max_score += 1

    # Check bank keywords
    bank_matches = 0
    for kw in BANK_KEYWORDS:
        if kw.lower() in text_lower:
            bank_matches += 1
    if bank_matches >= 3:
        score += 2
        reasons.append(f"Found {bank_matches} bank keywords")
    elif bank_matches >= 1:
        score += 1
        reasons.append(f"Found {bank_matches} bank keywords")
    max_score += 2

    # Check SA bank patterns regex
    pattern_matches = 0
    for pat in SA_BANK_PATTERNS:
        if re.search(pat, text, re.I):
            pattern_matches += 1
    if pattern_matches >= 2:
        score += 2
        reasons.append(f"Found {pattern_matches} SA bank patterns")
    max_score += 2

    # Check for transaction-like structure: dates + amounts + balances
    date_count = len(re.findall(r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)|\d{4}/\d{1,2}/\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}', text, re.I))
    amount_count = len(re.findall(r'R?\s*\d[\d\s,\.]*\s*(?:Cr|Dr)?|\(\s*[\d\s,\.]+\s*\)', text))
    if date_count >= 3 and amount_count >= 3:
        score += 2
        reasons.append(f"Found transaction structure: {date_count} dates, {amount_count} amounts")
    max_score += 2

    # Check for opening/closing balance
    if re.search(r'Opening Balance|Closing Balance', text, re.I):
        score += 1
        reasons.append("Found opening/closing balance")
    max_score += 1

    # Penalize non-bank indicators
    non_bank_score = 0
    for pat in NON_BANK_INDICATORS:
        if re.search(pat, text, re.I) or re.search(pat, filename, re.I):
            # Check if invoice/receipt - could be bank? But if invoice and also bank keywords, keep
            if "invoice" in pat.lower() and bank_matches >= 2:
                continue  # Might be bank statement that mentions invoice
            non_bank_score += 1
    if non_bank_score >= 2:
        score = max(0, score - 1)
        reasons.append(f"Found {non_bank_score} non-bank indicators - penalize")

    confidence = score / max_score if max_score > 0 else 0
    is_bank = confidence >= 0.5  # Threshold 0.5

    return is_bank, confidence, reasons

def is_duplicate_file(sha256: str, tenant_id: str, db) -> Tuple[bool, str]:
    """
    Can intake know when 2 files are duplicates?
    YES: Content-hash vault SHA256 check per DB-first

    Returns (is_duplicate, existing_doc_id)
    """
    cur = db.execute("SELECT id, original_filename FROM source_documents WHERE sha256=? AND tenant_id=?", (sha256, tenant_id))
    row = cur.fetchone()
    if row:
        doc_id = row["id"] if isinstance(row, dict) else row[0]
        filename = row["original_filename"] if isinstance(row, dict) else row[1]
        return True, f"Duplicate of {doc_id} ({filename}) SHA256 {sha256[:12]}..."
    return False, ""

def is_near_duplicate_transactions(new_fingerprints: List[str], tenant_id: str, db, threshold: float = 0.8) -> Tuple[bool, List[str]]:
    """
    Near-duplicate via transaction fingerprints SHA256(date|amount|desc_norm)
    If >80% fingerprints overlap with existing transactions, likely duplicate file with different name
    """
    if not new_fingerprints:
        return False, []
    # Get existing fingerprints for tenant
    cur = db.execute("SELECT fingerprint_sha256 FROM transactions WHERE tenant_id=?", (tenant_id,))
    existing = set([r["fingerprint_sha256"] if isinstance(r, dict) else r[0] for r in cur.fetchall()])
    if not existing:
        return False, []
    overlap = len(set(new_fingerprints) & existing)
    overlap_ratio = overlap / len(new_fingerprints) if new_fingerprints else 0
    if overlap_ratio >= threshold:
        return True, [f"Overlap {overlap}/{len(new_fingerprints)} = {overlap_ratio:.0%} fingerprints"]
    return False, []

def should_exclude_from_extraction(text: str, filename: str, mime: str, is_bank: bool, confidence: float) -> Tuple[bool, str]:
    """
    Can we exclude other files from extraction?
    YES: If not bank statement with low confidence, skip extraction to save AI cost

    Returns (should_exclude, reason)
    """
    # Exclude if not bank statement and low confidence
    if not is_bank and confidence < 0.3:
        return True, f"Not bank statement - confidence {confidence:.0%} <30% - exclude to save AI cost per config/models.yaml per_document_token_ceiling 15000"

    # Exclude if image and no bank keywords (e.g., random JPG)
    if mime.startswith("image/") and confidence < 0.5:
        # Check if image is receipt/invoice image - might be bank? For MVP, exclude if low confidence
        # In future, SAM 3.1 receipt segmentation could handle receipt images
        return True, f"Image file with low bank confidence {confidence:.0%} - exclude, SAM 3.1 stretch for receipt images"

    # Exclude if file is too small (likely not bank statement)
    if len(text.strip()) < 50:
        return True, "File too small <50 chars - likely not bank statement"

    return False, ""

def classify_file_type(text: str, filename: str, mime: str) -> str:
    """
    Classify file type for intake routing
    Returns: bank_statement, csv_statement, ofx_statement, receipt_image, invoice, other
    """
    is_bank, conf, _ = is_bank_statement(text, filename, mime)
    if is_bank:
        if filename.lower().endswith('.csv'):
            return "csv_statement"
        elif filename.lower().endswith('.ofx'):
            return "ofx_statement"
        else:
            return "bank_statement"
    if filename.lower().endswith(('.jpg','.jpeg','.png')):
        # Could be receipt image for SAM 3.1
        if "receipt" in text.lower() or "invoice" in filename.lower():
            return "receipt_image"
        return "other_image"
    if "invoice" in filename.lower() or "invoice" in text.lower():
        return "invoice"
    return "other"
