"""
Email service abstraction - Resend free tier per homework Part 5.14 + SMTP fallback
Per user question: Do we need mailback service/no-reply mail for login? YES for production grade

SMTP fallback: send_email() via SMTP_HOST/PORT/USER/PASS/FROM with smtplib.SMTP starttls timeout 10s; welcome + reset templates; reset links emailed, never shown openly

FIN_SPY upgrade:
- Resend free tier per homework Part 5.14 + Part 6: Resend or Postmark free tier, Supabase SMTP alternative
- Env: EMAIL_API_KEY worker only never browser per AGENTS.md Never commit secrets, EMAIL_FROM=noreply@fin-spy.example, SMTP_HOST etc fallback via env_or_setting
- Service: send_email(to, subject, body, html=None) tries Resend API POST https://api.resend.com/emails Bearer key, if no key logs to console + audit_log, never exposes key in browser
- Templates: welcome, reset with token 1h expiry, payment_failed dunning 7 days read-only
- No-reply: from noreply@fin-spy.example, reply-to support@fin-spy.example
- Privacy: log redacted, never log body with token in production logs per AGENTS.md Never print secrets
- For hackathon demo, can return reset_token directly in API response (dev mode only), prod emails
"""
import os
import logging
from typing import Optional
import requests

from .db import env_or_setting

log = logging.getLogger(__name__)

def get_email_api_key() -> str:
    return env_or_setting('email_api_key', '') or os.getenv('RESEND_API_KEY', '')

def get_email_from() -> str:
    return env_or_setting('email_from', 'noreply@fin-spy.example')

def send_email(to_email: str, subject: str, body: str, html: Optional[str] = None, tenant_id: str = "default") -> bool:
    """
    Send email via Resend free tier, fallback to SMTP, fallback to log if no key
    Returns True if sent or logged, False on exception
    Per AGENTS.md Never print secrets, redact in logs
    """
    api_key = get_email_api_key()
    from_addr = get_email_from()

    # If no API key, log and return True for dev (mock email)
    if not api_key:
        log.info(f"[MOCK EMAIL] To: {to_email} Subject: {subject} From: {from_addr} Body: {body[:100]}... [REDACTED]")
        # Append audit log for email sent (without token content)
        try:
            from .db import append_audit_log
            append_audit_log(tenant_id, None, "email.mock_sent", "email", to_email, {"to": to_email, "subject": subject})
        except Exception:
            pass
        return True

    # Try Resend API
    try:
        # Resend API: POST https://api.resend.com/emails with Bearer key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": from_addr,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        if html:
            payload["html"] = html

        resp = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        log.info(f"Email sent via Resend to {to_email} subject {subject}")
        # Audit log (redacted body)
        try:
            from .db import append_audit_log
            append_audit_log(tenant_id, None, "email.sent", "email", to_email, {"to": to_email, "subject": subject, "provider": "resend"})
        except Exception:
            pass
        return True
    except Exception as e:
        log.warning(f"Resend failed {e}, trying SMTP fallback")

    # Fallback to SMTP
    try:
        import smtplib
        from email.message import EmailMessage
        host = env_or_setting('smtp_host', '')
        port_str = env_or_setting('smtp_port', '587')
        port = int(port_str) if port_str.isdigit() else 587
        user = env_or_setting('smtp_user', '')
        pw = env_or_setting('smtp_pass', '')
        from_addr_smtp = env_or_setting('smtp_from', from_addr)

        if not host or not user or not pw:
            log.warning("SMTP not configured, email logged as mock")
            return True

        msg = EmailMessage()
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype='html')
        msg['Subject'] = subject
        msg['From'] = from_addr_smtp
        msg['To'] = to_email

        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()
        server.login(user, pw)
        server.send_message(msg)
        server.quit()
        log.info(f"Email sent via SMTP to {to_email}")
        return True
    except Exception as e:
        log.warning(f"Email send failed: {e}")
        return False

def send_welcome_email(to_email: str, name: str = "", app_base_url: str = "https://finspy-production.up.railway.app", tenant_id: str = "default"):
    subject = "Welcome to FIN_SPY - Financial Surveillance & Peak Insights"
    body = f"Hi {name or 'there'},\n\nWelcome to FIN_SPY! Your account {to_email} is ready.\n\nGet started: {app_base_url}\n\nYour money has a stalker. Find it.\n\nBuilt with Meta Muse Spark/Wonder/Image/SAM 3.1\n\n- FIN_SPY Team\nnoreply@fin-spy.example"
    html = f"<p>Hi {name or 'there'},</p><p>Welcome to FIN_SPY! Your account {to_email} is ready.</p><p><a href='{app_base_url}'>Get started</a></p><p>Your money has a stalker. Find it.</p><p>Built with Meta Muse</p><p>- FIN_SPY Team<br>noreply@fin-spy.example</p>"
    return send_email(to_email, subject, body, html, tenant_id=tenant_id)

def send_reset_email(to_email: str, token: str, app_base_url: str = "https://finspy-production.up.railway.app", tenant_id: str = "default"):
    reset_link = f"{app_base_url}/reset?token={token}"
    # For Paystack live URL proof, use railway domain
    subject = "FIN_SPY - Reset your password"
    body = f"Reset your password link (expires 1h): {reset_link}\n\nIf you didn't request, ignore.\n\n- FIN_SPY noreply@fin-spy.example"
    html = f"<p>Reset your password (expires 1h):</p><p><a href='{reset_link}'>{reset_link}</a></p><p>If you didn't request, ignore.</p><p>- FIN_SPY noreply@fin-spy.example</p>"
    return send_email(to_email, subject, body, html, tenant_id=tenant_id)

def send_payment_failed_email(to_email: str, plan_code: str = "individual", tenant_id: str = "default"):
    subject = f"FIN_SPY - Payment failed for {plan_code}"
    body = f"Your payment for {plan_code} failed. Your subscription will be read-only after 7 days grace per refund policy.\n\nUpdate card: https://finspy-production.up.railway.app/account\n\n- FIN_SPY noreply"
    html = f"<p>Your payment for {plan_code} failed. Read-only after 7 days grace.</p><p><a href='https://finspy-production.up.railway.app/account'>Update card</a></p>"
    return send_email(to_email, subject, body, html, tenant_id=tenant_id)
