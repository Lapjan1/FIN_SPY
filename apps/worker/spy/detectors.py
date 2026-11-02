"""
Spy detectors: rule-first, AI explains second per homework 5.9.
All read from DB, not from extraction directly.
Flag codes: SUB subscription, DUP exact duplicate, NDUP 24h near-duplicate,
F-010 fee, F-020 leak (subscription creep), F-030 amount anomaly, BEN Benford.
Money in minor units (cents), never float.
"""
from typing import List, Dict
from datetime import datetime
import hashlib
import re

AMOUNT_TOLERANCE = 0.05  # +/-5%
CADENCE_MIN_DAYS = 25
CADENCE_MAX_DAYS = 35
MIN_OCCURRENCES = 3


def norm_merchant(desc: str) -> str:
    """Normalize description to a merchant key: lowercase, alnum runs only."""
    words = re.findall(r"[a-z0-9]+", (desc or "").lower())
    return " ".join(words)


def _parse_date(s: str):
    try:
        return datetime.fromisoformat((s or "")[:10]).date()
    except ValueError:
        return None


def detect_recurring(transactions: List[Dict]) -> List[Dict]:
    """
    Same amount +/-5% + similar merchant + 25-35d cadence, >=3 occurrences.
    Outflows only (debits). Returns one subscription per merchant run.
    """
    groups: Dict[str, List[Dict]] = {}
    for tx in transactions:
        if (tx.get("direction") or "debit").lower() != "debit":
            continue
        d = _parse_date(tx.get("txn_date", "") or tx.get("date", ""))
        if d is None:
            continue
        key = norm_merchant(tx.get("description_raw", "") or tx.get("description", ""))
        if not key:
            continue
        groups.setdefault(key, []).append({**tx, "_d": d})

    subs = []
    for merchant, txns in groups.items():
        txns.sort(key=lambda t: t["_d"])
        best = _longest_run(txns)
        if len(best) >= MIN_OCCURRENCES:
            amounts = sorted(int(t.get("amount_minor", 0)) for t in best)
            median = amounts[len(amounts) // 2]
            gaps = [(best[i + 1]["_d"] - best[i]["_d"]).days for i in range(len(best) - 1)]
            subs.append({
                "type": "recurring_subscription",
                "code": "SUB",
                "merchant": merchant,
                "amount_minor": median,
                "monthly_cost_minor": median,
                "cadence_days": sum(gaps) // len(gaps),
                "occurrences": len(best),
                "first_date": str(best[0]["_d"]),
                "last_date": str(best[-1]["_d"]),
                "tx_ids": [t.get("id") for t in best],
            })
    return subs


def _longest_run(txns: List[Dict]) -> List[Dict]:
    """Longest run where each gap is 25-35d and amount within 5% of anchor."""
    best: List[Dict] = []
    run: List[Dict] = []
    anchor = 0
    for tx in txns:
        amt = int(tx.get("amount_minor", 0))
        if not run:
            run, anchor = [tx], amt
            continue
        gap = (tx["_d"] - run[-1]["_d"]).days
        within = abs(amt - anchor) <= anchor * AMOUNT_TOLERANCE if anchor else False
        if CADENCE_MIN_DAYS <= gap <= CADENCE_MAX_DAYS and within:
            run.append(tx)
            continue
        if len(run) > len(best):
            best = run
        run, anchor = [tx], amt
    return run if len(run) > len(best) else best


def detect_duplicate(transactions: List[Dict]) -> List[Dict]:
    """
    fingerprint SHA256(date|amount|desc|balance) same -> exact duplicate.
    Same amount + same normalized desc within 1 calendar day but different
    fingerprint -> 24h near-duplicate.
    """
    dups = []
    seen = {}
    for tx in transactions:
        fp = tx.get("fingerprint_sha256")
        if fp in seen:
            dups.append({"type": "exact_duplicate", "code": "DUP",
                         "tx_id": tx.get("id"), "dup_of": seen[fp],
                         "fingerprint": fp})
        else:
            seen[fp] = tx.get("id")
    # Near-duplicate pass
    keyed = []
    for tx in transactions:
        d = _parse_date(tx.get("txn_date", "") or tx.get("date", ""))
        if d is None:
            continue
        keyed.append((norm_merchant(tx.get("description_raw", "") or tx.get("description", "")),
                      int(tx.get("amount_minor", 0)), d, tx))
    keyed.sort(key=lambda t: (t[0], t[1], t[2]))
    for i in range(1, len(keyed)):
        prev, cur = keyed[i - 1], keyed[i]
        if (prev[0] and prev[0] == cur[0] and prev[1] == cur[1]
                and abs((cur[2] - prev[2]).days) <= 1
                and prev[3].get("fingerprint_sha256") != cur[3].get("fingerprint_sha256")):
            dups.append({"type": "near_duplicate_24h", "code": "NDUP",
                         "tx_id": cur[3].get("id"), "dup_of": prev[3].get("id"),
                         "merchant": cur[0], "amount_minor": cur[1]})
    return dups


FEE_KEYWORDS = ["fee", "service charge", "service fee", "fx", "commission",
                "bank charge", "account fee", "monthly fee", "transaction fee",
                "atm fee", "card fee", "admin fee", "penalty", "late payment",
                "dishonour", "dishonor"]


def detect_fee(transactions: List[Dict]) -> List[Dict]:
    """F-010: bank/service fee keyword hits with amounts summed by caller."""
    res = []
    for tx in transactions:
        desc = tx.get("description_raw", "") or tx.get("description", "")
        if any(k in desc.lower() for k in FEE_KEYWORDS):
            res.append({"type": "fee", "code": "F-010", "tx_id": tx.get("id"),
                        "description": desc,
                        "amount_minor": int(tx.get("amount_minor", 0))})
    return res


def detect_anomaly_iqr(transactions: List[Dict]) -> List[Dict]:
    """
    F-030: per-merchant IQR outlier. Groups with >=5 outflows; flags amounts
    above Q3 + 1.5*IQR. Evidence links via tx_id + merchant stats.
    """
    groups: Dict[str, List[Dict]] = {}
    for tx in transactions:
        if (tx.get("direction") or "debit").lower() != "debit":
            continue
        key = norm_merchant(tx.get("description_raw", "") or tx.get("description", ""))
        if key:
            groups.setdefault(key, []).append(tx)
    flags = []
    for merchant, txns in groups.items():
        if len(txns) < 5:
            continue
        amounts = sorted(int(t.get("amount_minor", 0)) for t in txns)
        q1 = amounts[len(amounts) // 4]
        q3 = amounts[(3 * len(amounts)) // 4]
        iqr = q3 - q1
        fence = q3 + 1.5 * iqr
        for tx in txns:
            amt = int(tx.get("amount_minor", 0))
            if amt > fence:
                flags.append({"type": "anomaly_amount", "code": "F-030",
                              "tx_id": tx.get("id"), "merchant": merchant,
                              "amount_minor": amt, "fence_minor": int(fence),
                              "group_median_minor": amounts[len(amounts) // 2]})
    return flags


def detect_benford(transactions: List[Dict]) -> List[Dict]:
    """
    BEN: first-digit smoke test on outflows. Benford expects ~30% leading 1s;
    with n>=20, flag when the digit-1 share is <15% or >45% (fabricated or
    threshold-gamed books). Single aggregate flag, not per-txn.
    """
    digits = []
    for tx in transactions:
        if (tx.get("direction") or "debit").lower() != "debit":
            continue
        amt = int(tx.get("amount_minor", 0))
        if amt > 0:
            digits.append(str(amt)[0])
    if len(digits) < 20:
        return []
    share_one = sum(1 for d in digits if d == "1") / len(digits)
    if share_one < 0.15 or share_one > 0.45:
        return [{"type": "benford_deviation", "code": "BEN",
                 "n": len(digits), "digit_one_share": round(share_one, 3),
                 "expected": 0.301}]
    return []


def leak_score_per_month(transactions: List[Dict]) -> int:
    """F-020: subscription creep R/mo = sum of recurring monthly costs."""
    return sum(s["monthly_cost_minor"] for s in detect_recurring(transactions))


def detect_private_use(transactions: List[Dict], owner_keywords: List[str]) -> List[Dict]:
    # Transactions to owners/family - user supplied list
    res = []
    for tx in transactions:
        desc = (tx.get("description_raw", "") or tx.get("description", "")).lower()
        if any(k.lower() in desc for k in owner_keywords):
            res.append({"type": "related_party", "code": "RP", "tx_id": tx.get("id")})
    return res


def flag_id(tenant_id: str, code: str, key: str) -> str:
    """Deterministic flag id so spy re-runs overwrite, never duplicate."""
    return hashlib.sha256(f"{tenant_id}|{code}|{key}".encode()).hexdigest()[:16]
