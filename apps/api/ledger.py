"""
Ledger-core: dynamic double-entry ledger, per-tenant COA, balanced journal enforcement.
Per docs/MODULES.md ledger-core + docs/TIMELINE.md Day4 + LEARNINGS 2026-10-26-02.

Public API:
  post_transaction(tx, classification, created_by=None) -> JournalEntry dict
  trial_balance(tenant_id, as_of=None, entity_id=None) -> {lines, totals, balanced}
  get_journal_entries(tenant_id, transaction_id=None)

Money: int minor (cents) only, never float. Dates YYYY-MM-DD strings.
Tenant isolation: every lookup filters tenant_id. Never posts across tenants.
Active books: resolves accounts in tenants.active_template first (one at a time).
"""

import uuid
from typing import Dict, List, Optional

from .db import get_db


class UnbalancedEntry(ValueError):
    pass


class UnknownAccount(ValueError):
    pass


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row) if not isinstance(row, dict) else row


def resolve_account(
    tenant_id: str,
    code: Optional[str] = None,
    account_id: Optional[str] = None,
    db=None,
) -> Dict:
    """Resolve one account for tenant. Prefers active template, never cross-tenant.

    Raises UnknownAccount (with 'Invalid parameters' prefix) when not found.
    """
    if db is None:
        db = get_db()
    try:
        from apps.worker.parsers.registry import ensure_coa_seeded

        ensure_coa_seeded(tenant_id, db=db)
    except Exception:
        pass
    if account_id:
        cur = db.execute(
            "SELECT * FROM accounts WHERE id=? AND tenant_id=?", (account_id, tenant_id)
        )
        row = _row_to_dict(cur.fetchone())
        if not row:
            raise UnknownAccount(
                f"Invalid parameters: account_id '{account_id}' does not exist "
                f"for tenant '{tenant_id}'. Seed COA first."
            )
        return row
    if code:
        # Prefer active template (one books choice at a time)
        try:
            from apps.worker.parsers.registry import get_active_template

            active = get_active_template(tenant_id, db=db)
        except Exception:
            active = "personal"
        cur = db.execute(
            "SELECT * FROM accounts WHERE tenant_id=? AND code=? AND template=?",
            (tenant_id, code, active),
        )
        row = _row_to_dict(cur.fetchone())
        if row:
            return row
        # Fallback: any template for this tenant
        cur = db.execute(
            "SELECT * FROM accounts WHERE tenant_id=? AND code=? LIMIT 1",
            (tenant_id, code),
        )
        row = _row_to_dict(cur.fetchone())
        if row:
            return row
        raise UnknownAccount(
            f"Invalid parameters: code '{code}' does not exist for tenant "
            f"'{tenant_id}' in template '{active}'. Seed COA first."
        )
    raise UnknownAccount("Invalid parameters: code or account_id is required")


def _resolve_bank_account(tx: Dict, tenant_id: str, db) -> Dict:
    """Bank side of a posting: tx account_id first, then account_number lookup."""
    if tx.get("account_id"):
        cur = db.execute(
            "SELECT * FROM accounts WHERE id=? AND tenant_id=?",
            (tx["account_id"], tenant_id),
        )
        row = _row_to_dict(cur.fetchone())
        if row:
            return row
    acct_no = tx.get("account_number")
    if acct_no:
        cur = db.execute(
            "SELECT * FROM accounts WHERE tenant_id=? AND account_number=?",
            (tenant_id, acct_no),
        )
        row = _row_to_dict(cur.fetchone())
        if row:
            return row
    raise UnknownAccount(
        f"Invalid parameters: bank account for transaction '{tx.get('id')}' "
        f"does not exist for tenant '{tenant_id}'. Seed COA / link account_number first."
    )


def _resolve_private_account(tenant_id: str, db) -> Optional[Dict]:
    """Private/drawings leg for mixed splits: 3300 suspense, else 7000/3210/3200 drawings."""
    for code in ("3300", "7000", "3210", "3200"):
        try:
            return resolve_account(tenant_id, code=code, db=db)
        except UnknownAccount:
            continue
    return None


def _validate_posting_inputs(tx: Dict, classification: Dict) -> tuple:
    """Validate money + classification inputs. Returns (tenant_id, txn_id, amount, direction, nature, business_pct)."""
    tenant_id = tx.get("tenant_id")
    if not tenant_id:
        raise ValueError("Invalid parameters: tx.tenant_id is required")
    txn_id = tx.get("id")
    if not txn_id:
        raise ValueError("Invalid parameters: tx.id is required")
    raw_amount = tx.get("amount_minor")
    if not isinstance(raw_amount, int) or isinstance(raw_amount, bool):
        raise ValueError(
            f"Invalid parameters: amount_minor must be int cents, got '{raw_amount}'"
        )
    amount = abs(raw_amount)
    if amount <= 0:
        raise ValueError(
            f"Invalid parameters: amount_minor must be non-zero, got {raw_amount}"
        )
    direction = (tx.get("direction") or "").lower()
    if direction not in ("debit", "credit"):
        direction = "credit" if raw_amount > 0 else "debit"
    business_pct = classification.get("business_pct", 100)
    if not isinstance(business_pct, int) or not (0 <= business_pct <= 100):
        raise ValueError(
            f"Invalid parameters: business_pct must be int 0-100, got '{business_pct}'"
        )
    nature = (classification.get("nature") or "business").lower()
    if nature not in ("business", "private", "mixed", "unknown"):
        raise ValueError(
            f"Invalid parameters: nature must be business|private|mixed|unknown, got '{nature}'"
        )
    return tenant_id, txn_id, amount, direction, nature, business_pct


def _build_posting_lines(
    target: Dict,
    bank: Dict,
    private_acct: Optional[Dict],
    amount: int,
    business_pct: int,
    is_inflow: bool,
) -> List[Dict]:
    """Build balanced debit=credit lines. Mixed splits need private_acct."""
    if 0 < business_pct < 100:
        if private_acct is None:
            raise UnknownAccount(
                "Invalid parameters: mixed split needs private account 3300/7000/3210/3200."
                " Personal template has no drawings - use mixed_sole_prop for mixed."
            )
        business_amount = amount * business_pct // 100
        private_amount = amount - business_amount
        if is_inflow:
            # Dr Bank total / Cr income business + Cr private suspense
            return [
                {
                    "account_id": bank["id"],
                    "code": bank.get("code"),
                    "debit_minor": amount,
                    "credit_minor": 0,
                },
                {
                    "account_id": target["id"],
                    "code": target.get("code"),
                    "debit_minor": 0,
                    "credit_minor": business_amount,
                },
                {
                    "account_id": private_acct["id"],
                    "code": private_acct.get("code"),
                    "debit_minor": 0,
                    "credit_minor": private_amount,
                },
            ]
        # Dr expense business + Dr private / Cr Bank total
        return [
            {
                "account_id": target["id"],
                "code": target.get("code"),
                "debit_minor": business_amount,
                "credit_minor": 0,
            },
            {
                "account_id": private_acct["id"],
                "code": private_acct.get("code"),
                "debit_minor": private_amount,
                "credit_minor": 0,
            },
            {
                "account_id": bank["id"],
                "code": bank.get("code"),
                "debit_minor": 0,
                "credit_minor": amount,
            },
        ]
    if is_inflow:
        # Dr Bank / Cr income
        return [
            {
                "account_id": bank["id"],
                "code": bank.get("code"),
                "debit_minor": amount,
                "credit_minor": 0,
            },
            {
                "account_id": target["id"],
                "code": target.get("code"),
                "debit_minor": 0,
                "credit_minor": amount,
            },
        ]
    # Dr expense / Cr Bank
    return [
        {
            "account_id": target["id"],
            "code": target.get("code"),
            "debit_minor": amount,
            "credit_minor": 0,
        },
        {
            "account_id": bank["id"],
            "code": bank.get("code"),
            "debit_minor": 0,
            "credit_minor": amount,
        },
    ]


def post_transaction(
    tx: Dict, classification: Dict, created_by: Optional[int] = None, db=None
) -> Dict:
    """Post one balanced journal entry for a transaction + classification.

    tx: {id, tenant_id, txn_date, amount_minor:int, direction:debit|credit|None,
         account_id?, account_number?}
    classification: {category_id|code?, account_id?, nature?, business_pct?}
    Returns {id, tenant_id, entry_date, lines:[{account_id, code, debit_minor, credit_minor}]}.
    Raises UnknownAccount / UnbalancedEntry / ValueError('Invalid parameters...').
    """
    if db is None:
        db = get_db()
    tenant_id, txn_id, amount, direction, nature, business_pct = (
        _validate_posting_inputs(tx, classification)
    )
    code = classification.get("category_id") or classification.get("code")
    target = resolve_account(
        tenant_id, code=code, account_id=classification.get("account_id"), db=db
    )
    bank = _resolve_bank_account(tx, tenant_id, db)
    private_acct = (
        _resolve_private_account(tenant_id, db) if 0 < business_pct < 100 else None
    )

    entry_id = f"je-{uuid.uuid4().hex[:8]}"
    entry_date = tx.get("txn_date") or ""
    memo = f"Post {txn_id} {direction} {amount}c -> {target.get('code')} ({nature} {business_pct}%)"
    lines = _build_posting_lines(
        target, bank, private_acct, amount, business_pct, direction == "credit"
    )

    debits = sum(line["debit_minor"] for line in lines)
    credits = sum(line["credit_minor"] for line in lines)
    if debits != credits or debits != amount:
        raise UnbalancedEntry(
            f"Journal entry not balanced: debits {debits} != credits {credits} (amount {amount})"
        )

    db.execute(
        "INSERT INTO journal_entries (id, tenant_id, entry_date, memo, transaction_id, classification_id, created_by, posted)"
        " VALUES (?,?,?,?,?,?,?,0)",
        (
            entry_id,
            tenant_id,
            entry_date,
            memo,
            txn_id,
            classification.get("id"),
            created_by,
        ),
    )
    for line in lines:
        db.execute(
            "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
            " VALUES (?,?,?,?,?)",
            (
                f"jl-{uuid.uuid4().hex[:6]}",
                entry_id,
                line["account_id"],
                line["debit_minor"],
                line["credit_minor"],
            ),
        )
    # Post: DB trigger re-verifies balance (defense in depth behind Python check above)
    try:
        db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise UnbalancedEntry(f"Journal entry not balanced: {e}")
    db.commit()
    return {
        "id": entry_id,
        "tenant_id": tenant_id,
        "entry_date": entry_date,
        "memo": memo,
        "transaction_id": txn_id,
        "lines": lines,
        "debits": debits,
        "credits": credits,
        "posted": 1,
    }


def _check_transfer_codes(from_code: str, to_code: str) -> None:
    if not from_code or not to_code:
        raise ValueError("Invalid parameters: from_code and to_code are required")
    if from_code == to_code:
        raise ValueError("Invalid parameters: from_code and to_code must differ")


def _load_transfer_txn(tenant_id: str, transaction_id: str, db) -> Optional[Dict]:
    """Load owned txn for transfer, or None when it has no posted journal yet."""
    if not tenant_id or not transaction_id:
        raise ValueError(
            "Invalid parameters: tenant_id and transaction_id are required"
        )
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    txn = dict(row) if row is not None and not isinstance(row, dict) else row
    if txn is None:
        raise ValueError(
            f"Invalid parameters: transaction '{transaction_id}' does not exist"
        )
    if txn.get("tenant_id") != tenant_id:
        raise PermissionError("Cross-tenant access denied - isolation guard")
    cur = db.execute(
        "SELECT id FROM journal_entries WHERE transaction_id=? AND tenant_id=? LIMIT 1",
        (transaction_id, tenant_id),
    )
    if not cur.fetchone():
        return None
    return txn


def _transfer_amount_direction(txn: Dict) -> tuple:
    raw_amount = txn.get("amount_minor")
    if not isinstance(raw_amount, int) or isinstance(raw_amount, bool):
        raise ValueError(
            "Invalid parameters: transaction amount_minor must be int cents"
        )
    direction = (txn.get("direction") or "").lower()
    if direction not in ("debit", "credit"):
        direction = "credit" if raw_amount > 0 else "debit"
    return abs(raw_amount), direction


def transfer_posting(
    tenant_id: str,
    transaction_id: str,
    from_code: str,
    to_code: str,
    created_by: Optional[int] = None,
    reason: str = "",
    db=None,
) -> Optional[Dict]:
    """Move a posted transaction's primary leg from one account to another.

    Used when a human re-decodes (e.g. 9999 suspense -> real expense): the money
    leaves 9999 so suspense stays small and statements stay correct. Returns the
    transfer entry, or None when the transaction has no posted journal yet
    (nothing to move - the next post uses the new category directly).
    Raises UnknownAccount / ValueError('Invalid parameters...') on bad input.
    """
    if db is None:
        db = get_db()
    _check_transfer_codes(from_code, to_code)
    txn = _load_transfer_txn(tenant_id, transaction_id, db)
    if txn is None:
        return None
    old_acct = resolve_account(tenant_id, code=from_code, db=db)
    new_acct = resolve_account(tenant_id, code=to_code, db=db)
    amount, direction = _transfer_amount_direction(txn)
    if direction == "credit":
        # Original Dr bank / Cr old -> transfer Dr old / Cr new
        legs = [
            (old_acct, amount, 0),
            (new_acct, 0, amount),
        ]
    else:
        # Original Dr old / Cr bank -> transfer Dr new / Cr old
        legs = [
            (new_acct, amount, 0),
            (old_acct, 0, amount),
        ]
    entry_id = f"je-{uuid.uuid4().hex[:8]}"
    memo = f"Re-decode {transaction_id} {from_code}->{to_code}: {reason[:120]}"
    db.execute(
        "INSERT INTO journal_entries (id, tenant_id, entry_date, memo, transaction_id, created_by, posted)"
        " VALUES (?,?,?,?,?,?,0)",
        (
            entry_id,
            tenant_id,
            txn.get("txn_date") or "",
            memo,
            transaction_id,
            created_by,
        ),
    )
    lines = []
    for acct, debit, credit in legs:
        db.execute(
            "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
            " VALUES (?,?,?,?,?)",
            (f"jl-{uuid.uuid4().hex[:6]}", entry_id, acct["id"], debit, credit),
        )
        lines.append(
            {
                "account_id": acct["id"],
                "code": acct.get("code"),
                "debit_minor": debit,
                "credit_minor": credit,
            }
        )
    try:
        db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise UnbalancedEntry(f"Journal entry not balanced: {e}")
    db.commit()
    return {
        "id": entry_id,
        "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "from_code": from_code,
        "to_code": to_code,
        "lines": lines,
        "debits": amount,
        "credits": amount,
        "posted": 1,
    }


def _posted_entries_for(transaction_id: str, tenant_id: str, db) -> List[Dict]:
    cur = db.execute(
        "SELECT * FROM journal_entries WHERE transaction_id=? AND tenant_id=?"
        " AND posted=1 ORDER BY created_at ASC",
        (transaction_id, tenant_id),
    )
    return [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]


def _reverse_entry(entry: Dict, reason: str, created_by: Optional[int], db) -> Dict:
    """Append a mirror-image reversal of one posted entry (never delete history)."""
    cur = db.execute("SELECT * FROM journal_lines WHERE entry_id=?", (entry["id"],))
    old_lines = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    if not old_lines:
        raise UnbalancedEntry(f"Cannot reverse entry {entry['id']}: it has no lines")
    entry_id = f"je-{uuid.uuid4().hex[:8]}"
    memo = f"Reversal of {entry['id']}: {reason[:120]}"
    db.execute(
        "INSERT INTO journal_entries (id, tenant_id, entry_date, memo, transaction_id,"
        " classification_id, created_by, posted) VALUES (?,?,?,?,?,?,?,0)",
        (
            entry_id,
            entry["tenant_id"],
            entry.get("entry_date") or "",
            memo,
            entry.get("transaction_id"),
            entry.get("classification_id"),
            created_by,
        ),
    )
    lines = []
    for old in old_lines:
        debit, credit = (
            int(old.get("credit_minor") or 0),
            int(old.get("debit_minor") or 0),
        )
        db.execute(
            "INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor)"
            " VALUES (?,?,?,?,?)",
            (
                f"jl-{uuid.uuid4().hex[:6]}",
                entry_id,
                old["account_id"],
                debit,
                credit,
            ),
        )
        lines.append(
            {
                "account_id": old["account_id"],
                "debit_minor": debit,
                "credit_minor": credit,
            }
        )
    debits = sum(line["debit_minor"] for line in lines)
    credits = sum(line["credit_minor"] for line in lines)
    if debits != credits:
        raise UnbalancedEntry(
            f"Reversal of {entry['id']} not balanced: {debits} != {credits}"
        )
    try:
        db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
    except Exception as e:
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise UnbalancedEntry(f"Journal entry not balanced: {e}")
    return {"id": entry_id, "reverses": entry["id"], "debits": debits}


def _latest_decision(transaction_id: str, tenant_id: str, db) -> Optional[Dict]:
    cur = db.execute(
        "SELECT * FROM classifications WHERE transaction_id=? AND tenant_id=?"
        " ORDER BY decided_at_utc DESC LIMIT 1",
        (transaction_id, tenant_id),
    )
    row = cur.fetchone()
    return dict(row) if row is not None and not isinstance(row, dict) else row


def _infer_posting_target(txn: Dict, first_entry: Dict, tenant_id: str, db) -> tuple:
    """Fallback target when a posted txn has no classification row (vendor path).

    Returns (classification dict, inferred flag). Prefers the original entry's
    non-bank leg, else parks in 9999 for human re-decode.
    """
    bank_id = txn.get("account_id")
    cur = db.execute(
        "SELECT * FROM journal_lines WHERE entry_id=?", (first_entry["id"],)
    )
    fallback = None
    for r in cur.fetchall():
        line = dict(r) if not isinstance(r, dict) else r
        if line["account_id"] == bank_id:
            continue
        if int(line.get("debit_minor") or 0) + int(line.get("credit_minor") or 0) <= 0:
            continue
        if fallback is None:
            fallback = line
        if int(line.get("debit_minor") or 0) > 0:
            fallback = line
            break
    if fallback is not None:
        return (
            {
                "account_id": fallback["account_id"],
                "nature": "unknown",
                "business_pct": 0,
            },
            True,
        )
    return {"category_id": "9999", "nature": "unknown", "business_pct": 0}, True


def repost_transaction(
    tenant_id: str,
    transaction_id: str,
    reason: str,
    created_by: Optional[int] = None,
    db=None,
) -> Optional[Dict]:
    """Reverse every posted entry for a txn, then post one fresh entry at current values.

    Called after a human edits amount/date on an already-posted transaction.
    History is append-only: originals + reversals + fresh post all remain linked
    by transaction_id. Returns None when the txn has no posted entries.
    The fresh post uses the latest classification, else the inferred original
    target, else 9999. Raises on bad input / unbalanced results.
    """
    if db is None:
        db = get_db()
    if not tenant_id or not transaction_id:
        raise ValueError(
            "Invalid parameters: tenant_id and transaction_id are required"
        )
    if not reason or not reason.strip():
        raise ValueError("Invalid parameters: reason is required for audit trail")
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    txn = dict(row) if row is not None and not isinstance(row, dict) else row
    if txn is None:
        raise ValueError(
            f"Invalid parameters: transaction '{transaction_id}' does not exist"
        )
    if txn.get("tenant_id") != tenant_id:
        raise PermissionError("Cross-tenant access denied - isolation guard")
    posted = _posted_entries_for(transaction_id, tenant_id, db)
    if not posted:
        return None
    decision = _latest_decision(transaction_id, tenant_id, db)
    if decision:
        classification: Dict = {
            "id": decision["id"],
            "category_id": decision.get("category_id"),
            "nature": decision.get("nature") or "business",
            "business_pct": decision.get("business_pct", 100),
        }
        inferred = False
    else:
        classification, inferred = _infer_posting_target(txn, posted[0], tenant_id, db)
    reversed_ids = []
    for entry in posted:
        rev = _reverse_entry(entry, reason.strip(), created_by, db)
        reversed_ids.append(rev["id"])
    fresh = post_transaction(txn, classification, created_by=created_by, db=db)
    db.commit()
    return {
        "transaction_id": transaction_id,
        "reversed_entry_ids": reversed_ids,
        "fresh_entry_id": fresh["id"],
        "fresh_category": classification.get("category_id") or "inferred",
        "target_inferred": inferred,
    }




def void_transaction(
    tenant_id: str,
    transaction_id: str,
    reason: str,
    created_by: Optional[int] = None,
    db=None,
) -> Dict:
    """Reject a proposed txn, or void a posted one via mirror-image reversals.

    Append-only: originals + reversals all remain (Q2 history). The txn
    status becomes 'rejected' either way; a status revision row records the
    human's reason. Raises ValueError('Invalid parameters...') on bad input,
    PermissionError on cross-tenant access."""
    from datetime import datetime, timezone

    if db is None:
        db = get_db()
    if not tenant_id or not transaction_id:
        raise ValueError(
            "Invalid parameters: tenant_id and transaction_id are required"
        )
    if not reason or not reason.strip():
        raise ValueError("Invalid parameters: reason is required for audit trail")
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    txn = dict(row) if row is not None and not isinstance(row, dict) else row
    if txn is None:
        raise ValueError(
            f"Invalid parameters: transaction '{transaction_id}' does not exist"
        )
    if txn.get("tenant_id") != tenant_id:
        raise PermissionError("Cross-tenant access denied - isolation guard")
    posted = _posted_entries_for(transaction_id, tenant_id, db)
    reversed_ids = []
    for entry in posted:
        rev = _reverse_entry(entry, reason.strip(), created_by, db)
        reversed_ids.append(rev["id"])
    old_status = txn.get("status")
    db.execute("UPDATE transactions SET status='rejected' WHERE id=?", (transaction_id,))
    db.execute(
        "INSERT INTO transaction_revisions (id, tenant_id, transaction_id, field,"
        " old_value, new_value, reason, actor_id, at_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            f"rev-{uuid.uuid4().hex[:8]}",
            tenant_id,
            transaction_id,
            "status",
            old_status,
            "rejected",
            reason.strip(),
            created_by,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    return {
        "transaction_id": transaction_id,
        "status": "rejected",
        "reversed_entry_ids": reversed_ids,
    }
def _chain_rows_for(tenant_id: str, txn: Dict, db) -> tuple:
    """Load the verification chain affected by an edit: document rows when the
    txn came from a statement, else the account chain. Ordered chronologically."""
    if txn.get("document_id"):
        cur = db.execute(
            "SELECT * FROM transactions WHERE tenant_id=? AND document_id=?"
            " ORDER BY txn_date ASC, created_at ASC, id ASC",
            (tenant_id, txn["document_id"]),
        )
        scope = {"document_id": txn["document_id"]}
    else:
        cur = db.execute(
            "SELECT * FROM transactions WHERE tenant_id=?"
            " AND COALESCE(account_number,'')=COALESCE(?,'')"
            " ORDER BY txn_date ASC, created_at ASC, id ASC",
            (tenant_id, txn.get("account_number") or ""),
        )
        scope = {"account_number": txn.get("account_number") or ""}
    rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    return scope, rows


def _row_line_evidence(transaction_id: str, db) -> tuple:
    """Line ids + source quote for a txn from its spans (empty when manually created)."""
    cur = db.execute(
        "SELECT ss.line_id, ss.text FROM transaction_sources ts"
        " JOIN source_spans ss ON ts.span_id=ss.id"
        " WHERE ts.transaction_id=? ORDER BY ss.page_no, ss.line_id",
        (transaction_id,),
    )
    spans = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    return [s.get("line_id") for s in spans], (
        spans[0].get("text") or "" if spans else ""
    )


def reverify_chain(tenant_id: str, transaction_id: str, db=None) -> Dict:
    """Re-run reconciliation checks forward over the chain an edit influences.

    Stored balances are immutable bank-printed source facts, so an amount/date
    edit cannot rewrite them - instead every check that consumes the edited
    values (document opening/closing both directions, running links both
    directions) is re-executed here and the outcome is logged + returned.
    Derived statements (trial/KPI/reports) read journals live, so they pick up
    the repost automatically. Read-only: writes nothing.
    """
    if db is None:
        db = get_db()
    from apps.worker.parsers.base import ExtractedRow
    from apps.worker.reconcile import (
        check_opening_closing,
        check_opening_closing_reverse,
        check_running_balance_monotonic,
        check_running_balance_reverse,
    )

    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    txn = dict(row) if row is not None and not isinstance(row, dict) else row
    if txn is None or txn.get("tenant_id") != tenant_id:
        raise ValueError(
            f"Invalid parameters: transaction '{transaction_id}' does not exist"
        )
    scope, chain = _chain_rows_for(tenant_id, txn, db)
    feed = []
    for r in chain:
        line_ids, quote = _row_line_evidence(r["id"], db)
        feed.append(
            ExtractedRow(
                line_ids=line_ids,
                date=r.get("txn_date") or "",
                description=r.get("description_raw") or "",
                # Reconcile convention is unsigned amount + direction (parsers
                # store abs(); ledger accepts both, so normalize here).
                amount_minor=abs(int(r.get("amount_minor") or 0)),
                direction=(r.get("direction") or "debit").lower(),
                balance_after_minor=r.get("balance_after_minor"),
                source_quote=quote or (r.get("description_raw") or ""),
            )
        )
    opening = closing = None
    if txn.get("document_id"):
        cur = db.execute(
            "SELECT opening_balance_minor, closing_balance_minor FROM extraction_runs"
            " WHERE document_id=? ORDER BY started_at DESC LIMIT 1",
            (txn["document_id"],),
        )
        run = cur.fetchone()
        if run:
            d = dict(run) if not isinstance(run, dict) else run
            opening, closing = (
                d.get("opening_balance_minor"),
                d.get("closing_balance_minor"),
            )
    oc_pass, oc_computed, oc_msg = check_opening_closing(opening, closing, feed)
    ocr_pass, ocr_computed, ocr_msg = check_opening_closing_reverse(
        closing, opening, feed
    )
    tb_pass, tb_breaks = check_running_balance_monotonic(feed)
    bt_pass, bt_breaks = check_running_balance_reverse(feed)
    return {
        "transaction_id": transaction_id,
        "scope": scope,
        "rows_checked": len(feed),
        "opening_closing": {
            "pass": oc_pass,
            "computed_closing_minor": oc_computed,
            "message": oc_msg,
        },
        "opening_closing_reverse": {
            "pass": ocr_pass,
            "computed_opening_minor": ocr_computed,
            "message": ocr_msg,
        },
        "running_top_bottom": {
            "pass": tb_pass,
            "breaks": tb_breaks[:10],
            "break_count": len(tb_breaks),
        },
        "running_bottom_top": {
            "pass": bt_pass,
            "breaks": bt_breaks[:10],
            "break_count": len(bt_breaks),
        },
        "overall_pass": oc_pass and ocr_pass and tb_pass and bt_pass,
    }


def trial_balance(
    tenant_id: str,
    as_of: Optional[str] = None,
    entity_id: Optional[str] = None,
    account_number: Optional[str] = None,
    db=None,
) -> Dict:
    """Trial balance per MODULES.md: debits, credits, zero check. Tenant-isolated."""
    if db is None:
        db = get_db()
    if not tenant_id:
        raise ValueError("Invalid parameters: tenant_id is required")
    bank_id = None
    unknown_only = account_number == "__unknown"
    if account_number and not unknown_only:
        brow = db.execute(
            "SELECT id FROM accounts WHERE tenant_id=? AND account_number=?",
            (tenant_id, account_number),
        ).fetchone()
        if not brow:
            raise ValueError(
                "Invalid parameters: unknown account_number"
                f" '{account_number}' for tenant"
            )
        bank_id = brow["id"] if isinstance(brow, dict) else brow[0]
    q = """
        SELECT a.id as account_id, a.code, a.name, a.type,
               COALESCE(SUM(jl.debit_minor),0) as debits,
               COALESCE(SUM(jl.credit_minor),0) as credits
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_id = a.id
        LEFT JOIN journal_entries je ON jl.entry_id = je.id AND je.tenant_id = a.tenant_id
        WHERE a.tenant_id = ?
    """
    params: list = [tenant_id]
    if unknown_only:
        q += (" AND (jl.entry_id IS NULL OR jl.entry_id IN (SELECT je2.id"
              " FROM journal_entries je2 JOIN transactions t"
              " ON je2.transaction_id=t.id WHERE t.tenant_id=?"
              " AND (t.account_number IS NULL OR t.account_number='')))")
        params.append(tenant_id)
    if bank_id:
        # Only entries touching the bank account; untouched accounts
        # fall out (their sums would be zero anyway). Balance holds:
        # every included entry is itself balanced.
        q += (" AND (jl.entry_id IS NULL OR jl.entry_id IN (SELECT entry_id"
              " FROM journal_lines WHERE account_id = ?))")
        params.append(bank_id)
    if as_of:
        q += " AND (je.entry_date IS NULL OR je.entry_date <= ?)"
        params.append(as_of)
    if entity_id:
        q += " AND (je.entity_id IS NULL OR je.entity_id = ?)"
        params.append(entity_id)
    q += " GROUP BY a.id, a.code, a.name, a.type ORDER BY a.code ASC"
    cur = db.execute(q, tuple(params))
    lines = []
    total_debits = 0
    total_credits = 0
    for r in cur.fetchall():
        d = dict(r) if not isinstance(r, dict) else r
        debits = int(d.get("debits") or 0)
        credits = int(d.get("credits") or 0)
        total_debits += debits
        total_credits += credits
        lines.append(
            {
                "account_id": d.get("account_id"),
                "code": d.get("code"),
                "name": d.get("name"),
                "type": d.get("type"),
                "debits": debits,
                "credits": credits,
                "net": debits - credits,
            }
        )
    return {
        "tenant_id": tenant_id,
        "as_of": as_of,
        "entity_id": entity_id,
        "account_number": account_number,
        "lines": lines,
        "total_debits": total_debits,
        "total_credits": total_credits,
        "balanced": total_debits == total_credits,
        "zero": total_debits - total_credits == 0,
    }


def get_journal_entries(
    tenant_id: str, transaction_id: Optional[str] = None, limit: int = 100, db=None
) -> List[Dict]:
    """List journal entries with lines for tenant (isolated)."""
    if db is None:
        db = get_db()
    q = "SELECT * FROM journal_entries WHERE tenant_id=?"
    params: list = [tenant_id]
    if transaction_id:
        q += " AND transaction_id=?"
        params.append(transaction_id)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    cur = db.execute(q, tuple(params))
    entries = []
    for r in cur.fetchall():
        e = dict(r) if not isinstance(r, dict) else r
        cur2 = db.execute(
            "SELECT jl.*, a.code, a.name FROM journal_lines jl"
            " LEFT JOIN accounts a ON jl.account_id=a.id WHERE jl.entry_id=?",
            (e["id"],),
        )
        e["lines"] = [
            dict(x) if not isinstance(x, dict) else x for x in cur2.fetchall()
        ]
        entries.append(e)
    return entries


SUSPENSE_CODE = "9999"
SUSPENSE_PCT_LIMIT = 0.05
SUSPENSE_MAX_AGE_DAYS = 30


def _suspense_age_days(oldest_created_at) -> Optional[int]:
    """Age in days of the oldest suspense entry (None when unparseable/empty)."""
    if not oldest_created_at:
        return None
    try:
        from datetime import datetime, timezone

        if hasattr(oldest_created_at, "year"):
            oldest = oldest_created_at
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
        else:
            text = str(oldest_created_at).strip().replace("T", " ")
            oldest = datetime.fromisoformat(text[:19])
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - oldest
        return max(0, delta.days)
    except (ValueError, TypeError, OverflowError):
        return None


def suspense_status(tenant_id: str, db=None) -> Dict:
    """9999 watchdog: suspense must stay small; every confirmed txn must be posted.

    Returns balance/count/aging vs thresholds plus the completeness check
    (confirmed transactions without any journal entry - must be zero, otherwise
    income/expense statements are incomplete).
    """
    if db is None:
        db = get_db()
    if not tenant_id:
        raise ValueError("Invalid parameters: tenant_id is required")
    # Only stuck money counts: per-transaction 9999 legs that do not net to zero.
    # Cleared transactions (re-decoded + transferred out) net to zero and never
    # trip the watchdog; failed transfers stay visible here. Portable HAVING form.
    cur = db.execute(
        "SELECT COALESCE(SUM(debits),0) AS debits, COALESCE(SUM(credits),0) AS credits,"
        " COUNT(*) AS txn_count, MIN(oldest) AS oldest FROM ("
        " SELECT SUM(jl.debit_minor) AS debits, SUM(jl.credit_minor) AS credits,"
        " MIN(je.created_at) AS oldest FROM journal_lines jl"
        " JOIN journal_entries je ON jl.entry_id=je.id"
        " JOIN accounts a ON jl.account_id=a.id"
        " WHERE je.tenant_id=? AND a.code=?"
        " GROUP BY je.transaction_id"
        " HAVING SUM(jl.debit_minor - jl.credit_minor) != 0)",
        (tenant_id, SUSPENSE_CODE),
    )
    row = cur.fetchone()
    d = dict(row) if row is not None and not isinstance(row, dict) else (row or {})
    debits = int(d.get("debits") or 0)
    credits = int(d.get("credits") or 0)
    txn_count = int(d.get("txn_count") or 0)
    age_days = _suspense_age_days(d.get("oldest"))
    cur = db.execute(
        "SELECT COALESCE(SUM(jl.debit_minor),0) AS total, COUNT(*) AS lines"
        " FROM journal_lines jl JOIN journal_entries je ON jl.entry_id=je.id"
        " WHERE je.tenant_id=?",
        (tenant_id,),
    )
    row = cur.fetchone()
    t = dict(row) if row is not None and not isinstance(row, dict) else (row or {})
    total_debits = int(t.get("total") or 0)
    cur = db.execute(
        "SELECT COUNT(*) AS c FROM transactions WHERE tenant_id=?", (tenant_id,)
    )
    row = cur.fetchone()
    total_txns = int((row["c"] if isinstance(row, dict) else row[0]) if row else 0)
    cur = db.execute(
        "SELECT t.id FROM transactions t WHERE t.tenant_id=? AND t.status='confirmed'"
        " AND NOT EXISTS (SELECT 1 FROM journal_entries je"
        " WHERE je.transaction_id=t.id AND je.tenant_id=t.tenant_id) LIMIT 50",
        (tenant_id,),
    )
    unposted = [(r["id"] if isinstance(r, dict) else r[0]) for r in cur.fetchall()]
    balance = debits - credits
    reasons = []
    if total_debits > 0 and abs(balance) > total_debits * SUSPENSE_PCT_LIMIT:
        reasons.append(
            f"suspense balance {balance}c exceeds {SUSPENSE_PCT_LIMIT:.0%} of postings"
        )
    if total_txns > 0 and txn_count > total_txns * SUSPENSE_PCT_LIMIT:
        reasons.append(
            f"suspense touches {txn_count}/{total_txns} transactions"
            f" (>{SUSPENSE_PCT_LIMIT:.0%})"
        )
    if age_days is not None and age_days > SUSPENSE_MAX_AGE_DAYS:
        reasons.append(
            f"oldest suspense item is {age_days}d old (>{SUSPENSE_MAX_AGE_DAYS}d)"
        )
    if unposted:
        reasons.append(
            f"{len(unposted)} confirmed transaction(s) have no journal entry"
            " - statements incomplete"
        )
    return {
        "tenant_id": tenant_id,
        "suspense_code": SUSPENSE_CODE,
        "balance_minor": balance,
        "debits_minor": debits,
        "credits_minor": credits,
        "txn_count": txn_count,
        "oldest_age_days": age_days,
        "total_debits_minor": total_debits,
        "total_txns": total_txns,
        "unposted_confirmed_count": len(unposted),
        "unposted_confirmed_ids": unposted,
        "thresholds": {
            "pct_limit": SUSPENSE_PCT_LIMIT,
            "max_age_days": SUSPENSE_MAX_AGE_DAYS,
        },
        "status": "review" if reasons else "ok",
        "reasons": reasons,
    }
