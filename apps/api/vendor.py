"""
Vendor rules per merchant per account - per user question: export vendor and add all transactions to certain account if like, sort and add rule, if certain code applies journal auto books other side
For competition not lifetime project, per merchant per account rules for presentation layer vendor grouping and % allocation
"""
import uuid
import re
from typing import List, Dict, Optional
from datetime import datetime, timezone

from .db import get_db, append_audit_log

def normalize_merchant(description: str) -> str:
    """Normalize merchant name for grouping: lower, trim, remove numbers, first word etc"""
    desc = description.lower().strip()
    # Remove common prefixes
    desc = re.sub(r'^(pos purchase|pos|purchase|payment to|internet pmt to|eft|rtgs|fnbapppaymentto|magtape debit)\s*', '', desc, flags=re.I)
    # First word as vendor
    vendor = desc.split()[0] if desc.split() else desc
    # Remove non-alpha
    vendor = re.sub(r'[^a-z0-9]', '', vendor)
    return vendor[:50]

def get_vendors(tenant_id: str) -> List[Dict]:
    """List vendors with counts, amounts, cadence for subscription radar wow factor"""
    db = get_db()
    cur = db.execute("""
        SELECT LOWER(TRIM(description_raw)) as raw_desc, COUNT(*) as cnt, SUM(amount_minor) as total_minor,
               MIN(txn_date) as first_date, MAX(txn_date) as last_date
        FROM transactions WHERE tenant_id=? GROUP BY LOWER(TRIM(description_raw)) ORDER BY cnt DESC LIMIT 100
    """, (tenant_id,))
    rows = cur.fetchall()
    vendors = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        # Normalize merchant
        norm = normalize_merchant(d.get('raw_desc',''))
        vendors.append({
            "normalized_merchant": norm,
            "raw_description": d.get('raw_desc'),
            "count": d.get('cnt'),
            "total_minor": d.get('total_minor'),
            "first_date": d.get('first_date'),
            "last_date": d.get('last_date'),
        })
    # Aggregate by normalized merchant
    from collections import defaultdict
    agg = defaultdict(lambda: {"count":0,"total_minor":0,"examples":[]})
    for v in vendors:
        key = v["normalized_merchant"]
        agg[key]["count"] += v["count"]
        agg[key]["total_minor"] += v["total_minor"] or 0
        agg[key]["examples"].append(v["raw_description"])
        agg[key]["first_date"] = min(agg[key].get("first_date","9999"), v["first_date"] or "9999")
        agg[key]["last_date"] = max(agg[key].get("last_date","0000"), v["last_date"] or "0000")

    result = []
    for norm, data in agg.items():
        # Detect recurring: count >=3 and cadence monthly +/-3days amount +/-5% per detectors.py
        # Simplified: count >=3
        is_recurring = data["count"] >= 3
        result.append({
            "normalized_merchant": norm,
            "count": data["count"],
            "total_minor": data["total_minor"],
            "avg_minor": data["total_minor"] // data["count"] if data["count"] else 0,
            "is_recurring": is_recurring,
            "first_date": data["first_date"],
            "last_date": data["last_date"],
            "examples": data["examples"][:3],
        })

    return sorted(result, key=lambda x: x["count"], reverse=True)

def create_vendor_rule(tenant_id: str, normalized_merchant: str, account_number: str, target_account_id: str, target_category_id: str = None, nature: str = "business", business_pct: int = 100, auto_book: bool = False, decided_by: int = None) -> str:
    """
    Create rule per merchant per account: export vendor and add all transactions to certain account if like, sort and add rule, if certain code applies journal auto books other side
    Per user: per merchant per account for competition not lifetime. Validates we never work on non-existing accounts.
    """
    db = get_db()
    if not normalized_merchant or not normalized_merchant.strip():
        raise ValueError("Invalid parameters: normalized_merchant is required")
    if not account_number or not account_number.strip():
        raise ValueError("Invalid parameters: account_number is required")
    if not target_account_id or not target_account_id.strip():
        raise ValueError("Invalid parameters: target_account_id is required")
    if nature not in ("business", "private", "mixed", "unknown"):
        raise ValueError(f"Invalid parameters: nature must be business|private|mixed|unknown, got '{nature}'")
    if not isinstance(business_pct, int) or not (0 <= business_pct <= 100):
        raise ValueError(f"Invalid parameters: business_pct must be int 0-100, got '{business_pct}'")
    # Validate target account exists for this tenant (never work on non-existing accounts)
    cur = db.execute("SELECT id, template FROM accounts WHERE id=? AND tenant_id=?", (target_account_id, tenant_id))
    acc = cur.fetchone()
    if not acc:
        raise ValueError(f"Invalid parameters: target_account_id '{target_account_id}' does not exist for tenant '{tenant_id}'. Seed COA first and use an existing account.")
    rule_id = f"rule-{uuid.uuid4().hex[:8]}"
    # Normalize merchant
    norm = normalize_merchant(normalized_merchant)

    # Insert into merchant_memory for classification (presentation layer)
    try:
        db.execute("""
            INSERT OR REPLACE INTO merchant_memory (id, tenant_id, normalized_merchant, account_number, account_id, category_id, nature, business_pct, rationale, source, confidence, decided_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (f"mem-{uuid.uuid4().hex[:8]}", tenant_id, norm, account_number, target_account_id, target_category_id, nature, business_pct, f"Tenant rule merchant_memory per merchant per account: {norm} in {account_number} -> {target_category_id} per user", "rule", 1.0, decided_by))
    except Exception as e:
        pass

    # Insert into vendor_rules for auto-booking when code applies
    try:
        db.execute("""
            INSERT OR REPLACE INTO vendor_rules (id, tenant_id, normalized_merchant, account_number, target_account_id, target_category_id, nature, business_pct, auto_book, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (rule_id, tenant_id, norm, account_number, target_account_id, target_category_id, nature, business_pct, 1 if auto_book else 0, decided_by))
    except Exception as e:
        # If table not exists yet, ignore
        pass

    db.commit()

    # Audit log
    append_audit_log(tenant_id, decided_by, "vendor_rule.create", "vendor_rules", rule_id, {"normalized_merchant": norm, "account_number": account_number, "target_account_id": target_account_id, "category_id": target_category_id, "nature": nature, "business_pct": business_pct, "auto_book": auto_book})

    return rule_id

def get_vendor_rules(tenant_id: str, account_number: str = None) -> List[Dict]:
    db = get_db()
    if account_number:
        cur = db.execute("SELECT * FROM vendor_rules WHERE tenant_id=? AND account_number=? ORDER BY created_at DESC", (tenant_id, account_number))
    else:
        cur = db.execute("SELECT * FROM vendor_rules WHERE tenant_id=? ORDER BY created_at DESC", (tenant_id,))
    rows = cur.fetchall()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]

def suggest_classification_with_merchant_memory(description: str, account_number: str, tenant_id: str) -> Optional[Dict]:
    """
    Suggest classification using merchant_memory per merchant per account - rules first per docs/DISCLAIMER.md
    Returns dict with category_id, nature, business_pct, account_id etc if rule exists
    """
    norm = normalize_merchant(description)
    db = get_db()
    # Try exact match per merchant per account
    cur = db.execute("SELECT * FROM merchant_memory WHERE tenant_id=? AND normalized_merchant=? AND account_number=? ORDER BY created_at DESC LIMIT 1", (tenant_id, norm, account_number))
    row = cur.fetchone()
    if row:
        d = dict(row) if not isinstance(row, dict) else row
        return {
            "category_id": d.get("category_id"),
            "account_id": d.get("account_id"),
            "nature": d.get("nature"),
            "business_pct": d.get("business_pct"),
            "source": "rule",
            "confidence": 1.0,
            "rationale": d.get("rationale")
        }
    # Try per merchant alone across all accounts
    cur = db.execute("SELECT * FROM merchant_memory WHERE tenant_id=? AND normalized_merchant=? ORDER BY created_at DESC LIMIT 1", (tenant_id, norm))
    row = cur.fetchone()
    if row:
        d = dict(row) if not isinstance(row, dict) else row
        return {
            "category_id": d.get("category_id"),
            "account_id": d.get("account_id"),
            "nature": d.get("nature"),
            "business_pct": d.get("business_pct"),
            "source": "rule",
            "confidence": 0.9,
            "rationale": d.get("rationale")
        }
    return None

def _post_entry(entry_id: str) -> bool:
    """Post a drafted entry: DB trigger verifies balance. Returns False + rollback on failure."""
    db = get_db()
    try:
        db.execute("UPDATE journal_entries SET posted=1 WHERE id=?", (entry_id,))
    except Exception:
        try:
            db.conn.rollback()
        except Exception:
            pass
        return False
    return True


def auto_book_journal_for_rule(transaction_id: str, rule: Dict) -> bool:
    """
    If certain code applies journal auto books other side per user question
    When rule has auto_book=1 and target_account_id, create journal entry with balanced lines
    Example: If category_id=6100 Rent maps to accounts.code=6100 expense, then Dr 6100 expense + Cr Bank account_number
    """
    db = get_db()
    # Get transaction
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    txn_row = cur.fetchone()
    if not txn_row:
        return False
    txn = dict(txn_row) if not isinstance(txn_row, dict) else txn_row
    amount_minor = txn.get("amount_minor", 0)
    tenant_id = txn.get("tenant_id")
    account_number = txn.get("account_number") or rule.get("account_number")
    target_account_id = rule.get("target_account_id")
    target_category_id = rule.get("target_category_id")
    nature = rule.get("nature", "business")
    business_pct = rule.get("business_pct", 100)

    if not target_account_id:
        return False

    # Find bank account id from transaction's account_number or use transaction's account_id
    bank_account_id = txn.get("account_id")
    if not bank_account_id:
        # Try to find bank account by account_number
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND account_number=?", (tenant_id, account_number))
        row = cur.fetchone()
        if row:
            bank_account_id = row["id"] if isinstance(row, dict) else row[0]

    # Create journal entry
    entry_id = f"je-{uuid.uuid4().hex[:8]}"
    db.execute("INSERT INTO journal_entries (id, tenant_id, entry_date, memo, transaction_id) VALUES (?,?,?, ?,?)",
               (entry_id, tenant_id, txn.get("txn_date"), f"Auto-book for {rule.get('normalized_merchant')} per rule {rule.get('id')}", transaction_id))

    # Split logic for mixed exceptional startup: business_pct
    # For simplicity, if business_pct=100, single line expense + bank
    # If mixed 60% business 40% private, split: Dr Expense 60% + Dr Drawings 40% / Cr Bank 100%
    if business_pct < 100 and business_pct > 0:
        business_amount = int(amount_minor * business_pct / 100)
        private_amount = amount_minor - business_amount
        # Dr expense business portion
        db.execute("INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                   (f"jl-{uuid.uuid4().hex[:6]}", entry_id, target_account_id, business_amount, 0))
        # Dr drawings private portion if exists account 7000
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND code='7000' LIMIT 1", (tenant_id,))
        drawings_row = cur.fetchone()
        if drawings_row:
            drawings_id = drawings_row["id"] if isinstance(drawings_row, dict) else drawings_row[0]
            db.execute("INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                       (f"jl-{uuid.uuid4().hex[:6]}", entry_id, drawings_id, private_amount, 0))
        # Cr bank
        if bank_account_id:
            db.execute("INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                       (f"jl-{uuid.uuid4().hex[:6]}", entry_id, bank_account_id, 0, amount_minor))
    else:
        # Simple: Dr expense target, Cr bank
        db.execute("INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                   (f"jl-{uuid.uuid4().hex[:6]}", entry_id, target_account_id, amount_minor, 0))
        if bank_account_id:
            db.execute("INSERT INTO journal_lines (id, entry_id, account_id, debit_minor, credit_minor) VALUES (?,?,?,?,?)",
                       (f"jl-{uuid.uuid4().hex[:6]}", entry_id, bank_account_id, 0, amount_minor))

    # Post: DB trigger verifies balance (Day4 mechanism - draft freely, enforce at post)
    if not _post_entry(entry_id):
        return False
    db.commit()
    return True
