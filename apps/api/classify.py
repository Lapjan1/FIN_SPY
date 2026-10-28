"""
Classify: private/business/mixed + category + rationale, source rule/ai/human, revision chain.
Per docs/MODULES.md classify + docs/TIMELINE.md Day4 + prompts/classify_private_business_v1.md v1.1.0.

Rules-first AI-second human-last. Private/business only; mixed exceptional startup
(sole prop person trading as) per docs/DISCLAIMER.md. Informative with acts reference.
All writes append-only: new classification row supersedes previous, never updates.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from .db import get_db, append_audit_log


VALID_NATURES = ("business", "private", "mixed", "unknown")

# Deterministic AI-second heuristics (no hosted call; prompt text lives in prompts/*.md).
_PRIVATE_KEYWORDS = (
    "woolworths",
    "checkers",
    "spar",
    "picknpay",
    "shoprite",
    "clothing",
    "school",
    "netflix",
    "dstv",
    "discovery",
    "cash withdrawal",
    "atm",
    "transfer to savings",
)
_BUSINESS_KEYWORDS = (
    "supplier",
    "fuel",
    "sasol",
    "engen",
    "shell",
    "rent",
    "eskom",
    "telkom",
    "vodacom",
    "mtn",
    "salary",
    "wages",
    "sars",
    "cipc",
    "professional fees",
    "marketing",
    "takealot",
)
_SHARED_KEYWORDS = (
    "fuel",
    "vehicle",
    "rent",
    "utilities",
    "cellphone",
    "internet",
    " Sasol".lower().strip(),
    "engen",
    "shell",
)

_CATEGORY_BY_KEYWORD = (
    ("fuel", "6200"),
    ("sasol", "6200"),
    ("engen", "6200"),
    ("shell", "6200"),
    ("rent", "6100"),
    ("marketing", "6000"),
    ("salary", "6300"),
    ("wages", "6300"),
    ("bank charges", "6600"),
    ("service fee", "6600"),
    ("woolworths", "6020"),
    ("checkers", "6020"),
    ("spar", "6020"),
    ("picknpay", "6020"),
    ("shoprite", "6020"),
    ("eskom", "6400"),
    ("telkom", "6400"),
    ("vodacom", "6400"),
    ("mtn", "6400"),
)


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row) if not isinstance(row, dict) else row


def _category_for(description: str, direction: str) -> str:
    desc = (description or "").lower()
    for keyword, code in _CATEGORY_BY_KEYWORD:
        if keyword in desc:
            return code
    # Inflow defaults to sales, outflow to general expense
    if direction == "credit":
        return "4000"
    return "6000"


def _rule_suggest(
    description: str, account_number: str, tenant_id: str, direction: Optional[str]
) -> Optional[Dict]:
    """Rules-first lookup in tenant merchant_memory. Returns suggestion or None."""
    try:
        from .vendor import suggest_classification_with_merchant_memory

        mem = suggest_classification_with_merchant_memory(
            description, account_number, tenant_id
        )
    except Exception:
        return None
    if not mem or mem.get("nature") not in VALID_NATURES:
        return None
    return {
        "nature": mem["nature"],
        "business_pct": int(mem.get("business_pct", 100)),
        "category_id": mem.get("category_id")
        or _category_for(description, direction or ""),
        "rationale": mem.get("rationale")
        or f"Tenant rule: merchant memory per merchant per account for '{description[:40]}'.",
        "source": "rule",
        "confidence": float(mem.get("confidence", 1.0)),
    }


def _heuristic_suggest(
    desc: str,
    direction: str,
    category_id: str,
    entity_kind: str,
    amount_minor: Optional[int],
) -> Dict:
    """AI-second deterministic heuristics with acts-aware rationale."""
    is_shared = any(k in desc for k in _SHARED_KEYWORDS)
    if entity_kind in ("sole_prop", "mixed_sole_prop", "mixed") and is_shared:
        return {
            "nature": "mixed",
            "business_pct": 60,
            "category_id": category_id,
            "rationale": (
                "Sole prop mixed 60% business per Income Tax Act s11(a) "
                "wholly/exclusively - exceptional startup case, user deals with "
                "auditor and SARS. Suggest split, human decides."
            ),
            "source": "ai",
            "confidence": 0.65,
        }
    if any(k in desc for k in _PRIVATE_KEYWORDS):
        rationale = (
            "Private indicators in description - suggest private. For registered "
            "business (Pty Ltd), private in company bank is an exception per "
            "Companies Act s19 s28 s76, should be drawings/director loan."
        )
        return {
            "nature": "private",
            "business_pct": 0,
            "category_id": category_id,
            "rationale": rationale,
            "source": "ai",
            "confidence": 0.75,
        }
    if any(k in desc for k in _BUSINESS_KEYWORDS):
        return {
            "nature": "business",
            "business_pct": 100,
            "category_id": category_id,
            "rationale": "Business indicators in description - suggest business, human decides.",
            "source": "ai",
            "confidence": 0.75,
        }
    if direction == "credit" and abs(amount_minor or 0) >= 10000:
        return {
            "nature": "business",
            "business_pct": 100,
            "category_id": "4000",
            "rationale": "Large inflow - suggest business sales, human decides.",
            "source": "ai",
            "confidence": 0.6,
        }
    # Unknown parks in 9999 suspense so statements stay complete; human re-decodes later.
    return {
        "nature": "unknown",
        "business_pct": 0,
        "category_id": "9999",
        "rationale": "Insufficient evidence - parked in 9999 Suspense pending human review.",
        "source": "human",
        "confidence": 0.0,
    }


def suggest_classification(
    description: str,
    account_number: str,
    tenant_id: str,
    entity_kind: str = "personal",
    amount_minor: Optional[int] = None,
    direction: Optional[str] = None,
    txn_date: Optional[str] = None,
    db=None,
) -> Dict:
    """Rules-first, AI-second, human-last suggestion. Never finalizes.

    Returns {nature, business_pct, category_id, rationale, source, confidence}.
    """
    if not tenant_id:
        raise ValueError("Invalid parameters: tenant_id is required")
    if description is None or account_number is None:
        raise ValueError(
            "Invalid parameters: description and account_number are required"
        )

    ruled = _rule_suggest(description, account_number, tenant_id, direction)
    if ruled:
        return ruled

    desc = (description or "").lower()
    direction = (direction or "").lower()
    if direction not in ("credit", "debit"):
        direction = "credit" if (amount_minor or 0) > 0 else "debit"
    return _heuristic_suggest(
        desc,
        direction,
        _category_for(description, direction),
        (entity_kind or "personal").lower(),
        amount_minor,
    )


def _validate_decide_inputs(
    transaction_id: str,
    nature: str,
    business_pct: int,
    category_id: str,
    reason: str,
    tenant_id: str,
) -> str:
    """Validate decide inputs. Returns stripped category code."""
    if not transaction_id or not tenant_id:
        raise ValueError(
            "Invalid parameters: transaction_id and tenant_id are required"
        )
    if nature not in VALID_NATURES:
        raise ValueError(
            f"Invalid parameters: nature must be {'|'.join(VALID_NATURES)}, got '{nature}'"
        )
    if not isinstance(business_pct, int) or not (0 <= business_pct <= 100):
        raise ValueError(
            f"Invalid parameters: business_pct must be int 0-100, got '{business_pct}'"
        )
    if not reason or not reason.strip():
        raise ValueError("Invalid parameters: reason is required for audit trail")
    if not category_id or not str(category_id).strip():
        raise ValueError("Invalid parameters: category_id is required")
    return str(category_id).strip()


def _load_owned_txn(transaction_id: str, tenant_id: str, db) -> Dict:
    """Load transaction, enforcing tenant isolation."""
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    txn = _row_to_dict(cur.fetchone())
    if not txn:
        raise ValueError(
            f"Invalid parameters: transaction '{transaction_id}' does not exist"
        )
    if txn.get("tenant_id") != tenant_id:
        raise PermissionError("Cross-tenant access denied - isolation guard")
    return txn


def _learn_merchant_memory(
    txn: Dict,
    tenant_id: str,
    target_account_id: str,
    category_code: str,
    nature: str,
    business_pct: int,
    rationale: str,
    actor_id: Optional[int],
    db,
) -> None:
    """Upsert merchant memory per merchant per account (best-effort learning)."""
    try:
        from .vendor import normalize_merchant

        norm = normalize_merchant(txn.get("description_raw") or "")
        acct_no = txn.get("account_number") or ""
        if norm and acct_no:
            db.execute(
                "INSERT OR REPLACE INTO merchant_memory (id, tenant_id, normalized_merchant,"
                " account_number, account_id, category_id, nature, business_pct, rationale,"
                " source, confidence, decided_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"mem-{uuid.uuid4().hex[:8]}",
                    tenant_id,
                    norm,
                    acct_no,
                    target_account_id,
                    category_code,
                    nature,
                    business_pct,
                    (rationale or "")[:500],
                    "human",
                    1.0,
                    actor_id,
                ),
            )
    except Exception:
        pass


def decide(
    transaction_id: str,
    nature: str,
    business_pct: int,
    category_id: str,
    rationale: str,
    actor_id: Optional[int],
    reason: str,
    tenant_id: str,
    db=None,
) -> Dict:
    """Human decision: append-only classification revision + merchant memory + audit.

    Raises ValueError('Invalid parameters...') on bad input,
    PermissionError('Cross-tenant...') on isolation violation.
    """
    if db is None:
        db = get_db()
    category_code = _validate_decide_inputs(
        transaction_id, nature, business_pct, category_id, reason, tenant_id
    )
    txn = _load_owned_txn(transaction_id, tenant_id, db)

    # Category must exist for tenant (never work on non-existing accounts)
    from .ledger import resolve_account, UnknownAccount

    try:
        target_acct = resolve_account(tenant_id, code=category_code, db=db)
    except UnknownAccount as e:
        raise ValueError(str(e))

    # Previous revision (append-only chain)
    cur = db.execute(
        "SELECT * FROM classifications WHERE transaction_id=? AND tenant_id=? "
        "ORDER BY decided_at_utc DESC LIMIT 1",
        (transaction_id, tenant_id),
    )
    prev = _row_to_dict(cur.fetchone())

    cls_id = f"cls-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO classifications (id, tenant_id, transaction_id, nature, business_pct,"
        " category_id, rationale, source, confidence, decided_by, decided_at_utc, supersedes_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            cls_id,
            tenant_id,
            transaction_id,
            nature,
            business_pct,
            category_code,
            rationale or "",
            "human",
            1.0,
            actor_id,
            now,
            prev["id"] if prev else None,
        ),
    )

    # Revision log (append-only)
    db.execute(
        "INSERT INTO transaction_revisions (id, tenant_id, transaction_id, field,"
        " old_value, new_value, reason, actor_id, at_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            f"rev-{uuid.uuid4().hex[:8]}",
            tenant_id,
            transaction_id,
            "classification",
            prev["id"] if prev else None,
            cls_id,
            reason.strip(),
            actor_id,
            now,
        ),
    )

    _learn_merchant_memory(
        txn,
        tenant_id,
        target_acct["id"],
        category_code,
        nature,
        business_pct,
        rationale or "",
        actor_id,
        db,
    )

    db.commit()

    # Re-decode: move the posted leg when the category changed (e.g. 9999 -> real).
    # Keeps suspense small and statements correct. No-op when never posted.
    # A failed transfer never blocks the decision, but is recorded visibly.
    transfer = None
    transfer_error = None
    prev_code = (prev.get("category_id") if prev else None) or ""
    if prev and prev_code and prev_code != category_code:
        from .ledger import transfer_posting

        try:
            transfer = transfer_posting(
                tenant_id,
                transaction_id,
                prev_code,
                category_code,
                created_by=actor_id,
                reason=reason.strip(),
                db=db,
            )
        except (ValueError, PermissionError) as e:
            transfer_error = str(e)

    append_audit_log(
        tenant_id,
        actor_id,
        "classify.decide",
        "classifications",
        cls_id,
        {
            "transaction_id": transaction_id,
            "nature": nature,
            "business_pct": business_pct,
            "category_id": category_code,
            "supersedes": prev["id"] if prev else None,
            "transfer_entry_id": transfer["id"] if transfer else None,
            "transfer_error": transfer_error,
        },
    )
    result = {
        "id": cls_id,
        "tenant_id": tenant_id,
        "transaction_id": transaction_id,
        "nature": nature,
        "business_pct": business_pct,
        "category_id": category_code,
        "rationale": rationale or "",
        "source": "human",
        "confidence": 1.0,
        "decided_by": actor_id,
        "supersedes_id": prev["id"] if prev else None,
    }
    if transfer:
        result["transfer_entry_id"] = transfer["id"]
    if transfer_error:
        result["transfer_error"] = transfer_error
    return result
