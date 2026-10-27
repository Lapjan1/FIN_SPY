"""
Extractor orchestrator - DB-first: Extract -> persist to .db -> all products read from DB
Based on homework Part 5.6: deterministic parsers first, text-LLM fallback second, vision fallback last, balance-verification gate, per-row source coordinates
"""
from typing import List, Dict, Optional
from pathlib import Path
import hashlib
import json

from .base import ExtractionResult, Span
from .fnb import parse_fnb_lines
from ..llm.client import MetaClient, prompt_hash

def extract_text_with_bbox(pdf_path: Path) -> List[Dict]:
    """
    PyMuPDF text + words with bbox per page, line-ID numbering per AGENTS.md
    Returns pages list: [{page_no, width, height, lines: [{line_id,bbox,text,text_hash}]}]
    """
    pages = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        line_counter = 1
        for pno in range(len(doc)):
            page = doc[pno]
            width, height = page.rect.width, page.rect.height
            # Get words with bbox
            words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,word_no
            # Group words into lines by y proximity
            lines_dict = {}
            for w in words:
                x0,y0,x1,y1,word,block_no,line_no,word_no = w
                key = (block_no, line_no)
                if key not in lines_dict:
                    lines_dict[key] = []
                lines_dict[key].append((x0,y0,x1,y1,word))
            lines = []
            for (block_no, line_no), word_list in sorted(lines_dict.items()):
                word_list_sorted = sorted(word_list, key=lambda x: x[0])
                x0 = min(w[0] for w in word_list)
                y0 = min(w[1] for w in word_list)
                x1 = max(w[2] for w in word_list)
                y1 = max(w[3] for w in word_list)
                text = " ".join(w[4] for w in word_list_sorted)
                line_id = f"L{line_counter:03d}"
                line_counter += 1
                text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
                # Hidden-text detection per AGENTS.md: flag near-zero font size, white on white, outside visible area
                # For scaffold, check if bbox outside page or very small
                if x0 < 0 or y0 < 0 or x1 > width+10 or y1 > height+10:
                    # Flag hidden text
                    pass
                lines.append({"line_id": line_id, "bbox": [x0,y0,x1,y1], "text": text, "text_hash": text_hash})
            pages.append({"page_no": pno+1, "width": width, "height": height, "lines": lines})
        return pages
    except Exception as e:
        # Fallback to pdfplumber if PyMuPDF AGPL license check per LEARNINGS 2026-10-26-01
        try:
            import pdfplumber
            pages = []
            line_counter = 1
            with pdfplumber.open(str(pdf_path)) as pdf:
                for pno, page in enumerate(pdf.pages):
                    width, height = page.width, page.height
                    words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=False, use_text_flow=False)
                    # Group by top proximity
                    lines_dict = {}
                    for w in words:
                        key = round(w['top'])
                        if key not in lines_dict:
                            lines_dict[key] = []
                        lines_dict[key].append(w)
                    lines = []
                    for top, wlist in sorted(lines_dict.items()):
                        wlist_sorted = sorted(wlist, key=lambda x: x['x0'])
                        x0 = min(w['x0'] for w in wlist_sorted)
                        y0 = top
                        x1 = max(w['x1'] for w in wlist_sorted)
                        y1 = max(w['bottom'] for w in wlist_sorted)
                        text = " ".join(w['text'] for w in wlist_sorted)
                        line_id = f"L{line_counter:03d}"
                        line_counter += 1
                        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
                        lines.append({"line_id": line_id, "bbox": [x0,y0,x1,y1], "text": text, "text_hash": text_hash})
                    pages.append({"page_no": pno+1, "width": width, "height": height, "lines": lines})
            return pages
        except Exception as e2:
            raise RuntimeError(f"Both PyMuPDF and pdfplumber failed: {e} {e2}")

def deterministic_parse(pages: List[Dict], bank_hint: str = "FNB") -> Optional[ExtractionResult]:
    """
    Try deterministic parsers first in order FNB, STDB, ABSA per homework
    Returns ExtractionResult if confidence high, else None to trigger LLM fallback
    """
    # Try FNB
    try:
        result = parse_fnb_lines(pages)
        # Confidence check: if rows >= 50% of lines with dates, accept
        total_lines = sum(len(p['lines']) for p in pages)
        if len(result.rows) > 0 and len(result.rows) >= total_lines * 0.1:  # 10% threshold for scaffold
            return result
    except Exception as e:
        pass
    # TODO: STDB, ABSA parsers per 25+ adaptors reference
    return None

def llm_fallback(pages: List[Dict], model_id: str = "muse-spark-1.1") -> ExtractionResult:
    """
    LLM fallback with line-ID grounding per prompts/extract_sa_bank_v1.md
    Front-loaded rules, untrusted page data delimited, schema enforced, refusal/unknown allowed, no tools
    """
    # Build numbered lines
    numbered_lines = []
    for page in pages:
        for line in page['lines']:
            numbered_lines.append(f"{line['line_id']} | Page {page['page_no']} | {line['text']} | bbox {line['bbox']}")

    prompt_path = Path("prompts/extract_sa_bank_v1.md")
    prompt_template = prompt_path.read_text() if prompt_path.exists() else "Extract transactions from lines: {{PAGE_LINES}}"
    prompt_text = prompt_template.replace("{{PAGE_LINES}}", "\n".join(numbered_lines[:200]))  # Limit to 200 lines for cost guard per config/models.yaml per_document_token_ceiling 15000

    client = MetaClient(provider="freellmapi" if model_id=="muse-spark-1.1" else "meta_official", model_id=model_id)
    messages = [
        {"role": "system", "content": "You are a forensic bank statement extractor for South African banks. Follow priority rules never invent, amounts decimal strings, every line accounted or noise, quote check, reconciliation integrity."},
        {"role": "user", "content": prompt_text}
    ]

    # For scaffold, return mock with quote validation
    # Real call: result = client.complete(messages, response_schema=extraction_schema, effort="medium")
    # Validate schema, quote exists, line IDs exist, all lines accounted
    # For now, mock 1 row per page as fallback
    from .base import ExtractedRow
    rows = []
    for page in pages[:1]:
        for line in page['lines'][:2]:
            # Mock row citing line_id
            rows.append(ExtractedRow(
                line_ids=[line['line_id']],
                date="2026-10-26",
                description="LLM Fallback Mock",
                amount_minor=10000,
                direction="debit",
                balance_after_minor=None,
                source_quote=line['text'][:100]
            ))

    return ExtractionResult(
        statement={"bank": None, "account_mask": None, "period_start": None, "period_end": None, "currency": "ZAR", "opening_balance": None, "closing_balance": None},
        rows=rows,
        unaccounted_lines=[{"line_id": l['line_id'], "reason": "noise"} for p in pages for l in p['lines'][2:][:2]],
        warnings=["LLM fallback mock - implement real Meta call"],
        opening_balance_minor=None,
        closing_balance_minor=None
    )

def extract_document(pdf_path: Path, bank_hint: str = "FNB") -> ExtractionResult:
    """
    Main entry: intake -> text+bbox -> deterministic -> LLM fallback -> validate -> persist
    DB-first: result should be persisted to source_spans/transactions before returning
    """
    pages = extract_text_with_bbox(pdf_path)
    # Deterministic first
    result = deterministic_parse(pages, bank_hint)
    if result is None:
        # LLM fallback
        result = llm_fallback(pages, model_id="muse-spark-1.1")

    # Validation per AGENTS.md: schema, line IDs exist, quote exists, page coverage, reconciliation gate
    # Schema validation
    try:
        import json
        schema_path = Path("packages/schemas/extraction_response.json")
        if schema_path.exists():
            # TODO: validate with jsonschema
            pass
    except:
        pass

    # Quote check: source_quote must be substring of cited lines
    line_map = {line['line_id']: line['text'] for page in pages for line in page['lines']}
    for row in result.rows:
        cited_text = " ".join([line_map.get(lid, "") for lid in row.line_ids])
        if row.source_quote not in cited_text:
            # In real impl, add warning or mark as hallucination
            result.warnings.append(f"Quote mismatch {row.line_ids}")

    # Page coverage check: every line accounted or noise/unreadable
    all_line_ids = set(line_map.keys())
    accounted = set()
    for row in result.rows:
        accounted.update(row.line_ids)
    for unacc in result.unaccounted_lines:
        accounted.add(unacc['line_id'])
    if len(accounted) < len(all_line_ids) * 0.5:  # 50% threshold for scaffold
        result.warnings.append(f"Low coverage: {len(accounted)}/{len(all_line_ids)}")

    # Reconciliation gate per AGENTS.md: opening + sum = closing, running balance monotonic
    # Already in parse_fnb_lines, but re-check here
    # TODO: implement

    # Token/cost logging per homework Part 5.7 ~8-page statement 2k tokens/page in + 5.5k out = $0.045
    # TODO: log to usage_events

    return result

def persist_to_db(result: ExtractionResult, document_id: str, tenant_id: str, run_id: str):
    """
    Persist extraction result to DB per DB-first: extraction_runs + source_spans + transactions + transaction_sources
    """
    from apps.api.db import get_db
    import uuid
    db = get_db()
    # extraction_runs already created elsewhere? For scaffold, assume run_id exists
    # source_spans
    for page_no in [1]:  # Simplified
        for row in result.rows:
            span_id = f"span-{uuid.uuid4().hex[:8]}"
            # Find line
            # For scaffold, use first line_id
            line_id = row.line_ids[0] if row.line_ids else "L001"
            db.execute(
                "INSERT OR REPLACE INTO source_spans (id, tenant_id, run_id, document_id, page_no, line_id, bbox_x0, bbox_y0, bbox_x1, bbox_y1, text, text_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (span_id, tenant_id, run_id, document_id, 1, line_id, 0,0,100,10, row.source_quote, hashlib.sha256(row.source_quote.encode()).hexdigest()[:16])
            )
            # transactions
            txn_id = f"txn-{uuid.uuid4().hex[:8]}"
            # fingerprint per AGENTS.md SHA256(date|amount|desc_norm)
            from .base import fingerprint_txn
            fp = fingerprint_txn(row.date, row.amount_minor, row.description)
            db.execute(
                "INSERT OR REPLACE INTO transactions (id, tenant_id, document_id, run_id, txn_date, description_raw, amount_minor, currency, direction, balance_after_minor, fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (txn_id, tenant_id, document_id, run_id, row.date, row.description, row.amount_minor, "ZAR", row.direction, row.balance_after_minor, fp, "proposed")
            )
            # transaction_sources
            db.execute(
                "INSERT OR REPLACE INTO transaction_sources (transaction_id, span_id, role) VALUES (?,?,?)",
                (txn_id, span_id, "amount")
            )
    db.commit()
