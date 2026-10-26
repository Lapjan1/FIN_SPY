# LEARNINGS.md - Append-only mistakes log

## 2026-10-26-01 PyMuPDF AGPL licensing trap
Symptom: Chose PyMuPDF for bbox extraction, later realized SaaS distribution needs commercial license check.
Cause: Did not verify license before picking library (AGPL vs commercial).
Fix: Keep PyMuPDF for hackathon MVP, document fallback to pdfplumber/pypdfium2 for prod SaaS path with abstraction layer in apps/worker/parsers/.
Applies when: Picking PDF libraries for commercial product.

## 2026-10-26-02 Old hardcoded single-company COA
Symptom: Previous FINSPIB had one set books hardcoded, feeding any other company still spit same COA.
Cause: Built SaaS around one tenant's books, not dynamic multi-tenant COA seeding.
Fix: This repo builds dynamic COA per tenant - seed generic SA COA, learn from transactions, merchant memory per tenant, never hardcode one company.
Applies when: Designing ledger, tenant isolation tests mandatory.

## 2026-10-26-03 DB-first vs direct report generation
Symptom: Initially extracted and produced Excel directly, losing traceability and ability to re-run.
Cause: No intermediate DB, every report required re-extraction.
Fix: Extract -> persist to SQLite/Postgres with line IDs and bbox spans -> ALL products (dashboard, Excel, PDF, KPIs, debt strategies) read from DB. Verification script re-hashes DB-stored files.
Applies when: Any extraction pipeline, ETL.

## 2026-10-26-04 Meta contributor tier data leak
Symptom: Tempted to use muse-spark-1.3-contributor for cheap cost.
Cause: Did not read data-use warning: "Meta may train on prompts/completions".
Fix: Use standard tier only for customer docs. Contributor only allowed for synthetic test data. Document in AGENTS.md.
Applies when: Choosing Meta model IDs.

## 2026-10-26-05 Clearmind weak SHA256 password hashing
Symptom: clearmind-ai/database.py:308 uses hashlib.sha256(password.encode()).hexdigest() no salt, easily cracked.
Cause: Copied clearmind pattern directly without security upgrade.
Fix: FIN_SPY apps/api/auth.py uses bcrypt $2b$ 60 chars with gensalt, verify with bcrypt.checkpw, legacy SHA256 fallback for migration but new hashes bcrypt. Added BCRYPT_AVAILABLE flag and test_bcrypt_not_sha256 asserts $2b$ not 64 hex. Document in ADR 0002.
Applies when: Implementing auth from reference project.

## 2026-10-26-06 Paystack webhook timing attack
Symptom: clearmind-ai paystack webhook checks signature with plain ==, vulnerable to timing attack, no idempotency, no raw body HMAC SHA512 of raw bytes.
Cause: Did not use constant time compare.
Fix: FIN_SPY apps/api/paystack.py verify_paystack_signature uses hmac.compare_digest HMAC SHA512 raw body like ClearFlag/routes/paystack.js, webhook stores webhook_events idempotency key event_id, raw body bytes not JSON parsed. Test test_paystack_timing_safe.
Applies when: Payment webhook implementation.

## 2026-10-26-07 Session secret random persisted bug
Symptom: clearmind-ai app.py:10 generates FLASK_SECRET random and persists to settings table if missing, if DB leaked sessions forgeable.
Cause: Fail-open design.
Fix: FIN_SPY check_session_secret() fail-closed REQUIRED in production per ClearFlag server.js env-check.js, random only for dev with warning, never persisted. Document in docs/AUTH_PAYSTACK.md.
Applies when: Session secret handling.

## 2026-10-26-08 Trial metering pages vs sessions
Symptom: clearmind trial 5 sessions counted via sessions table, FIN_SPY needs pages not sessions.
Cause: Direct copy would meter wrong resource.
Fix: get_trial_pages_remaining() counts source_documents where uploaded_by, max_trial 20 from settings trial_pages default 20, not trial_sessions 5. Plans free 20 individual 200 sme 1000 pages vs clearmind 5 sessions R370. Test test_trial_pages 20->15->None unlimited when active.
Applies when: Adapting trial logic to different product.
