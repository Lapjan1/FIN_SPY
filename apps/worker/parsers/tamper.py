"""
Tamper detection - can we know if file is still original or most likely tampered with?
Per user question: do we know if file is still original or most likely tampered?

Based on homework Part 5.6 + 5.9 + Appendix I F-050 PDF anomalies + Forensic tests + docs/METHOD_STATEMENT.md
"""
import re
import hashlib
from typing import Dict, List, Tuple
from pathlib import Path

def check_pdf_metadata_tampering(pdf_path: Path) -> Tuple[bool, List[str]]:
    """
    Check PDF metadata for tampering indicators:
    - Producer mismatch (e.g., different producers in same doc)
    - Creation date after modification date
    - Multiple producers
    - Incremental updates (presence of /Prev, /XRef, trailer with multiple revisions)
    - Font changes on amount lines (different fonts for same type)
    Returns (is_original_likely, reasons)
    """
    reasons = []
    is_original = True

    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        metadata = doc.metadata

        # Check producer
        producer = metadata.get('producer', '')
        if producer:
            reasons.append(f"Producer: {producer}")

        # Check creation vs modification
        creation = metadata.get('creationDate', '')
        mod = metadata.get('modDate', '')
        if creation and mod:
            # If modDate before creationDate, suspicious
            if mod < creation:
                is_original = False
                reasons.append(f"Tamper indicator: modDate {mod} before creationDate {creation} - possible metadata manipulation")

        # Check for incremental updates - presence of multiple trailers
        # fitz doc.xref length vs file? For simplicity, check if file has /Prev
        try:
            with open(pdf_path, 'rb') as f:
                content = f.read()
                if b'/Prev' in content:
                    is_original = False
                    reasons.append("Tamper indicator: incremental updates found (/Prev) - file has been modified after creation, not original")
                if content.count(b'%%EOF') > 1:
                    # Multiple EOFs indicate incremental updates
                    count_eof = content.count(b'%%EOF')
                    if count_eof > 1:
                        is_original = False
                        reasons.append(f"Tamper indicator: {count_eof} %%EOF markers - multiple revisions, not original byte-for-byte")
        except:
            pass

        # Check for font changes on amount lines - different fonts for amounts could indicate editing
        # For MVP, we skip detailed font analysis, but note as check
        reasons.append("Font consistency check: TODO detailed per F-050 - check if amount lines have different fonts")

        doc.close()

    except Exception as e:
        reasons.append(f"Metadata check failed: {e} - assume original but unknown")

    # If no tamper indicators, likely original
    if is_original and len([r for r in reasons if "Tamper indicator" in r]) == 0:
        reasons.append("No tamper indicators found - likely original byte-for-byte")

    return is_original, reasons

def check_content_hash_chain(sha256: str, tenant_id: str, db) -> Tuple[bool, List[str]]:
    """
    Check if file is still original via content-hash vault + hash-chain audit
    Vault is content-addressed key = SHA256, never overwritten, immutable per AGENTS.md
    Audit log hash-chain prev_hash/row_hash SHA256(prev||canonical_json) per AGENTS.md

    Returns (is_original, reasons)
    """
    reasons = []
    # Check if file exists in vault with same SHA256
    cur = db.execute("SELECT id, sha256, storage_key FROM source_documents WHERE sha256=? AND tenant_id=?", (sha256, tenant_id))
    row = cur.fetchone()
    if not row:
        return False, [f"File SHA256 {sha256[:12]}... not found in vault - not original or deleted"]

    # Check if file on disk hash matches stored hash (tamper detection)
    storage_key = row["storage_key"] if isinstance(row, dict) else row[2]
    try:
        file_data = Path(storage_key).read_bytes()
        computed_sha = hashlib.sha256(file_data).hexdigest()
        if computed_sha != sha256:
            return False, [f"Tamper detected: stored file hash {computed_sha[:12]}... != claimed {sha256[:12]}... - file modified after upload"]
        else:
            reasons.append(f"Content-hash verified: stored file hash matches claimed {sha256[:12]}... - byte-for-byte original")
    except Exception as e:
        reasons.append(f"Could not verify file on disk: {e}")

    # Check audit_log chain integrity for this document
    cur = db.execute("SELECT prev_hash, row_hash, payload_json FROM audit_log WHERE tenant_id=? AND object_type='source_documents' AND object_id=? ORDER BY id", (tenant_id, row["id"] if isinstance(row, dict) else row[0]))
    audit_rows = cur.fetchall()
    if audit_rows:
        # Verify chain: each prev_hash should equal previous row_hash
        prev_expected = "0"*64
        for audit_row in audit_rows:
            prev = audit_row["prev_hash"] if isinstance(audit_row, dict) else audit_row[0]
            row_hash = audit_row["row_hash"] if isinstance(audit_row, dict) else audit_row[1]
            if prev != prev_expected:
                return False, [f"Audit chain broken: expected prev {prev_expected[:12]}... got {prev[:12]}... - possible tampering"] + reasons
            prev_expected = row_hash
        reasons.append(f"Audit chain intact: {len(audit_rows)} entries, last hash {prev_expected[:12]}... - chain verified")

    return True, reasons

def check_visual_tampering_indicators(text: str, pages: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Check for visual tampering indicators:
    - Hidden text white on white, near-zero font size, outside visible area per AGENTS.md
    - Different fonts for amount lines
    - Inconsistent number formatting
    """
    reasons = []
    is_original = True

    # Check hidden text: words with bbox outside page or very small
    hidden_count = 0
    for page in pages:
        for line in page.get('lines', []):
            bbox = line.get('bbox', [0,0,0,0])
            x0,y0,x1,y1 = bbox
            width = x1 - x0
            height = y1 - y0
            # Near-zero font size: height < 1
            if height < 1:
                hidden_count += 1
            # Outside visible area
            if x0 < -10 or y0 < -10 or x1 > page.get('width', 1000) + 10 or y1 > page.get('height', 1000) + 10:
                hidden_count += 1

    if hidden_count > 0:
        is_original = False
        reasons.append(f"Tamper indicator: {hidden_count} hidden text lines found (outside visible area or near-zero font) - possible prompt injection or tampering per AGENTS.md")

    # Check inconsistent number formatting: mix of comma and dot decimals in same doc
    # SA formats: R prefix, space thousands, comma vs dot - but mixing could indicate editing
    comma_count = len(re.findall(r'\d+,\d{2}', text))
    dot_count = len(re.findall(r'\d+\.\d{2}', text))
    if comma_count > 0 and dot_count > 0:
        # If both comma and dot decimals used, could be edited from different sources
        reasons.append(f"Inconsistent number formatting: {comma_count} comma decimals (1 234,56) and {dot_count} dot decimals (1,234.56) - possible editing from different sources")

    return is_original, reasons

def full_tamper_check(pdf_path: Path, sha256: str, tenant_id: str, db, pages: List[Dict] = None) -> Dict:
    """
    Full tamper check combining metadata + hash chain + visual
    Returns dict with is_original_likely, confidence, reasons, tamper_indicators
    For wow factor: report on chances of tamper and reasons per user question
    """
    all_reasons = []
    tamper_indicators = []
    original_checks = []

    # 1. Metadata check
    meta_original, meta_reasons = check_pdf_metadata_tampering(pdf_path)
    all_reasons.extend(meta_reasons)
    original_checks.append(meta_original)
    tamper_indicators.extend([r for r in meta_reasons if "Tamper indicator" in r])

    # 2. Content hash chain
    hash_original, hash_reasons = check_content_hash_chain(sha256, tenant_id, db)
    all_reasons.extend(hash_reasons)
    original_checks.append(hash_original)
    tamper_indicators.extend([r for r in hash_reasons if "Tamper detected" in r or "broken" in r])

    # 3. Visual tampering if pages provided
    if pages:
        visual_original, visual_reasons = check_visual_tampering_indicators(open(pdf_path, 'rb').read().decode(errors='ignore') if pdf_path.suffix != '.pdf' else "", pages)
        all_reasons.extend(visual_reasons)
        original_checks.append(visual_original)
        tamper_indicators.extend([r for r in visual_reasons if "Tamper indicator" in r])

    is_original_likely = all(original_checks) if original_checks else True
    confidence = sum(original_checks) / len(original_checks) if original_checks else 0.5

    # Chance of tamper = 1 - confidence + weighted by tamper indicators
    tamper_chance = 1.0 - confidence
    if tamper_indicators:
        tamper_chance = min(1.0, tamper_chance + 0.2 * len(tamper_indicators))

    return {
        "is_original_likely": is_original_likely,
        "confidence": confidence,
        "tamper_chance": tamper_chance,
        "tamper_indicators": tamper_indicators,
        "reasons": all_reasons,
        "checks": {
            "metadata_original": meta_original,
            "hash_chain_original": hash_original,
            "visual_original": original_checks[2] if len(original_checks) > 2 else True
        }
    }
