"""
Worker - Procrastinate SQLite queue (MVP) -> Postgres prod per AGENTS.md
Per docs: intake -> hash -> store -> text/OCR -> extract -> reconcile -> classify -> post -> analytics -> reports
DB-first: every step persists to .db before next.

Day2: Worker queue that processes queued documents + calls extractor
Handles encrypted PDFs with password param transiently, never logs/stores password
"""
import os
import time
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone

from apps.api.db import get_db, init_db, append_audit_log, compute_row_hash
from apps.worker.parsers.extractor import extract_document, persist_to_db
from apps.worker.parsers.base import ExtractionResult
from apps.worker.reconcile import run_reconciliation_gate

VAULT_PATH = Path(os.getenv("VAULT_PATH", "./data/vault"))
RATE_LIMIT_RPM = int(os.getenv("META_RATE_LIMIT_RPM", "100"))
# Global rate limiter: 100 RPM per AGENTS.md
REQUEST_INTERVAL = 60.0 / RATE_LIMIT_RPM if RATE_LIMIT_RPM > 0 else 0.6

def process_one_document(doc_id: str, tenant_id: str, sha256: str, storage_key: str, uploaded_by: int, password: str = None):
    """
    Process single queued document: text+bbox -> deterministic -> LLM fallback -> validate -> persist
    Returns status, extraction result
    """
    db = get_db()
    # Create extraction_runs record
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    pipeline_version = "1.0.0"
    git_commit = "unknown"  # TODO: get from git
    db.execute(
        "INSERT INTO extraction_runs (id, document_id, pipeline_version, git_commit, method, model_id, status, started_at) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, doc_id, pipeline_version, git_commit, "deterministic+llm", "muse-spark-1.1", "running", datetime.now(timezone.utc).isoformat())
    )
    db.commit()

    # Stage tracking: logs carry stage + counts + exception class only,
    # never page text or amounts, so prod logs stay PII-free.
    stage = "enter"
    try:
        pdf_path = Path(storage_key)
        if not pdf_path.exists():
            # Try vault path
            pdf_path = VAULT_PATH / f"{sha256}.pdf"
        if not pdf_path.exists():
            print(f"worker: doc {doc_id} vault-miss sha {sha256[:8]}...")

        stage = "extract"
        result = extract_document(pdf_path, bank_hint="FNB", password=password, tenant_id=tenant_id)
        print(f"worker: doc {doc_id} stage=extract rows={len(result.rows)}")

        # Reconciliation gate per AGENTS.md + docs/FLOWS.md + apps/worker/reconcile.py
        # Opening + sum = closing, running balance monotonic, duplicate fingerprints
        gate = run_reconciliation_gate(result.opening_balance_minor, result.closing_balance_minor, result.rows)
        warnings = list(result.warnings)
        for _gk in ("opening_closing_top_bottom", "opening_closing_bottom_top"):
            if not gate[_gk]["pass"]:
                warnings.append(gate[_gk]["message"])
        for _gk in ("running_balance_top_bottom", "running_balance_bottom_top"):
            if not gate[_gk]["pass"]:
                warnings.extend(gate[_gk]["breaks"])
        if not gate["duplicates"]["pass"]:
            warnings.append(f"Duplicate fingerprints: {gate['duplicates']['duplicates']}")

        has_recon_fail = not gate["overall_pass"]
        has_low_coverage = any("Low coverage" in w for w in warnings)

        status = "proposed"
        if has_recon_fail:
            status = "exception"

        stage = "gate"
        print(f"worker: doc {doc_id} stage=gate pass={gate['overall_pass']}")

        # Persist to DB per DB-first
        # For MVP, create source_spans, transactions via persist_to_db
        stage = "persist"
        persist_to_db(result, doc_id, tenant_id, run_id)
        print(f"worker: doc {doc_id} stage=persist done")

        stage = "finalize"
        # Update extraction_runs
        db.execute(
            "UPDATE extraction_runs SET status=?, finished_at=?, opening_balance_minor=?, closing_balance_minor=?, computed_closing_minor=?, reconciliation=? WHERE id=?",
            ("pass" if status=="proposed" else "fail" if status=="exception" else "na",
             datetime.now(timezone.utc).isoformat(),
             result.opening_balance_minor, result.closing_balance_minor,
             result.closing_balance_minor, # computed for now same as closing
             "pass" if not has_recon_fail else "fail",
             run_id)
        )
        # Update document status
        db.execute("UPDATE source_documents SET status=? WHERE id=?", (status, doc_id))
        db.commit()

        # Audit log append with prev_hash/row_hash
        append_audit_log(tenant_id, uploaded_by, f"extraction.{status}", "extraction_runs", run_id, {"document_id": doc_id, "rows": len(result.rows), "warnings": warnings[:5]})

        # Usage metering per homework Part 5.13
        db.execute("INSERT INTO usage_events (id, tenant_id, kind, units, est_cost_usd) VALUES (?,?,?,?,?)",
                   (f"usage-{uuid.uuid4().hex[:8]}", tenant_id, "pages", 1, 0.04))
        db.commit()

        # Rate limit per AGENTS.md global limiter
        time.sleep(REQUEST_INTERVAL)

        return status, result

    except ValueError as e:
        # Encrypted needs password per our encrypted handling
        if "needs_password" in str(e).lower() or "encrypted" in str(e).lower():
            db.execute("UPDATE source_documents SET status=? WHERE id=?", ("needs_password", doc_id))
            db.commit()
            append_audit_log(tenant_id, uploaded_by, "extraction.needs_password", "source_documents", doc_id, {"error": str(e)[:200]})
            print(f"worker: doc {doc_id} stage={stage} needs_password")
            return "needs_password", None
        else:
            db.execute("UPDATE extraction_runs SET status=?, finished_at=? WHERE id=?", ("fail", datetime.now(timezone.utc).isoformat(), run_id))
            db.execute("UPDATE source_documents SET status=? WHERE id=?", ("exception", doc_id))
            db.commit()
            append_audit_log(tenant_id, uploaded_by, "extraction.fail", "extraction_runs", run_id, {"error": str(e)[:500]})
            print(f"worker: doc {doc_id} FAILED stage={stage} exc=ValueError")
            return "exception", None
    except Exception as e:
        db.execute("UPDATE extraction_runs SET status=?, finished_at=? WHERE id=?", ("fail", datetime.now(timezone.utc).isoformat(), run_id))
        db.execute("UPDATE source_documents SET status=? WHERE id=?", ("exception", doc_id))
        db.commit()
        append_audit_log(tenant_id, uploaded_by, "extraction.fail", "extraction_runs", run_id, {"error": str(e)[:500]})
        # Schema-shape errors carry identifiers only (never row values),
        # so their text is safe for logs; everything else stays class-only.
        _safe_msg = (
            f" msg={str(e)[:120]}"
            if type(e).__name__
            in ("InvalidColumnReference", "UndefinedColumn", "UndefinedTable")
            else ""
        )
        print(f"worker: doc {doc_id} FAILED stage={stage} exc={type(e).__name__}{_safe_msg}")
        return "exception", None

def worker_loop(poll_interval: int = 5, max_iterations: int = None):
    """
    Simple polling worker per AGENTS.md queue sqlite MVP
    For prod, replace with Procrastinate Postgres-backed queue per homework Part 5.3
    """
    print("FIN_SPY worker starting...")
    init_db()
    print(f"Vault: {VAULT_PATH}")
    from apps.api.db import redact_url
    print(f"DB: {redact_url(os.getenv('DATABASE_URL', 'sqlite:///./data/fin_spy.db'))}")
    print(f"Meta base: {os.getenv('FREELLMAPI_BASE_URL', 'http://127.0.0.1:3001/v1')}")
    print(f"Queue: polling every {poll_interval}s, rate limit {RATE_LIMIT_RPM} RPM, interval {REQUEST_INTERVAL}s")
    print("Forensic pipeline: intake->hash->text+bbox->deterministic->LLM fallback line-ID grounding->validate->persist")
    print("Reference extractor with 25+ adaptors can be READ per AGENTS.md at FNBP_REFERENCE_PATH, never imported")

    iteration = 0
    while True:
        db = get_db()
        # Get queued documents - per-tenant fairness: order by uploaded_at_utc asc
        cur = db.execute("SELECT id, tenant_id, sha256, storage_key, uploaded_by FROM source_documents WHERE status='queued' ORDER BY uploaded_at_utc ASC LIMIT 5")
        rows = cur.fetchall()
        if not rows:
            time.sleep(poll_interval)
            iteration += 1
            if max_iterations and iteration >= max_iterations:
                print("Max iterations reached, exiting")
                break
            continue

        for row in rows:
            doc_id = row["id"] if isinstance(row, dict) else row[0]
            tenant_id = row["tenant_id"] if isinstance(row, dict) else row[1]
            sha256 = row["sha256"] if isinstance(row, dict) else row[2]
            storage_key = row["storage_key"] if isinstance(row, dict) else row[3]
            uploaded_by = row["uploaded_by"] if isinstance(row, dict) else row[4]
            print(f"Processing doc {doc_id} tenant {tenant_id} sha {sha256[:8]}...")
            status, result = process_one_document(doc_id, tenant_id, sha256, storage_key, uploaded_by)
            print(f"Doc {doc_id} -> status {status}, rows {len(result.rows) if result else 0}, warnings {result.warnings[:2] if result else []}")

        iteration += 1
        if max_iterations and iteration >= max_iterations:
            print("Max iterations reached, exiting")
            break

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FIN_SPY Worker - DB-first extraction pipeline")
    parser.add_argument("--queue", default="sqlite", help="Queue type sqlite or postgres")
    parser.add_argument("--poll-interval", type=int, default=5, help="Poll interval seconds")
    parser.add_argument("--max-iterations", type=int, default=None, help="Max iterations for testing, None infinite")
    parser.add_argument("--once", action="store_true", help="Process one batch then exit")
    args = parser.parse_args()

    poll = args.poll_interval
    max_iter = 1 if args.once else args.max_iterations
    worker_loop(poll_interval=poll, max_iterations=max_iter)

if __name__ == "__main__":
    main()
