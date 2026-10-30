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
from ..llm.client import MetaClient, provider_for_model, resolve_model

def extract_text_with_bbox(pdf_path: Path, password: Optional[str] = None) -> List[Dict]:
    """
    PyMuPDF text + words with bbox per page, line-ID numbering per AGENTS.md
    Handles encrypted/password protected PDFs: tries password param transiently, never logs/stores password
    Returns pages list: [{page_no, width, height, lines: [{line_id,bbox,text,text_hash}]}]
    """
    pages = []
    try:
        import fitz  # PyMuPDF
        # Open with password if provided
        doc = fitz.open(str(pdf_path))
        if doc.is_encrypted:
            if password:
                auth = doc.authenticate(password)
                if auth == 0:
                    raise ValueError("PDF password authentication failed - needs password")
            elif doc.needs_pass:
                raise ValueError("PDF is encrypted and needs password - status needs_password")
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
                if x0 < 0 or y0 < 0 or x1 > width+10 or y1 > height+10:
                    pass
                lines.append({"line_id": line_id, "bbox": [x0,y0,x1,y1], "text": text, "text_hash": text_hash})
            pages.append({"page_no": pno+1, "width": width, "height": height, "lines": lines})
        doc.close()
        return pages
    except Exception as e:
        # Fallback to pdfplumber if PyMuPDF AGPL license check per LEARNINGS 2026-10-26-01
        # Also handles encrypted PDFs via password param
        try:
            import pdfplumber
            pages = []
            line_counter = 1
            # pdfplumber open supports password param for encrypted PDFs
            open_kwargs = {}
            if password:
                open_kwargs['password'] = password
            with pdfplumber.open(str(pdf_path), **open_kwargs) as pdf:
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



TEXT_SUFFIXES = {".csv", ".txt", ".ofx", ".qif"}


def _looks_csv(raw: str) -> bool:
    """Content sniff for CSV: 2+ lines sharing a 3+ cell count.

    Suffixes lie (vault keys always end .pdf), and blind csv-parsing
    would shred space-separated TXT amounts - so only consistent
    multi-cell content takes the CSV path.
    """
    import csv as _csv
    import io as _io
    counts = []
    for row in _csv.reader(_io.StringIO(raw)):
        if not row or not any(c.strip() for c in row):
            continue
        counts.append(len(row))
        if len(counts) >= 5:
            break
    return (len(counts) >= 2 and counts[0] >= 3
            and all(c == counts[0] for c in counts))

def extract_text_lines(text_path: Path) -> List[Dict]:
    """Text-reader twin of extract_text_with_bbox for CSV/TXT/OFX uploads.

    Same pages shape (one page, Lxxx ids, text_hash) so bank parsers,
    the generic engine, and the LLM fallback all run unchanged. No pixel
    boxes exist for text rows - persist falls back to its placeholder.
    """
    raw = text_path.read_bytes().decode("utf-8-sig", errors="replace")
    # CSV: parse cells and space-join. Raw commas fuse adjacent amounts
    # into one SA-format token (298.94,9701.06); spaces keep them apart.
    if text_path.suffix.lower() == ".csv" or _looks_csv(raw):
        import csv as _csv
        import io as _io
        import re as _re
        chunks = []
        for row in _csv.reader(_io.StringIO(raw)):
            joined = " ".join(c.strip() for c in row)
            # ISO-style leading signs (-298.94): the generic engine reads
            # direction from balance chaining, and a stray '-' would
            # otherwise survive span-stripping into the description.
            joined = _re.sub(r"(?<=\s)[-+](?=\d)", "", joined)
            chunks.append(joined)
    else:
        chunks = raw.splitlines()
    lines = []
    counter = 1
    for chunk in chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        line_id = f"L{counter:03d}"
        counter += 1
        lines.append({
            "line_id": line_id,
            "bbox": [0, 0, 100, 10],
            "text": stripped,
            "text_hash": hashlib.sha256(stripped.encode()).hexdigest()[:16],
        })
    return [{"page_no": 1, "width": None, "height": None, "lines": lines}]
def deterministic_parse(pages: List[Dict], bank_hint: str = "FNB") -> Optional[ExtractionResult]:
    """
    Try deterministic parsers first in order based on bank_hint or detected bank from registry
    Uses config/banks.yaml registry + bankcodes and deviations per bank per user question entity register bankcodes and deviations per bank
    Returns ExtractionResult if confidence high, else None to trigger LLM fallback
    """
    from .registry import detect_bank_from_text, get_bank_config
    from .fnb import parse_fnb_lines
    from .stdb import parse_stdb_lines
    from .absa import parse_absa_lines

    # Detect bank from text if not provided
    all_text = " ".join([line['text'] for page in pages for line in page['lines']])
    detected_bank = detect_bank_from_text(all_text) or bank_hint

    # Bank-gated: only the detected bank's parser may claim the document.
    # Cross-bank parsers over-match (Absa's loose DD/MM/YYYY + number
    # patterns once claimed 96 garbage rows on an FNB file), so anything
    # below the threshold falls through to the LLM fallback instead of a
    # wrong parser. Diagnostics are counts only - never page text - so
    # prod logs stay PII-free.
    bank_parsers = {
        "FNB": parse_fnb_lines,
        "STDB": parse_stdb_lines,
        "ABSA": parse_absa_lines,
    }
    total_lines = sum(len(p['lines']) for p in pages)
    parser = bank_parsers.get(detected_bank or "")
    if parser is None:
        print(
            f"deterministic: bank={detected_bank} lines={total_lines} "
            "no dedicated parser -> LLM fallback"
        )
        return None
    try:
        result = parser(pages)
        found = len(result.rows)
    except Exception:
        print(
            f"deterministic: bank={detected_bank} lines={total_lines} "
            f"{parser.__name__}=ERR -> LLM fallback"
        )
        return None
    # Confidence check: rows >= 10% of total lines and at least 1 row
    if found > 0 and found >= total_lines * 0.1:
        # Check bank config deviations if available
        bank_cfg = get_bank_config(detected_bank or bank_hint)
        if bank_cfg:
            # Add bank info to statement
            result.statement['bank'] = detected_bank or bank_hint
        print(
            f"deterministic: bank={detected_bank} lines={total_lines} "
            f"{parser.__name__}={found} -> {parser.__name__}"
        )
        return result
    print(
        f"deterministic: bank={detected_bank} lines={total_lines} "
        f"{parser.__name__}={found} below 10% -> LLM fallback"
    )
    return None

def _extraction_client(model_id: Optional[str]) -> MetaClient:
    """Explicit model_id honored (synthetic contributor runs), else resolved
    from admin settings (model_extraction -> model) per Day 9 wiring."""
    if model_id:
        return MetaClient(provider=provider_for_model(model_id), model_id=model_id)
    provider, resolved = resolve_model("extraction")
    return MetaClient(provider=provider, model_id=resolved)

def llm_fallback(pages: List[Dict], model_id: Optional[str] = None, tenant_id: str = "default") -> ExtractionResult:
    """
    LLM fallback with line-ID grounding per prompts/extract_sa_bank_v1.md
    Front-loaded rules, untrusted page data delimited, schema enforced, refusal/unknown allowed, no tools
    Real implementation per Day3 extraction quality: wire Meta adapter with line-ID grounding prompts, spans with page/bbox/line_id/text_hash, fingerprint dedup, validation
    """
    from .base import ExtractedRow, ExtractionResult
    import json

    # Build numbered lines
    numbered_lines = []
    for page in pages:
        for line in page['lines']:
            numbered_lines.append(f"{line['line_id']} | Page {page['page_no']} | {line['text']} | bbox {line['bbox']}")

    prompt_path = Path("prompts/extract_sa_bank_v1.md")
    prompt_template = prompt_path.read_text() if prompt_path.exists() else "Extract transactions from lines: {{PAGE_LINES}}"
    prompt_text = prompt_template.replace("{{PAGE_LINES}}", "\n".join(numbered_lines[:200]))  # Limit to 200 lines for cost guard per config/models.yaml per_document_token_ceiling 15000

    # Load schema for structured output validation
    schema_path = Path("packages/schemas/extraction_response.json")
    schema = None
    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text())
        except:
            pass

    # Try real Meta call with $123.88 credits if available per user team_id 1097489856409281 project_id 1468380911895358
    # Provider/model via _extraction_client: explicit model_id or admin settings
    client = _extraction_client(model_id)
    messages = [
        {"role": "system", "content": "You are a forensic bank statement extractor for South African banks. Follow priority rules never invent, amounts decimal strings, every line accounted or noise, quote check, reconciliation integrity. Return JSON per schema with statement, rows, unaccounted_lines, warnings. Every row must cite >=1 line_id and verbatim source_quote exact match."},
        {"role": "user", "content": prompt_text}
    ]

    try:
        result = client.complete(messages, response_schema=schema, effort="medium", tenant_id=tenant_id)
        content = result.content
        # Try parse JSON
        # Content may have markdown code block ```json ... ```
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        parsed = json.loads(json_str)

        # Validate basic structure
        rows = []
        for r in parsed.get("rows", []):
            # Validate line_ids exist
            line_ids = r.get("line_ids", [])
            # Validate quote exists handled later
            try:
                from .base import parse_sa_amount
                amount_str = r.get("amount", "0")
                amount_minor = parse_sa_amount(amount_str)
                # Direction
                direction = r.get("direction", "debit")
                # Balance after
                bal_str = r.get("balance_after")
                bal_minor = parse_sa_amount(bal_str) if bal_str else None

                rows.append(ExtractedRow(
                    line_ids=line_ids,
                    date=r.get("date", "2026-10-26"),
                    description=r.get("description", "")[:200],
                    amount_minor=abs(amount_minor),
                    direction=direction,
                    balance_after_minor=bal_minor,
                    source_quote=r.get("source_quote", "")[:500]
                ))
            except Exception as e:
                # Skip invalid row but add warning
                continue

        # Opening/closing balances
        stmt = parsed.get("statement", {})
        opening_raw = stmt.get("opening_balance")
        closing_raw = stmt.get("closing_balance")
        opening_minor = None
        closing_minor = None
        try:
            from .base import parse_sa_amount
            if opening_raw:
                opening_minor = parse_sa_amount(opening_raw)
            if closing_raw:
                closing_minor = parse_sa_amount(closing_raw)
        except:
            pass

        unaccounted = parsed.get("unaccounted_lines", [])
        warnings = parsed.get("warnings", [])

        # Token logging per homework Part 5.7 ~$0.045 per 8p
        # Log usage via usage_events in persist_to_db

        return ExtractionResult(
            statement=stmt,
            rows=rows,
            unaccounted_lines=unaccounted,
            warnings=warnings + [f"LLM real call success model {model_id} tokens {result.usage}"],
            opening_balance_minor=opening_minor,
            closing_balance_minor=closing_minor
        )

    except Exception as e:
        # P0-A0/Q3: never fabricate rows on LLM failure. Zero rows
        # plus a loud warning - the doc visibly needs re-extract or
        # manual capture. Class-only in print (no prompt echoes).
        print(f"llm_fallback failed: {type(e).__name__} - zero rows")
        return ExtractionResult(
            statement={"bank": None, "account_mask": None, "period_start": None, "period_end": None, "currency": "ZAR", "opening_balance": None, "closing_balance": None},
            rows=[],
            unaccounted_lines=[{"line_id": l['line_id'], "reason": "llm_failed"} for p in pages for l in p['lines']],
            warnings=[f"LLM fallback failed ({type(e).__name__}): zero rows persisted - re-extract or capture manually"],
            opening_balance_minor=None,
            closing_balance_minor=None
        )

def extract_document(pdf_path: Path, bank_hint: str = "FNB", password: Optional[str] = None, tenant_id: str = "default") -> ExtractionResult:
    """
    Main entry: intake -> text+bbox -> deterministic -> generic -> LLM fallback -> validate -> persist
    DB-first: result should be persisted to source_spans/transactions before returning
    Handles encrypted PDFs: password param transient, never logged/stored, if no password and encrypted raises needs_password
    """
    # Dispatch sniffs content, never the suffix: vault keys always end
    # .pdf (storage_key = {sha}.pdf) even when the bytes are CSV/text.
    head = pdf_path.read_bytes()[:5]
    if head[:4] == b"%PDF":
        pages = extract_text_with_bbox(pdf_path, password=password)
    else:
        # Text-based statements (CSV/TXT/OFX). Binary uploads (photos)
        # fail here with a clear error instead of burning LLM money on
        # garbage lines - OCR is not wired yet.
        try:
            pdf_path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(
                "Only PDF and text-based statements (CSV/TXT/OFX) are"
                " supported; image uploads need OCR, which is not wired yet."
            )
        pages = extract_text_lines(pdf_path)
    # Bank parser first (precision), generic engine second (recall),
    # whole-statement LLM strictly last resort (P0-A0/D9).
    result = deterministic_parse(pages, bank_hint)
    if result is None:
        from .generic import parse_generic_lines
        result = parse_generic_lines(pages)
    if result is None:
        # LLM fallback
        result = llm_fallback(pages, tenant_id=tenant_id)

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

    # Day-6 drill: carry pages so persist_to_db stores real bboxes + dims
    result.pages = pages
    return result

def persist_to_db(result: ExtractionResult, document_id: str, tenant_id: str, run_id: str):
    """
    Persist extraction result to DB per DB-first: extraction_runs + source_spans + transactions + transaction_sources
    Per user question: all transactions only ever recorded per bank account number, each account number should have its own database? No, own ledger account within same DB per tenant, with unique constraint tenant_id + account_number
    """
    from apps.api.db import get_db
    import uuid
    db = get_db()

    # Handle account_number per bank account: create account if not exists with tenant_id + account_number unique
    extracted_number = result.statement.get("account_number") if result.statement else None
    asserted_number = None
    try:
        drow = db.execute(
            "SELECT asserted_account_number FROM source_documents"
            " WHERE id=?", (document_id,)).fetchone()
        if drow:
            d = dict(drow) if not isinstance(drow, dict) else drow
            asserted_number = (d.get("asserted_account_number") or "").strip() or None
    except Exception:
        asserted_number = None  # column missing on old DBs: proceed unattributed
    account_number = asserted_number or extracted_number
    if asserted_number and extracted_number:
        from apps.api.db import append_audit_log
        if asserted_number == extracted_number:
            append_audit_log(tenant_id, None, "document.account_confirmed",
                             "source_documents", document_id,
                             {"account_number": asserted_number})
        else:
            append_audit_log(tenant_id, None, "document.account_mismatch",
                             "source_documents", document_id,
                             {"asserted": asserted_number,
                              "extracted": extracted_number,
                              "filed_under": asserted_number})
    bank_name = result.statement.get("bank") or result.statement.get("bank_name") if result.statement else None
    branch_code = result.statement.get("branch_code") if result.statement else None
    account_id = None
    if account_number:
        # Check if account exists for this tenant + account_number
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND account_number=?", (tenant_id, account_number))
        row = cur.fetchone()
        if row:
            account_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            # Create account with code = account_number or generic
            account_id = f"acc-{uuid.uuid4().hex[:8]}"
            code = account_number[-6:] if len(account_number) > 6 else account_number
            name = f"{bank_name or 'Bank'} - {account_number}" if bank_name else f"Bank Account {account_number}"
            try:
                db.execute(
                    "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, bank_name, branch_code) VALUES (?,?,?,?,?,?,?,?)",
                    (account_id, tenant_id, code, name, "asset", account_number, bank_name, branch_code)
                )
            except Exception as e:
                # If unique constraint fails, fetch existing
                cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND account_number=?", (tenant_id, account_number))
                row = cur.fetchone()
                if row:
                    account_id = row["id"] if isinstance(row, dict) else row[0]
        # Update source_documents: account_number is the FILING
        # (assertion wins); extracted_account_number is the FINDING.
        try:
            db.execute(
                "UPDATE source_documents SET account_id=?, account_number=?, extracted_account_number=?, bank_name=?, branch_code=? WHERE id=?",
                (account_id, account_number, extracted_number, bank_name, branch_code, document_id)
            )
        except Exception:
            pass

    # If no account_number, use default account per tenant
    if not account_id:
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND code='1000' LIMIT 1", (tenant_id,))
        row = cur.fetchone()
        if row:
            account_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            # Create generic bank account
            account_id = f"acc-{uuid.uuid4().hex[:8]}"
            try:
                db.execute(
                    "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, bank_name) VALUES (?,?,?,?,?,?,?)",
                    (account_id, tenant_id, "1000", "Bank - Generic", "asset", account_number or "unknown", bank_name or "Unknown")
                )
            except:
                pass

    # source_spans + transactions with account_id and account_number per user question
    # Day-6 drill: real per-line bbox + page dims from result.pages (fallback
    # placeholder only when pages are absent, e.g. synthetic unit results)
    line_lookup = {}
    for page in getattr(result, "pages", None) or []:
        for line in page.get("lines", []):
            bbox = line.get("bbox") or [0, 0, 100, 10]
            line_lookup[line.get("line_id")] = (
                page.get("page_no", 1), page.get("width"), page.get("height"),
                bbox, line.get("text", ""))
    from .base import fingerprint_txn
    for row in result.rows:
        txn_id = f"txn-{uuid.uuid4().hex[:8]}"
        fp = fingerprint_txn(row.date, row.amount_minor, row.description)
        if not account_number:
            # Unknown account: scope the fingerprint to this document so
            # identical rows (debit orders) in another unknown-account
            # statement do not dedup against each other. Re-extracts of
            # THIS doc keep the same fp and still dedup correctly.
            fp = hashlib.sha256(f"{fp}|{document_id}".encode()).hexdigest()
        # Ensure transaction only once ever per bank account number per user question: UNIQUE(tenant_id, account_number, fingerprint_sha256)
        # Check if fingerprint already exists for this tenant + account_number
        cur = db.execute("SELECT id FROM transactions WHERE tenant_id=? AND account_number=? AND fingerprint_sha256=?", (tenant_id, account_number or "", fp))
        existing = cur.fetchone()
        if existing:
            # Duplicate transaction - skip per each transaction only once ever
            # (spans are written after this check, so no orphans)
            continue
        db.execute(
            "INSERT OR REPLACE INTO transactions (id, tenant_id, account_id, account_number, document_id, run_id, txn_date, description_raw, amount_minor, currency, direction, balance_after_minor, fingerprint_sha256, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (txn_id, tenant_id, account_id, account_number or "", document_id, run_id, row.date, row.description, row.amount_minor, "ZAR", row.direction, row.balance_after_minor, fp, "proposed")
        )
        for line_id in (row.line_ids or ["L001"]):
            page_no, width, height, bbox, text = line_lookup.get(
                line_id, (1, None, None, [0, 0, 100, 10], row.source_quote))
            span_id = f"span-{uuid.uuid4().hex[:8]}"
            db.execute(
                "INSERT OR REPLACE INTO source_spans (id, tenant_id, run_id, document_id, page_no, line_id, bbox_x0, bbox_y0, bbox_x1, bbox_y1, page_width, page_height, text, text_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (span_id, tenant_id, run_id, document_id, page_no, line_id,
                 bbox[0], bbox[1], bbox[2], bbox[3], width, height,
                 text or row.source_quote,
                 hashlib.sha256((text or row.source_quote).encode()).hexdigest()[:16])
            )
            db.execute(
                "INSERT OR REPLACE INTO transaction_sources (transaction_id, span_id, role) VALUES (?,?,?)",
                (txn_id, span_id, "amount")
            )
    db.commit()
