# Terms of Service - FIN_SPY
Last updated: October 26, 2026

Adapted from clearmind-ai/templates/terms.html but for forensic finance.

## 1. Service Description
FIN_SPY provides forensic financial tools: SA bank PDF upload, every number traced to exact bbox SHA256 vault + hash-chain audit, dynamic double-entry books, leak/subscription/duplicate spy, KPIs (runway,burn,savings_rate,debt-to-income), debt snowball/avalanche, signed PAdES PDF + Evidence Pack ZIP + PowerBI-ready pack. Service offered on subscription basis per `docs/PLAN.md`.

## 2. Account Registration
You must register an account to use service. You are responsible for maintaining confidentiality of login credentials (bcrypt $2b$ stored, not SHA256) and all activity under your account. Tenant isolation via `tenant_id + user_id` - no cross-account access tested via `test_user_isolation`.

## 3. Subscription & Billing
After free trial (20 pages default, trial_pages setting vs clearmind 5 sessions), continued use requires paid subscription: Free 20 pages R0, Individual 200 pages R149/mo, SME 1000 pages R599/mo, Practice custom per `docs/decisions/0001`. Payments processed securely via Paystack timing-safe HMAC SHA512 raw body `hmac.compare_digest` per ClearFlag, not plain ==, idempotent webhook_events. Subscriptions auto-renew monthly. You may cancel anytime - access continues until end of billing period, builds_used reset on renewal per ClearFlag upsertSubscription pattern.

## 4. Acceptable Use
You agree to:
- Use service only for lawful financial record-keeping, own data or authorized
- Maintain confidentiality of financial data per POPIA
- Not use service to generate harmful or fraudulent books
- Not attempt to reverse-engineer or abuse AI systems, not inject hidden text white/0pt to steer model
- Not upload malicious PDFs (JS, incremental updates, zip bombs) - sanitization checks size/type 50MB limit, page-count limit, worker timeouts per AGENTS.md security

## 5. AI-Generated Content & Court-Ready Disclaimer
AI extraction fallback uses Meta Muse Spark 1.3 structured output with line-ID grounding, classification suggestions AI second opinion. All AI outputs labelled source=ai confidence rationale. AI never finalizes - human decides. AI-generated classifications, KPIs, debt strategies are tools to assist your bookkeeping judgement. They do not replace professional accountant assessment. You remain solely responsible for reviewing and approving all books before use. Private/business split needs professional review. Debt strategies calculation aid not financial advice (SARS deductibility need practitioner). Reports must state flags are indicators for inquiry, not findings of fault. "Court-ready" in marketing means built to support admissibility and expert testimony per ECTA s15, NOT guaranteed admissible - admissibility decided by court, needs witness who can explain method per `docs/METHOD_STATEMENT.md`. AI disclosure in every report.

## 6. Limitation of Liability
FIN_SPY provided as is without warranty. Not liable for damages arising from use of AI-generated content, books, service interruptions, data loss, reconciliation failures. Total liability limited to amount paid in preceding 12 months. Excel workbook live SUMIFS not tamper-proof - integrity anchor is signed PDF + manifest SHA256 printed in PDF footer + QR verification page.

## 7. Termination
We may suspend or terminate accounts violating terms (malicious PDFs, prompt injection, IDOR attempts, forged webhooks, brute-force). You may delete account anytime. Upon termination, data permanently deleted within 30 days per privacy, audit non-personal skeleton may remain, deletion certificate hash list, legal_hold flag blocks deletion.

## 8. Changes to Terms
We may update terms. Continued use after changes constitutes acceptance. Material changes notified via email.

## 9. Governing Law
Terms governed by laws of South Africa. POPIA compliance, ECTA s15 data messages admissibility.

## 10. Contact
For questions, email admin at `{{ admin_email }}`.
