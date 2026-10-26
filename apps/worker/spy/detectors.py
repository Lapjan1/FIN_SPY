"""
Spy detectors: rule-first, AI explains second per homework 5.9.
All read from DB, not from extraction directly.
"""
from typing import List, Dict
from decimal import Decimal
import hashlib

def detect_recurring(transactions: List[Dict]) -> List[Dict]:
    """
    Same amount +/-5% + similar merchant + 28-32d cadence.
    """
    # TODO: group by normalized merchant + amount tolerance
    return []

def detect_duplicate(transactions: List[Dict]) -> List[Dict]:
    """
    fingerprint SHA256(date|amount|desc_norm) same + <24h near-duplicate.
    """
    seen = {}
    dups = []
    for tx in transactions:
        fp = tx.get('fingerprint_sha256')
        if fp in seen:
            dups.append({"type":"exact_duplicate","tx_id":tx['id'],"dup_of":seen[fp],"fingerprint":fp})
        else:
            seen[fp] = tx['id']
    return dups

def detect_fee(transactions: List[Dict]) -> List[Dict]:
    keywords = ['fee','service charge','fx','commission','bank charge']
    res = []
    for tx in transactions:
        desc = tx.get('description_raw','').lower()
        if any(k in desc for k in keywords):
            res.append({"type":"fee","tx_id":tx['id'],"description":tx['description_raw']})
    return res

def detect_anomaly_iqr(transactions: List[Dict]) -> List[Dict]:
    """
    IQR or z-score per category. Returns flags with evidence links.
    """
    # TODO: compute per category stats
    return []

def detect_private_use(transactions: List[Dict], owner_keywords: List[str]) -> List[Dict]:
    # Transactions to owners/family - user supplied list
    res = []
    for tx in transactions:
        desc = tx.get('description_raw','').lower()
        if any(k.lower() in desc for k in owner_keywords):
            res.append({"type":"related_party","tx_id":tx['id']})
    return res
