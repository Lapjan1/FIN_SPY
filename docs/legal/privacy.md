# Privacy Policy - FIN_SPY
Last updated: October 26, 2026

Adapted from clearmind-ai/templates/privacy.html POPIA template, but for forensic financial data.

## 1. Information We Collect
We collect information you provide when you register, upload bank statements (PDF/CSV/OFX), invoices/receipts (images), create entities (personal/business), and use AI features. This includes:
- Account: name, email, password_hash bcrypt
- Financial: bank statement transactions (date, description_raw, amount_minor Decimal, balance_after, fingerprint SHA256(date|amount|desc_norm)), document SHA256, storage_key content-hash, page bbox, line_id, source_spans
- Classification: private/business/mixed %, category, rationale, decided_by
- Usage: pages processed, tokens, exports, audit_log actions
- Technical: upload IP, user_agent, tenant_id

We do NOT store raw PDFs as searchable text beyond bbox spans - originals preserved byte-for-byte SHA256 vault immutable `data/vault/` (MVP) or Supabase Storage (prod) content-addressed key = SHA256, never overwritten.

## 2. How We Use Your Information
Your data is used solely to provide FIN_SPY service: forensic extraction with line-ID grounding, reconciliation gate, double-entry books, leak/subscription/duplicate spy, KPI peek (runway,burn,savings_rate), debt snowball/avalanche, signed PAdES PDF + Evidence Pack ZIP. We do not sell, rent, or share your data with third parties.

## 3. Data Storage & Security
All data stored securely on Railway/Supabase infrastructure per `config/models.yaml`. Each tenant's data isolated by `tenant_id + user_id` - no cross-account access, tested via `test_user_isolation` asserts tenant-a can't see doc-b, RLS path Supabase prod. Append-only audit_log hash-chained `row_hash = SHA256(prev_hash||canonical_json)` per AGENTS.md, prev_hash/row_hash verification.

We use:
- Encryption in transit HTTPS, disk encryption BitLocker, Sentry free tier error tracking (redacted)
- Content-hash vault immutable, derivatives separate with derived_from link, TSA RFC3161 timestamp tokens FreeTSA/DigiCert free no SLA, pyHanko PAdES signature
- Passwords bcrypt $2b$ 60 chars with gensalt, not SHA256 hex (clearmind weak pattern fixed), legacy SHA256 fallback for migration
- Session secret fail-closed REQUIRED in production per ClearFlag pattern, not random persisted like clearmind bug
- Paystack secret key timing-safe `hmac.compare_digest` HMAC SHA512 raw body per ClearFlag, idempotent webhook_events

## 4. AI Processing
Bank transaction description, amount, date sent to Meta Muse Spark 1.3 standard (NOT contributor) via `apps/worker/llm/client.py` adapter:
- `config/models.yaml` capabilities: max_context 1M, supports_images, parallel tools, effort low/medium/high/xhigh
- Routing local-first per docs/FLOWS.md Flowchart #2: local ollama `llama3.2` first, hosted only after user approval gate showing exact text to be sent, `show_exact_text_before_hosted=true`
- Privacy gate: show exact text before hosted call, user must approve
- Meta standard tier does NOT train on prompts - per Meta docs. Contributor tier `muse-spark-1.3-contributor` trains on prompts - NEVER for real bank docs, only synthetic test data per AGENTS.md Known pitfalls, test data `data/samples/` synthetic FNB/STDB/ABSA
- OpenAI API policy no training: if using fallback OpenAI, same, but primary is Meta
- Forensic layer: line-ID grounding anti-hallucination - model gets Lxxx numbered lines + bbox, must return line_ids + source_quote exact match, quote validation + reconciliation gate

## 5. Data Retention & Legal Hold
You retain ownership. You may delete documents, transactions, or entire tenant at any time - deletes content but leaves non-personal audit skeleton per law, deletion certificate hash list. Retention per record type is legal decision: commonly 5 years tax, 7 years company per SA anchors [VERIFY with accountant/attorney] per docs/METHOD_STATEMENT.md. Tenant-level legal_hold flag blocks deletion. POPIA expects justified retention + deletion/de-identification when no longer needed, with legal-hold exceptions. Data permanently removed within 30 days of account deletion, audit non-personal skeleton may remain.

## 6. Your Rights (POPIA)
As South African service, we comply with POPIA Protection of Personal Information Act. You may request copy, correct, delete by contacting admin at `{{ admin_email }}` or via `/v1/auth/me`. You may request export of all data as Evidence Pack ZIP manifest.json + manifest.sha256 + .tsr tokens + verification instructions per Appendix D. Data on Railway isolated by tenant_id.

## 7. Cross-Border Transfers
Dev Railway EU approx, Supabase free region may not be SA [VERIFY]. POPIA s72 disclosure applies, operator agreements with sub-processors (Railway, Supabase, Meta), roadmap AWS af-south-1 Cape Town per docs/PLAN.md. Disclose in this notice.

## 8. Contact
For privacy inquiries, email admin at `{{ admin_email }}` or check `docs/METHOD_STATEMENT.md` court wording what we guarantee vs not, AI disclosure.
