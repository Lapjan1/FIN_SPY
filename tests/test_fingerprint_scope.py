"""
Unknown-account dedup scope: two statements with no account number must not
eat each other's identical rows (same date+amount+desc, e.g. debit orders).
Scope = (tenant, account, fp) when known, (tenant, doc, fp) when unknown.
"""

import uuid

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.worker.parsers.base import ExtractionResult, ExtractedRow
from apps.worker.parsers.extractor import persist_to_db


def _result(rows):
    return ExtractionResult(
        statement={"bank": "GENERIC", "account_number": None,
                   "period_start": None, "period_end": None,
                   "currency": "ZAR", "opening_balance": None,
                   "closing_balance": None},
        rows=rows, unaccounted_lines=[], warnings=[],
        opening_balance_minor=None, closing_balance_minor=None)


def _row(desc="DEBIT ORDER", date="2026-08-02", amount=50000):
    return ExtractedRow(
        line_ids=["L001"], date=date, description=desc,
        amount_minor=amount, direction="debit",
        balance_after_minor=9500000, source_quote=f"{date} {desc}")


def _count(tenant):
    db = get_db()
    cur = db.execute("SELECT COUNT(*) AS c FROM transactions WHERE tenant_id=?",
                     (tenant,))
    row = cur.fetchone()
    return row["c"] if isinstance(row, dict) else row[0]


def test_same_row_two_unknown_docs_both_persist():
    init_db()
    tag = uuid.uuid4().hex[:6]
    tenant = f"fpscope-{tag}"
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    for doc, run in ((f"doc-a-{tag}", f"run-a-{tag}"),
                     (f"doc-b-{tag}", f"run-b-{tag}")):
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
            " storage_key, status) VALUES (?,?,?,?,?,?)",
            (doc, tenant, f"sha-{doc}-{tenant}", 10, f"k-{doc}", "queued"),
        )
        db.execute("INSERT INTO extraction_runs (id, document_id)"
                   " VALUES (?,?)", (run, doc))
    doc_a, doc_b = f"doc-a-{tag}", f"doc-b-{tag}"
    db.commit()
    try:
        persist_to_db(_result([_row()]), doc_a, tenant, f"run-a-{tag}")
        persist_to_db(_result([_row()]), doc_b, tenant, f"run-b-{tag}")
        assert _count(tenant) == 2
    finally:
        cleanup_tenant(tenant)


def test_same_doc_reextract_still_dedups():
    init_db()
    tag = uuid.uuid4().hex[:6]
    tenant = f"fpscope2-{tag}"
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
               " storage_key, status) VALUES (?,?,?,?,?,?)",
               (f"doc-x-{tag}", tenant, "sha-x", 10, "k-x", "queued"))
    for run in (f"run-1-{tag}", f"run-2-{tag}"):
        db.execute("INSERT INTO extraction_runs (id, document_id)"
                   " VALUES (?,?)", (run, f"doc-x-{tag}"))
    db.commit()
    try:
        persist_to_db(_result([_row()]), f"doc-x-{tag}", tenant,
                      f"run-1-{tag}")
        persist_to_db(_result([_row()]), f"doc-x-{tag}", tenant,
                      f"run-2-{tag}")
        assert _count(tenant) == 1
    finally:
        cleanup_tenant(tenant)
