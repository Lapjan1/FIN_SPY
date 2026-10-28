"""
Audit reports: every human change (legal record) + integrity verification.

Per the forensic rule: source rows (vault PDFs, spans, extraction runs) are
immutable; human corrections layer on top as append-only revisions with reasons.
human_changes() lists the complete correction record; verify_integrity()
recomputes the audit hash chain and vault file hashes to prove sha256 intact.
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional

from .db import get_db, compute_row_hash

VAULT_PATH = Path(os.getenv("VAULT_PATH", "data/vault"))

HUMAN_JOURNAL_ACTIONS = (
    "journal.post",
    "journal.repost",
    "review.accept",
    "review.edit",
)


def verify_audit_chain(tenant_id: str, db=None) -> Dict:
    """Recompute the tenant audit hash chain. Returns {checked, ok, bad_id, head}."""
    if db is None:
        db = get_db()
    cur = db.execute(
        "SELECT id, prev_hash, row_hash, payload_json FROM audit_log"
        " WHERE tenant_id=? ORDER BY id ASC",
        (tenant_id,),
    )
    expected = "0" * 64
    checked = 0
    for r in cur.fetchall():
        d = dict(r) if not isinstance(r, dict) else r
        checked += 1
        if (d.get("prev_hash") or "") != expected:
            return {
                "checked": checked,
                "ok": False,
                "bad_id": d.get("id"),
                "reason": "prev_hash does not match previous row_hash",
                "head": expected,
            }
        if compute_row_hash(d.get("prev_hash") or "", d.get("payload_json") or "") != (
            d.get("row_hash") or ""
        ):
            return {
                "checked": checked,
                "ok": False,
                "bad_id": d.get("id"),
                "reason": "row_hash != SHA256(prev||payload)",
                "head": expected,
            }
        expected = d.get("row_hash") or ""
    return {"checked": checked, "ok": True, "bad_id": None, "head": expected}


def verify_vault_files(tenant_id: str, db=None) -> Dict:
    """Rehash vault files vs stored sha256. Returns {checked, ok, missing, mismatched}."""
    if db is None:
        db = get_db()
    cur = db.execute(
        "SELECT id, sha256, storage_key FROM source_documents WHERE tenant_id=?",
        (tenant_id,),
    )
    checked = 0
    missing: List[str] = []
    mismatched: List[str] = []
    for r in cur.fetchall():
        d = dict(r) if not isinstance(r, dict) else r
        checked += 1
        name = str(d.get("storage_key") or f"{d.get('sha256')}.pdf")
        candidates = [Path(name), VAULT_PATH / Path(name).name]
        path = next((c for c in candidates if c.exists()), None)
        if path is None:
            missing.append(d.get("id"))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != (d.get("sha256") or ""):
            mismatched.append(d.get("id"))
    return {
        "checked": checked,
        "ok": not missing and not mismatched,
        "missing": missing,
        "mismatched": mismatched,
    }


def verify_integrity(tenant_id: str, db=None) -> Dict:
    """Full integrity proof: audit chain + vault hashes. Read-only."""
    chain = verify_audit_chain(tenant_id, db=db)
    vault = verify_vault_files(tenant_id, db=db)
    return {
        "tenant_id": tenant_id,
        "audit_chain": chain,
        "vault_files": vault,
        "intact": chain["ok"] and vault["ok"],
    }


def _filtered(
    base: str,
    tenant_id: str,
    alias: str,
    id_col: str,
    order: str,
    from_utc,
    to_utc,
    actor_id,
    transaction_id,
    limit,
    db,
) -> List[Dict]:
    """Run a tenant-scoped report query with shared time/actor/txn filters.

    Every value stays a bound parameter (tenant_id is user-influenced at
    registration, so it must never be interpolated into SQL).
    """
    q, params = base, [tenant_id]
    if from_utc:
        q += f" AND {alias}.at_utc>=?"
        params.append(from_utc)
    if to_utc:
        q += f" AND {alias}.at_utc<=?"
        params.append(to_utc)
    if actor_id is not None:
        q += f" AND {alias}.actor_id=?"
        params.append(actor_id)
    if transaction_id:
        q += f" AND {alias}.{id_col}=?"
        params.append(transaction_id)
    q += f" ORDER BY {order} DESC LIMIT ?"
    params.append(limit)
    cur = db.execute(q, tuple(params))
    return [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]


def human_changes(
    tenant_id: str,
    from_utc: Optional[str] = None,
    to_utc: Optional[str] = None,
    actor_id: Optional[int] = None,
    transaction_id: Optional[str] = None,
    limit: int = 100,
    db=None,
) -> Dict:
    """Legal record of every human change: field revisions + journal/human actions.

    Revisions carry old/new values with reasons; journal actions (accept, edit,
    post, repost, transfers via decide) carry entry links. Newest first.
    """
    if db is None:
        db = get_db()
    if not tenant_id:
        raise ValueError("Invalid parameters: tenant_id is required")
    limit = max(1, min(int(limit or 100), 500))
    revisions = _filtered(
        "SELECT r.id, r.at_utc, r.actor_id, u.email AS actor_email,"
        " r.transaction_id, t.txn_date, t.description_raw, r.field,"
        " r.old_value, r.new_value, r.reason FROM transaction_revisions r"
        " LEFT JOIN transactions t ON r.transaction_id=t.id"
        " LEFT JOIN users u ON r.actor_id=u.id WHERE r.tenant_id=?",
        tenant_id,
        "r",
        "transaction_id",
        "r.at_utc",
        from_utc,
        to_utc,
        actor_id,
        transaction_id,
        limit,
        db,
    )
    actions = _filtered(
        "SELECT a.id, a.at_utc, a.actor_id, u.email AS actor_email,"
        " a.action, a.object_type, a.object_id, a.payload_json, a.row_hash"
        " FROM audit_log a LEFT JOIN users u ON a.actor_id=u.id"
        " WHERE a.tenant_id=? AND (a.action LIKE 'journal.%'"
        " OR a.action LIKE 'review.%' OR a.action LIKE 'classify.%')",
        tenant_id,
        "a",
        "object_id",
        "a.id",
        from_utc,
        to_utc,
        actor_id,
        transaction_id,
        limit,
        db,
    )
    return {
        "tenant_id": tenant_id,
        "revisions": revisions,
        "revision_count": len(revisions),
        "journal_actions": actions,
        "journal_action_count": len(actions),
    }
