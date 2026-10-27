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

## 2026-10-26-09 Web build JSX escaping -> and {{{{
Symptom: Next.js 15.5.28 build FAILED Error x Unexpected token. Did you mean {'>'} or &gt;? at page.tsx:46 Browser Next.js -> FastAPI contains -> with > inside <pre> JSX parser treats > as tag close, plus settings/page.tsx value={{{{ openai_api_key }}}} quadruple braces invalid Expected '</', got '{'.
Cause: Used -> with > inside JSX text and {{{{ for template display, not escaped.
Fix: Replace -> with → unicode arrow per JSX escaping, {{ with {'{{'}} {{'}}'} escaped, e.g., value={'{{ openai_api_key }}'}. Added public/.gitkeep for Dockerfile COPY. Tests: pnpm build now Compiled successfully in 13.6s Generating static pages (9/9). Commit 03d0279 + ab663a6.
Applies when: Building Next.js with -> arrows or template braces in JSX.

## 2026-10-26-10 Railway deploy uvicorn not found + email-validator missing
Symptom: Railway logs /bin/bash: line 1: uvicorn: command not found then /mise/.../python: No module named uvicorn then ImportError email-validator not installed Pydantic networks.py 1080 EmailStr requires email-validator.
Cause: pip install -e . did not install deps in Nixpacks mise Python 3.13.16, railway.json buildCommand pip install -e . only, needs pip install -r requirements.txt, plus missing email-validator for EmailStr.
Fix: Added requirements.txt with all deps from pyproject.toml, nixpacks.toml phases.install pip install --upgrade pip + pip install -r requirements.txt + pip install -e ., railway.json buildCommand same, Procfile web: python -m uvicorn not uvicorn, pyproject.toml pydantic[email] + email-validator. Now build SUCCESS + Online https://finspy-production.up.railway.app ready true backend pg. Commit 4f65d08 + 5c6b34b + c514e7c + 2228242.
Applies when: Deploying FastAPI on Railway Nixpacks.

## 2026-10-26-11 Railway sleep after inactivity
Symptom: Railway free tier sleeps after ~10m inactivity, shows 502 Application failed to respond while waking, needs startup time 30-60s cold start.
Cause: Free tier sleeps, no uptime ping.
Fix: Added .github/workflows/uptime.yml cron */5 * * * * pinging https://finspy-production.up.railway.app/health/ready every 5 min per user note, plus railway.json healthcheckPath /health/ready restart always, plus docs mention UptimeRobot/Better Stack free tier alternative. Commit 246d942.
Applies when: Hosting on Railway free tier for Paystack live URL proof.

## 2026-10-26-12 Encrypted PDF handling
Symptom: User can upload PDF but what if encrypted/password protected? How to open?
Cause: Initial intake did not handle encrypted PDFs, fitz.open without password fails, no status needs_password.
Fix: API POST /v1/documents now accepts pdf_password Optional Form + X-PDF-Password header + X-PDF-Password-Env env var name per clearmind pattern never log/store password, detection fitz.open is_encrypted needs_pass, try authenticate(password) 0 fail -> needs_password else queued, audit log is_encrypted needs_password encryption_method but not password, extractor extract_text_with_bbox(pdf_path,password) tries authenticate, raises ValueError needs_password if no password, fallback pdfplumber open with password param, tests 6 new test_encrypted_pdf.py detection correct/wrong password, upload without/with correct/wrong password, extraction without/with password, password not logged/stored checks DB and audit_log no supersecret123, total 52 passed. Commit 3f2a8e6.
Applies when: Handling password protected bank statements.

## 2026-10-26-13 Intake classifier + duplicate + tamper detection
Symptom: User asked can intake know when PDF is bank statement? duplicates? exclude other files? original or tampered?
Cause: Initial intake only checked size/type SHA256, no bank statement classifier, no near-duplicate via fingerprints, no exclusion to save AI cost, no tamper detection metadata/incremental updates/hash-chain/visual hidden text.
Fix: Implemented apps/worker/parsers/classifier.py BANK_KEYWORDS FNB Standard Bank etc SA_BANK_PATTERNS Account Number Branch Code Opening Balance, NON_BANK_INDICATORS Invoice Receipt jpg, is_bank_statement() scores mime/extension + bank keywords >=3 +2 >=1 +1 patterns >=2 +2 dates+amounts >=3 +2 opening/closing +1 penalize non-bank, confidence score/max threshold 0.5, is_duplicate_file() SHA256 content-hash vault SELECT id FROM source_documents WHERE sha256=? tenant_id, is_near_duplicate_transactions() fingerprint SHA256(date|amount|desc_norm) overlap >=80% threshold, should_exclude_from_extraction() low confidence <0.3 not bank -> exclude to save AI cost per per_document_token_ceiling 15000, image low conf exclude SAM 3.1 stretch, file <50 chars exclude, classify_file_type() bank_statement csv_statement ofx_statement receipt_image invoice other, plus tamper.py check_pdf_metadata_tampering() producer modDate before creationDate incremental updates /Prev multiple %%EOF font consistency per F-050, check_content_hash_chain() vault content-hash key=SHA256 never overwrite immutable + audit_log hash-chain prev_hash/row_hash + file on disk hash vs claimed, check_visual_tampering_indicators() hidden text outside visible area near-zero font inconsistent number formatting comma vs dot, full_tamper_check() combining returns is_original_likely confidence tamper_chance tamper_indicators reasons, wow factor report chances of tamper and reasons per user question. Tests 8 passed test_intake.py bank detection, duplicate, near-duplicate 80% overlap, exclude other files, classify file type, tamper metadata, hash chain, full tamper check, total 62 passed. Commit 1f99344.
Applies when: Intake verification for forensic evidence.

## 2026-10-26-14 Extraction line-ID grounding v1 + reconciliation gate + review queue
Symptom: Day2 extraction not yet wired, worker main only prints, no text+bbox, no deterministic parser, no reconciliation gate opening+sum=closing running balance monotonic duplicate fingerprints, no review queue API.
Cause: Scaffold only, no implementation of homework Part 5.6 deterministic first LLM fallback second vision last balance-verification gate per-row source coordinates.
Fix: Implemented apps/worker/parsers/fnb.py deterministic FNB parser SA formats R prefix space thousands 1 234,56 comma (450) negative Cr/Dr suffix dates 2026/10/25 25 Oct 25-10-2026 normalize_date, parse_fnb_lines heuristic date pattern + amounts regex description without date amounts direction debit/credit amount_minor Decimal int cents source_quote exact unaccounted header/noise/unreadable reconciliation gate 1 Rand tolerance, apps/worker/parsers/extractor.py orchestrator DB-first extract_text_with_bbox PyMuPDF words bbox line-ID L001 hidden-text detection fallback pdfplumber with password param deterministic_parse tries FNB 10% threshold else None triggers LLM fallback, llm_fallback builds numbered lines Lxxx Page bbox text + prompt prompts/extract_sa_bank_v1.md front-loaded never invent + MetaClient freellmapi muse-spark-1.1 dev + meta_official 1.3 prod mock rows with quote validation page coverage 50% token logging placeholder usage_events, persist_to_db source_spans tenant_id run_id document_id page_no line_id bbox text_hash + transactions fingerprint + transaction_sources, apps/worker/reconcile.py check_opening_closing opening+sum=closing tolerance 100 cents + check_running_balance_monotonic prev balance + signed amount = current diff 100 + check_duplicate_fingerprints, run_reconciliation_gate overall pass/fail, apps/worker/main.py worker_loop polling every 5s source_documents WHERE status=queued ORDER BY uploaded_at_utc ASC LIMIT 5 per-tenant fairness, process_one_document creates extraction_runs pipeline_version git_commit method muse-spark-1.1 status running calls extract_document runs reconciliation gate warnings + breaks + duplicates status proposed if pass else exception persist + update document status + audit_log hash-chain + usage_events 0.04 USD per page + rate limit 60/RPM 100 RPM, handles encrypted needs_password ValueError, apps/api/main.py GET /v1/review-queue returns transactions proposed|exception|needs_password + documents needs_password|exception|queued with tenant isolation 403. Tests test_extraction.py 6 passed SA amount parsing red, normalize_date, fnb deterministic, line-ID grounding quote validation, reconciliation gate, llm fallback mock, test_e2e_day2.py 2 passed e2e intake vault worker reconcile review, bbox line-ID Lxxx, total 54 passed. Commit a513a6c.
Applies when: Day2 extraction per docs/TIMELINE.md.
