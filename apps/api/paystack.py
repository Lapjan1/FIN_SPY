"""
Paystack adapter - Based on clearmind-ai/app.py:63-360 + ClearFlag/routes/paystack.js hardening
- env_or_setting pattern (env overrides DB)
- has_paystack() checks sk_test|sk_live (bug fix from clearmind PROJECT_NOTES.md:52)
- Checkout initialize 37000 ZAR clearmind vs FIN_SPY 14900/59900, callback verify, webhook with timingSafeEqual
- Plan mapping free 20 pages / individual 200 / sme 1000 (vs clearmind 5 sessions)
- Timing-safe verify via hmac.compare_digest per ClearFlag lib, not plain ==

Per AGENTS.md: PAYSTACK_SECRET_KEY worker? Actually api only, never in browser.
Webhook verifies x-paystack-signature HMAC SHA512 raw body, idempotent via webhook_events.
"""
import os
import hmac
import hashlib
import json
import requests
from typing import Dict, Optional
from datetime import datetime, timezone

from .db import get_db, get_setting, env_or_setting, append_audit_log

def get_paystack_sk() -> str:
    return env_or_setting('paystack_secret_key', '')

def get_paystack_pk() -> str:
    return env_or_setting('paystack_public_key', '')

def get_paystack_plan_individual() -> str:
    # FIN_SPY plans JSON or single codes - support both clearmind style and new JSON
    plans_json = env_or_setting('paystack_plan_codes_json', '')
    if plans_json:
        try:
            data = json.loads(plans_json)
            return data.get('individual', data.get('plan', ''))
        except:
            pass
    return env_or_setting('paystack_plan_code', '') or env_or_setting('paystack_plan_individual', '')

def get_paystack_plans() -> Dict[str, str]:
    raw = env_or_setting('paystack_plan_codes_json', '')
    if raw:
        try:
            return json.loads(raw)
        except:
            pass
    # Fallback to single plan code like clearmind
    single = env_or_setting('paystack_plan_code', '')
    if single:
        return {"individual": single}
    return {}

def has_paystack() -> bool:
    sk = get_paystack_sk()
    return bool(sk) and ('sk_test' in sk or 'sk_live' in sk)

def plan_key_from_paystack_code(code: str) -> str:
    """
    Map Paystack plan code to internal plan_key, like ClearFlag lib/plans.js planKeyFromPaystackCode
    """
    plans = get_paystack_plans()
    for k, v in plans.items():
        if v == code:
            return k
    # Fallback heuristic
    if 'sme' in code.lower() or 'growth' in code.lower():
        return 'sme'
    if 'individual' in code.lower() or 'starter' in code.lower():
        return 'individual'
    return 'individual'

def plan_details(plan_code: str) -> Dict:
    """
    FIN_SPY plans per docs/decision 0001: free 20 pages, individual 200, sme 1000
    vs clearmind 5 sessions R370
    """
    mapping = {
        "free": {"name": "Free", "pages": 20, "amount_minor": 0, "price_display": "R0"},
        "individual": {"name": "Individual", "pages": 200, "amount_minor": 14900, "price_display": "R149/mo"},
        "sme": {"name": "SME", "pages": 1000, "amount_minor": 59900, "price_display": "R599/mo"},
        "practice": {"name": "Practice", "pages": 5000, "amount_minor": 199900, "price_display": "R1999/mo"},
    }
    return mapping.get(plan_code, mapping["individual"])

def verify_paystack_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Timing-safe verify per ClearFlag/routes/paystack.js verifyPaystackSignature
    Uses HMAC SHA512 of raw body with secret key, constant time compare.
    """
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
    # Use constant time compare
    return hmac.compare_digest(expected, signature)

def initialize_transaction(email: str, plan_code: str, callback_url: str, user_id: int, tenant_id: str) -> Dict:
    """
    Like clearmind app.py:253-281 /subscribe
    """
    details = plan_details(plan_code)
    # If free plan, no paystack needed - return early before has_paystack check per red test
    if details["amount_minor"] == 0:
        return {"status": True, "free": True, "plan_code": plan_code}
    if not has_paystack():
        raise ValueError("Paystack not configured - missing sk_test|sk_live")
    sk = get_paystack_sk()
    plans = get_paystack_plans()
    paystack_plan_code = plans.get(plan_code, get_paystack_plan_individual())
    body = {
        "email": email,
        "amount": details["amount_minor"],
        "currency": "ZAR",
        "plan": paystack_plan_code,
        "callback_url": callback_url,
        "metadata": {"user_id": user_id, "tenant_id": tenant_id, "plan_code": plan_code}
    }
    headers = {"Authorization": f"Bearer {sk}", "Content-Type": "application/json"}
    resp = requests.post("https://api.paystack.co/transaction/initialize", json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("status"):
        raise ValueError(f"Paystack init failed: {data}")
    return data["data"]

def verify_transaction(reference: str) -> Dict:
    sk = get_paystack_sk()
    headers = {"Authorization": f"Bearer {sk}"}
    resp = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]

def create_subscription(customer_code: str, plan_code: str, authorization_code: str) -> Dict:
    sk = get_paystack_sk()
    plans = get_paystack_plans()
    paystack_plan_code = plans.get(plan_code, get_paystack_plan_individual())
    body = {
        "customer": customer_code,
        "plan": paystack_plan_code,
        "authorization": authorization_code
    }
    headers = {"Authorization": f"Bearer {sk}", "Content-Type": "application/json"}
    resp = requests.post("https://api.paystack.co/subscription", json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]

def _maybe_send_dunning(event_type: str, user, tenant_id: str) -> None:
    """Dunning email on failed payments; 7-day grace per template, status untouched."""
    if "failed" not in event_type:
        return
    try:
        from .email import send_payment_failed_email
        uemail = user["email"] if isinstance(user, dict) else (user[2] if len(user) > 2 else "")
        if uemail:
            send_payment_failed_email(uemail, tenant_id=tenant_id)
    except Exception:
        pass


def handle_webhook_event(event_type: str, event_data: Dict) -> Optional[str]:
    """
    Like clearmind app.py:328-360 + ClearFlag paystack.js
    Handles charge.success, subscription.create, invoice.success, subscription.disable
    Returns tenant_id/user_id affected for audit
    """
    db = get_db()
    # Extract email from various Paystack payload shapes
    email = ""
    customer_code = ""
    subscription_code = ""
    authorization_code = ""
    try:
        if "customer" in event_data:
            cust = event_data["customer"]
            if isinstance(cust, dict):
                email = cust.get("email", "")
                customer_code = cust.get("customer_code", "")
            else:
                customer_code = str(cust)
        if "data" in event_data and isinstance(event_data["data"], dict):
            # Nested
            inner = event_data["data"]
            if "customer" in inner and isinstance(inner["customer"], dict):
                email = inner["customer"].get("email", email)
    except:
        pass

    # Find user by paystack_customer_code or email
    user = None
    if customer_code:
        cur = db.execute("SELECT id, tenant_id, email FROM users WHERE paystack_customer_code=?", (customer_code,))
        user = cur.fetchone()
    if not user and email:
        cur = db.execute("SELECT id, tenant_id, email FROM users WHERE email=?", (email.lower(),))
        user = cur.fetchone()

    if not user:
        return None

    user_id = user["id"] if isinstance(user, dict) else user[0]
    tenant_id = user["tenant_id"] if isinstance(user, dict) else (user[1] if len(user)>1 else "default-tenant")

    if event_type in ("charge.success", "subscription.create", "invoice.success"):
        # Set active
        auth_code = event_data.get("authorization", {}).get("authorization_code", "") if isinstance(event_data.get("authorization"), dict) else event_data.get("authorization_code", "")
        sub_code = event_data.get("subscription_code") or event_data.get("subscription", {}).get("subscription_code", "")
        if not sub_code and "subscription" in event_data and isinstance(event_data["subscription"], dict):
            sub_code = event_data["subscription"].get("subscription_code","")
        # Extract plan
        plan_code = "individual"
        if "plan" in event_data and isinstance(event_data["plan"], dict):
            p_code = event_data["plan"].get("plan_code") or event_data["plan"].get("code","")
            plan_code = plan_key_from_paystack_code(p_code)

        # Upsert subscription like ClearFlag upsertSubscription
        # Update user
        db.execute(
            "UPDATE users SET paystack_customer_code=?, paystack_subscription_code=?, paystack_authorization_code=?, subscription_status='active' WHERE id=?",
            (customer_code or "", sub_code or "", auth_code or "", user_id)
        )
        # Upsert subscriptions table
        details = plan_details(plan_code)
        sub_id = sub_code or f"sub_{user_id}_{plan_code}"
        db.execute(
            "INSERT OR REPLACE INTO subscriptions (id, tenant_id, user_id, paystack_customer_code, plan_code, status, paystack_subscription_code, builds_allowed, builds_used, reference) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sub_id, tenant_id, user_id, customer_code, plan_code, "active", sub_code, details["pages"], 0, event_data.get("reference",""))
        )
        db.commit()
        append_audit_log(tenant_id, user_id, "billing.subscription.active", "subscriptions", sub_id, {"plan_code": plan_code, "event_type": event_type})
        return tenant_id

    elif "deactivated" in event_type or "failed" in event_type or event_type in ("subscription.disable", "invoice.payment_failed"):
        _maybe_send_dunning(event_type, user, tenant_id)
        # Set free + reset usage on renewal failure? ClearFlag resets builds_used on renewal, we set status free on disable
        if "disable" in event_type:
            db.execute("UPDATE users SET subscription_status='free' WHERE id=?", (user_id,))
            # Find subscription
            cur = db.execute("SELECT id FROM subscriptions WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
            row = cur.fetchone()
            if row:
                sub_id = row["id"] if isinstance(row, dict) else row[0]
                db.execute("UPDATE subscriptions SET status='cancelled' WHERE id=?", (sub_id,))
            db.commit()
            append_audit_log(tenant_id, user_id, "billing.subscription.cancelled", "subscriptions", str(user_id), {"event_type": event_type})
        return tenant_id

    return None
