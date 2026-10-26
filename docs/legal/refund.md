# Refund Policy - FIN_SPY
Last updated: October 26, 2026

Adapted from clearmind-ai/templates/refund.html but for forensic finance pages metering.

## Free Trial
All new accounts receive 20 free pages (default trial_pages setting, configurable 0-50 like clearmind trial_sessions) before any payment required. This allows you to fully evaluate service before committing. Trial counts source_documents where uploaded_by, not sessions. Remaining pages shown in dashboard per `get_trial_pages_remaining()`. Clearmind had 5 free sessions, FIN_SPY 20 pages.

## Subscription Cancellation
You may cancel subscription anytime from Account page. Upon cancellation:
- Subscription remains active until end of current billing period
- No further charges will be made
- You retain access to all features until period ends
- builds_used reset on renewal per ClearFlag upsert pattern, not immediate reset

## Refunds
Because service is digital and immediately accessible (PDF upload -> hash vault -> extraction), we do not offer refunds for partial billing periods. If you cancel, you continue to have access until end of paid period. Excel workbook live formulas, signed PDF, Evidence Pack ZIP already generated are digital.

## Exceptions
If you experience technical issue that prevents you from using service for more than 48 consecutive hours (e.g., reconciliation gate always failing, vault hash mismatch, extraction 0% accuracy, dashboard drill-to-bbox broken), contact us for pro-rata refund or service credit. Verification via `scripts/verify_pack.py` independent hasher + audit_log hash-chain check per Appendix D.

## Dispute Resolution
If you have billing dispute, email admin at `{{ admin_email }}`. We will respond within 5 business days. Provide tenant_id, subscription_code, reference from Paystack transaction initialize.

## Plans
- Free: 20 pages/mo R0
- Individual: 200 pages/mo R149 (vs clearmind R370)
- SME: 1000 pages/mo R599 2 entities
- Practice: custom
Metering: pages processed + tokens + exports per `usage_events` table, est_cost_usd tracked per homework Part 5.13, per-tenant monthly caps, global daily Meta budget alarm, kill switch to No-AI mode.
