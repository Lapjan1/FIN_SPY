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
Fix: Implemented apps/worker/parsers/fnb.py deterministic FNB parser SA formats R prefix space thousands 1 234,56 comma (450) negative Cr/Dr suffix dates 2026/10/25 25 Oct 25-10-2026 normalize_date, parse_fnb_lines heuristic date pattern + amounts regex description without date amounts direction debit/credit amount_minor Decimal int cents source_quote exact unaccounted header/noise/unreadable reconciliation gate 1 Rand tolerance, apps/worker/parsers/extractor.py orchestrator DB-first extract_text_with_bbox PyMuPDF words bbox line-ID L001 hidden-text detection fallback pdfplumber with password param deterministic_parse tries FNB 10% threshold else None triggers LLM fallback, llm_fallback builds numbered lines Lxxx Page bbox text + prompt prompts/extract_sa_bank_v1.md front-loaded never invent + MetaClient freellmapi muse-spark-1.1 dev + meta_official 1.3 prod mock rows with quote validation page coverage 50% token logging placeholder usage_events, persist_to_db source_spans tenant_id run_id document_id page_no line_id bbox text_hash + transactions fingerprint + transaction_sources, apps/worker/reconcile.py check_opening_closing opening+sum=closing tolerance 100 cents + check_running_balance_monotonic prev balance + signed amount = current diff 100 + check_duplicate_fingerprints, run_reconciliation_gate overall pass/fail, apps/worker/main.py worker_loop polling every 5s source_documents WHERE status=queued ORDER BY uploaded_at_utc ASC LIMIT 5 per-tenant fairness, process_one_document creates extraction_runs pipeline_version git_commit method muse-spark-1.1 status running calls extract_document runs reconciliation gate warnings + breaks + duplicates status proposed if pass else exception persist + update document status + audit_log hash-chain + usage_events 0.04 USD per page + rate limit 60/RPM 100 RPM, handles encrypted needs_password ValueError, apps/api/main.py GET /v1/review-queue returns transactions proposed|exception|needs_password + documents.
Applies when: Day2 extraction per docs/TIMELINE.md.

## 2026-10-26-15 Per bank account number ledger - each account number own ledger within same DB per tenant, not own DB
Symptom: Accounts table had no account_number column, source_documents no account_id/account_number, transactions no account_id/account_number, so NOT per account number, only per tenant, potential contamination.
Cause: Initial schema only per tenant with multiple accounts but not per account number database - anti-pattern would be per account DB.
Fix: Added account_number, bank_name, branch_code, is_active to accounts table with UNIQUE(tenant_id,account_number) + UNIQUE INDEX idx_accounts_tenant_account_number WHERE account_number IS NOT NULL + idx_accounts_account_number, added account_id, account_number, bank_name, branch_code to source_documents FK account_id REFERENCES accounts(id), added account_id, account_number to transactions FK account_id + UNIQUE(tenant_id,account_number,fingerprint_sha256) + indexes idx_transactions_account, idx_transactions_account_number, idx_transactions_tenant_account_fingerprint ON transactions(tenant_id,account_number,fingerprint_sha256) per user question each transaction only once ever per bank account number, plus _ensure_schema cols, updated extractor to detect account number from statement via registry config/banks.yaml account_regex Branch Code regex bankcodes 250655 FNB 051001 STDB 632005 ABSA etc, fnb.py now detects account_number via re.search(account_regex, all_text) from get_bank_config(FNB) + branch_code, includes in statement dict, persist_to_db() handles per bank account number ledger: if statement has account_number, check SELECT id FROM accounts WHERE tenant_id=? AND account_number=? else create account id acc-... code account_number[-6:] name Bank - account_number type asset bank_name branch_code, then UPDATE source_documents SET account_id,account_number,bank_name,branch_code, then for each row check SELECT id FROM transactions WHERE tenant_id=? AND account_number=? AND fingerprint_sha256=? if exists skip per each transaction only once ever per bank account number. Commit fe7ddf3 + 2ace643.
Applies when: Effective finance per bank account number, per customer with 20 private 100 business accounts.

## 2026-10-26-16 Account contamination and per customer 20 private 100 business
Symptom: User asked ok but we will not have account contamination then this is sufficient? and this also helps per customer although he has 20 private and 100 business account?
Cause: No test for account contamination, no test for per customer many accounts.
Fix: Created tests/test_account_isolation.py 3 tests: no contamination private 123456 FNB + business 456789 STDB 1 row each correct account_number no private in business, per customer 20 private + 100 business = 120 accounts per tenant customer 120 transactions private 20 business 100 each account exactly 1 transaction with matching account_number per isolation, unique constraint prevents duplicate account_number per tenant different tenant same account_number succeeds no cross-tenant contamination, total 80 passed (77 previous +3 new). Single DB per tenant with 120 accounts sufficient and helps per customer via accounts table type personal/business. Commit 2ace643.
Applies when: Multi-account per customer, per bank account ledger.

## 2026-10-26-17 Totals +/- == balance from top to bottom and bottom to top
Symptom: User Ok so our totals =/- == balance from top to bottom and from bottom to top? + Ok so the extraction test should be opening balance +/- amount == running balance/total from top to bottom and from bottom to top.
Cause: Previous reconcile.py only checked top->bottom opening+sum=closing and running prev+signed=current, not bottom->top.
Fix: Added check_opening_closing_reverse() closing - sum = opening computed_opening = closing; for r in reversed(rows): computed_opening -= signed, check_running_balance_reverse() current = next - signed_next expected_curr = next.balance_after - signed_next, run_reconciliation_gate() now returns opening_closing_top_bottom + opening_closing_bottom_top + running_balance_top_bottom + running_balance_bottom_top + duplicates + overall_pass = all four balance checks + duplicates + totals_check dict top_to_bottom bottom_to_top explanation Totals +/- == balance from top to bottom and from bottom to top per user question, example opening 10000 rows -1000 9000 -2000 7000 +500 7500 closing top 10000-1000-2000+500=7500 pass bottom 7500+1000+2000-500=10000 pass. Tests 3 new test_reconcile_both.py totals_plus_minus_equals_balance_both_directions pass both, totals_fail_both_directions wrong closing 8000 fails both, running_balance_break_both_directions, plus updated test_extraction.py test_reconciliation_gate to check both directions and new test_reconciliation_both_directions_extraction explicit, total 66 passed. Commit d4c4aa8 + c84a49b + 4b42ad7.
Applies when: Bank statement reconciliation forensic evidence.

## 2026-10-26-18 Email service no-reply mail for login
Symptom: User asked do we need mailback service/no reply mail for login if yes just add note to relevant planning day.
Cause: Initial auth had no email service, just returned reset_token directly in API response like clearmind forgot_password.html:10 shows link openly (security leak).
Fix: Created docs/TIMELINE.md 10-day plan with Day2 auth + Day7 billing note, created apps/api/email.py Resend free tier per homework Part 5.14 + clearmind SMTP pattern worker only never browser EMAIL_API_KEY env EMAIL_FROM noreply@fin-spy.example service send_email(to,subject,body,html) tries Resend API POST https://api.resend.com/emails Bearer key else SMTP smtplib.SMTP starttls timeout 10s else log mock + audit_log, templates welcome reset payment_failed no-reply from noreply reply-to support, privacy log redacted never token, .env.example EMAIL_API_KEY etc, docs/PLAN.md Constraints + Done Means Email Resend free tier + clearmind SMTP pattern, STATE.md Next 3 steps email service Resend. Tests 15 still pass. Commit 66445dd.
Applies when: Auth with welcome + reset + billing notifications, production grade Startup track.

## 2026-10-26-19 PowerBI pack + DB useful for Excel/PowerBI per conventions
Symptom: User asked OK so we have a descent database? is our database useful in terms of data storage and extraction/representation for excell powerbi etc according to database conventions?
Cause: No indexes for 1000 tx <5s, no dim_date, no star-schema views fact_transactions fact_journal dim_account dim_category dim_entity dim_document, no journal balance constraint trigger, no PowerBI export endpoint.
Fix: Added indexes CREATE INDEX IF NOT EXISTS idx_transactions_tenant_date etc 15 indexes for performance per homework Done Means 1000 tx analyze <5s, removed dim_date table creation to avoid conflict table+view same name, kept view dim_date SELECT DISTINCT txn_date as date year month day quarter month_name day_of_week is_weekend FROM transactions UNION entry_date FROM journal_entries for PowerBI calendar, star-schema views fact_transactions SELECT t.id tenant_id entity_id document_id run_id txn_date as date description_raw amount_minor etc LEFT JOIN classifications, fact_journal SELECT entry_id tenant_id entity_id entry_date date memo transaction_id classification_id line_id account_id debit_minor credit_minor account_code name type FROM journal_entries JOIN journal_lines LEFT JOIN accounts, dim_account id tenant_id entity_id code name type FROM accounts, dim_category DISTINCT category_id + 6000 Marketing etc, dim_entity tenants UNION distinct entity_id, dim_document id tenant_id sha256 original_filename, plus trigger trg_journal_balance_check_insert AFTER INSERT ON journal_lines FOR EACH ROW SELECT CASE WHEN SUM(debit)!=SUM(credit) AND COUNT>=2 THEN RAISE(ABORT) per AGENTS.md ledger-core double-entry, plus _ensure_indexes and _ensure_schema for existing DBs, created apps/api/reports.py generate_powerbi_pack() queries fact/dim views XlsxWriter sheets Cover fact_transactions fact_journal dim_account dim_category dim_entity dim_document dim_date Method_Notes + CSVs fact_transactions.csv etc in csv_dir, generate_excel_workbook() per Appendix G Cover Summary Transactions Table Journal Trial_Balance live SUMIFS Private_vs_Business Flags Source_Register Method_Notes Dictionary, endpoints GET /v1/reports/powerbi and GET /v1/reports/excel and POST /v1/reports?kind=powerbi immediate per homework Part 5.10, tests 6 new test_db_powerbi.py indexes exist star-schema views exist dim_date view year 2026 month 10 fact_transactions view category_id 6100 journal balance constraint trigger powerbi pack generation file exists total 72 passed (62 previous +6 powerbi +... actually 72 total now). Commit ab3836a.
Applies when: Making DB useful for Excel/PowerBI per conventions.

## 2026-10-26-20 Side-by-side viewer + pnpm approve-builds
Symptom: User Can I see the statement and the extraction side by side? + pnpm --dir apps/web dev --port 3000 failed [ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: canvas@3.2.3, unrs-resolver@1.12.2 Run pnpm approve-builds.
Cause: Next.js had JSX escaping -> with > inside <pre> + {{{{ openai_api_key }}}}, plus pnpm-workspace.yaml placeholder allowBuilds: canvas: set this to true or false, plus Dockerfile public/.gitkeep missing + COPY apps/web/package.json context.
Fix: Created scripts/show_side_by_side.py generates synthetic FNB bank statement PDF with opening R12 340.55 5 transactions closing R20 790.55 via PyMuPDF A4, extracts via extract_text_with_bbox() words bbox line-ID L001, deterministic_parse() FNB parser + llm_fallback mock, run_reconciliation_gate() both directions, classifier is_bank_statement() True 100%, generates HTML data/samples/side_by_side.html two columns left original statement Lxxx bbox right extraction transactions + reconciliation both directions + fingerprint SHA256(date|amount|desc_norm), sample PDF copied to data/samples/synthetic_statement.pdf, fixed pnpm-workspace.yaml allowBuilds: canvas: true unrs-resolver: true, fixed Dockerfile COPY apps/web/package.json ./ + COPY apps/web/ ./ supports repo root context, public/.gitkeep, JSX escaping -> to → unicode arrow and {{{{ to {'{{'}} for Next.js 15.5.28 webpack Unexpected token, now Compiled successfully in 13.6s Generating static pages (9/9) Route / 2.08kB /privacy 2.72kB etc, live domain https://finspy-production.up.railway.app ACTIVE ID 082e4fd8-5340-4fa3-be81-2eb81f8084a5 + web Online fad6eda9 SUCCESS after fixes, uptime ping Cron .github/workflows/uptime.yml every 5 min per user note sleep after given time. Commit e723d17 + 03d0279 + ab663a6 + 8e5ad69.
Applies when: Showing statement and extraction side by side for forensic verification + fixing web build for Paystack live webpage proof.
