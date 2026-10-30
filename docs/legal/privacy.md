# Privacy Policy - FIN_SPY
Last updated: October 26, 2026

This policy explains how FIN_SPY collects, uses, stores, and protects your information under the Protection of Personal Information Act (POPIA).

## 1. Information We Collect
We collect information you provide when you register, upload bank statements (PDF/CSV/OFX), create entities (personal/business), and use AI features. Invoice/receipt photo uploads are planned but not accepted yet (the API returns a clear 422 until OCR ships). This includes:
- Account: name, email, password_hash bcrypt
- Financial: bank statement transactions (date, description_raw, amount_minor Decimal, balance_after, fingerprint SHA256(date|amount|desc_norm)), document SHA256, storage_key content-hash, page bbox, line_id, source_spans
- Classification: private/business/mixed %, category, rationale, decided_by
- Usage: uploads processed, tokens, exports, audit_log actions
- Technical: upload IP, user_agent, tenant_id

We do NOT store your raw PDFs as searchable text beyond the extracted word spans. Originals are preserved byte-for-byte in an immutable, content-addressed vault (keyed by SHA256 hash) and are never overwritten.

One login holds one subscriber's finances: bank accounts, credit cards, garage cards, and family card numbers each keep their own books under their own account number, and every download (Excel, PowerBI, auditor CSV, evidence pack, signed PDF, POPIA export) can be scoped to a single account so a business pack never contains your other accounts. Whole-tenant exports exist for your own subject access and carry a multi-account warning in the manifest; do not share them with anyone else.

## 2. How We Use Your Information
Your data is used solely to provide FIN_SPY service: forensic extraction with line-ID grounding, reconciliation gate, double-entry books, leak/subscription/duplicate spy, KPI peek (runway,burn,savings_rate), debt snowball/avalanche, signed PAdES PDF + Evidence Pack ZIP. We do not sell, rent, or share your data with third parties.

## 3. Data Storage & Security
All data is stored securely on Railway and Supabase infrastructure. Each tenant's data is isolated by tenant and user ID, so no account can access another account's data (verified by automated isolation tests, with row-level security in production). Every action is recorded in an append-only audit log where each entry is hash-chained to the previous one, so tampering is detectable.

We use:
- Encryption in transit (HTTPS) and at rest (disk encryption); error tracking with redacted personal data
- Immutable content-hash vault; derived files stored separately with a link back to the source; RFC3161 trusted timestamps and PAdES digital signatures on reports
- Passwords bcrypt $2b$ 60 chars with gensalt, not unsalted SHA256 hex; legacy SHA256 fallback for migration
- Session secret fail-closed REQUIRED in production
- Paystack secret key timing-safe `hmac.compare_digest` HMAC SHA512 raw body, idempotent webhook_events

## 4. AI Processing
Bank transaction descriptions, amounts, and dates are sent to Meta Muse Spark 1.3 standard edition (NOT the contributor edition):
- Model capabilities: 1M-token context window, image support, parallel tool use, adjustable reasoning effort
- Local-first routing: a local model is tried first, and a hosted model is only called after you approve the exact text to be sent
- Privacy gate: you always see and approve the exact text before any hosted call
- The Meta standard tier does NOT train on your prompts. The contributor tier does train on prompts, so it is NEVER used for real bank documents - only for synthetic test data
- No OpenAI models are used. The only fallback is a local model running on our own infrastructure, so your data never leaves the service without your approval
- Anti-hallucination layer: the model works from numbered source lines with page coordinates and must cite the exact lines and quote for every figure; all figures pass a reconciliation check

## 5. Data Retention & Legal Hold
You retain ownership of your data. You may delete documents, transactions, or your entire account at any time; deletion removes your content but keeps a non-personal audit skeleton as required by law, with a deletion certificate listing the hashes. Retention periods depend on record type: commonly 5 years for tax and 7 years for company records in South Africa (confirm the periods that apply to you with your accountant or attorney). A legal hold on your account blocks deletion. POPIA requires retention to be justified, with deletion or de-identification once data is no longer needed, subject to legal-hold exceptions. Data is permanently removed within 30 days of account deletion, though the non-personal audit skeleton may remain.

## 6. Your Rights (POPIA)
As a South African service, we comply with the Protection of Personal Information Act (POPIA). You may request a copy of your data, or its correction or deletion, by emailing `admin@fin-spy.example` or via your account page. You may request an export of all your data as an Evidence Pack ZIP (manifest, hashes, timestamp tokens, and verification instructions). Your data is isolated per tenant.

## 7. Cross-Border Transfers
Our infrastructure providers (Railway, Supabase) and AI provider (Meta) may process your data outside South Africa. Transfers comply with POPIA section 72, and we maintain operator agreements with each sub-processor. Hosting data in South Africa (AWS Cape Town region) is on our roadmap.

## 8. Contact
For privacy inquiries, email `admin@fin-spy.example`. Our method statement and AI disclosure describe in detail what we guarantee and what we do not.
