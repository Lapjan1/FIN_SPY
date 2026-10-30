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

## 2026-10-27-21 FK cleanup must delete children first (invalid parameters bug)
Symptom: test_vendor_export_and_rule_per_merchant_per_account failed sqlite3.IntegrityError: FOREIGN KEY constraint failed on DELETE FROM accounts WHERE tenant_id=? after auto_book created journal_entries/lines referencing accounts.
Cause: Cleanup deleted accounts before journal_lines/journal_entries/merchant_memory/vendor_rules/transactions. Also seed tests double-called cur.fetchone() losing row.
Fix: Added db.cleanup_tenant(tenant_id) deleting in FK-safe order (transaction_sources, classifications, flags, journal_lines, journal_entries, transactions, merchant_memory, vendor_rules, spans, runs, pages, documents, accounts, audit/usage/subs, users/reset_tokens, tenants). Tests use cleanup_tenant. Found by running pytest -q (bug report: request contains invalid parameters / FK failed). Applies when: any test or endpoint deleting tenant data with FKs on.

## 2026-10-27-22 Invalid parameters must say so with 422
Symptom: Vendor rule creation with empty merchant, bad nature, or non-existing target_account_id crashed or silently passed; dashboard with bad from_date accepted.
Cause: No validation that we never work on non-existing accounts; Pydantic only checks types, not existence.
Fix: Manual checks in POST /v1/vendors/rules + vendor.create_vendor_rule raising ValueError("Invalid parameters: ...") mapped to HTTPException 422. Dashboard _validate_period regex YYYY-MM-DD + from<=to else 422, plus account_number existence check else 422. Books select validates template in VALID_TEMPLATES else 422. Tests test_vendor_rule_invalid_parameters assert 422 + "Invalid parameters" in text. Applies when: any endpoint taking merchant/account/template/period params.

## 2026-10-27-23 Three books one at a time + totals before percentages + explicit inflow/outflow
Symptom: Single generic COA seed could not represent personal vs SME/CC vs mixed sole prop; dashboard returned mock leak 18700/runway 4.5 unrelated to direction; percentages computed before totals.
Cause: No active_template choice; seed_coa id acc-{tenant}-{code} collided across templates; KPI summed without period filter or explicit flags.
Fix: tenants.active_template + accounts.template, seed_coa id acc-{tenant}-{template}-{code} + WHERE code+template, set_active_template validates + seeds + sets active, endpoints GET /v1/books/templates|active + POST /v1/books/select (422 on bad template). kpi.direction_flags + compute_period_totals(from_date,to_date,account_number) first, compute_kpis derives percentages from totals, dashboard accepts period params with validation and returns totals + inflow/outflow + flags. fact_transactions view rebuilt with account_id,account_number. Applies when: 3 sets of books choice + period inspection KPIs.

## 2026-10-26-20 Side-by-side viewer + pnpm approve-builds
Symptom: User Can I see the statement and the extraction side by side? + pnpm --dir apps/web dev --port 3000 failed [ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: canvas@3.2.3, unrs-resolver@1.12.2 Run pnpm approve-builds.
Cause: Next.js had JSX escaping -> with > inside <pre> + {{{{ openai_api_key }}}}, plus pnpm-workspace.yaml placeholder allowBuilds: canvas: set this to true or false, plus Dockerfile public/.gitkeep missing + COPY apps/web/package.json context.
Fix: Created scripts/show_side_by_side.py generates synthetic FNB bank statement PDF with opening R12 340.55 5 transactions closing R20 790.55 via PyMuPDF A4, extracts via extract_text_with_bbox() words bbox line-ID L001, deterministic_parse() FNB parser + llm_fallback mock, run_reconciliation_gate() both directions, classifier is_bank_statement() True 100%, generates HTML data/samples/side_by_side.html two columns left original statement Lxxx bbox right extraction transactions + reconciliation both directions + fingerprint SHA256(date|amount|desc_norm), sample PDF copied to data/samples/synthetic_statement.pdf, fixed pnpm-workspace.yaml allowBuilds: canvas: true unrs-resolver: true, fixed Dockerfile COPY apps/web/package.json ./ + COPY apps/web/ ./ supports repo root context, public/.gitkeep, JSX escaping -> to → unicode arrow and {{{{ to {'{{'}} for Next.js 15.5.28 webpack Unexpected token, now Compiled successfully in 13.6s Generating static pages (9/9) Route / 2.08kB /privacy 2.72kB etc, live domain https://finspy-production.up.railway.app ACTIVE ID 082e4fd8-5340-4fa3-be81-2eb81f8084a5 + web Online fad6eda9 SUCCESS after fixes, uptime ping Cron .github/workflows/uptime.yml every 5 min per user note sleep after given time. Commit e723d17 + 03d0279 + ab663a6 + 8e5ad69.
Applies when: Showing statement and extraction side by side for forensic verification + fixing web build for Paystack live webpage proof.

## 2026-10-28-24 Journal balance trigger must enforce at post, not per line-prefix
Symptom: Legal 3-line mixed split (Dr expense 6000 + Dr suspense 4000 / Cr bank 10000) aborted with sqlite3.IntegrityError: Journal entry not balanced on the 2nd line insert.
Cause: Trigger checked SUM(debits)!=SUM(credits) whenever a 2+ line prefix existed. Any 2-line prefix of a 3-line split is unbalanced, so multi-line entries were impossible. Same bug silently broke vendor auto-book mixed path.
Fix: journal_entries.posted INTEGER DEFAULT 0 + migration in _ensure_schema + DROP old triggers in init_db. New triggers: trg_journal_lines_guard_insert/update/delete enforce balance only WHEN parent posted=1, delete guard blocks removing lines from posted entries (unpost first), trg_journal_entry_post AFTER UPDATE OF posted WHEN NEW.posted=1 aborts unless >=2 lines and debits=credits. ledger.post_transaction + vendor._post_entry draft lines then UPDATE posted=1 with rollback + UnbalancedEntry/False on abort. cleanup_tenant unposts via _cleanup_journals first. tests/test_ledger_day4.py trigger test covers draft-allowed/post-blocked/posted-guarded; tests/test_db_powerbi.py updated to post before 3rd-line attempt. Files apps/api/db.py:322,568-620,746-795,799-815,842,910 apps/api/ledger.py:227-237 apps/api/vendor.py:171-183,239-242.
Applies when: Any DB-level invariant over a multi-row group - enforce at completion event, never on intermediate prefixes.

## 2026-10-28-25 Formatter hunks merge across your boundary - verify removed-lines hash
Symptom: Region-formatting only added lines still reflowed ~20 original lines (vendor auto-book body, powerbi setup INSERTs, main.py return) because ruff merges nearby changes into single hunks; applying a hunk that merely intersects your range rewrites adjacent original lines.
Cause: Hunk-level granularity is coarser than line-level intent; intersection test applied whole hunks.
Fix: Snapshot oracle first: sorted removed-lines SHA256 of git diff before formatting (was f5059256...). After formatting, hash changed -> inspected every minus-line, restored churn via git checkout + redo of logical edits in original style, re-verified hash equality f50592563f8c786a31ee54401f05f21850b05a833d0ea01495b8f57b96acf18f. Rule: new files must be ruff-format clean; edited files keep surrounding style unless the whole file is already clean.
Applies when: Formatting files that fail ruff format --check at HEAD - never whole-file format in a feature PR.

## 2026-10-28-26 9999 suspense keeps statements complete while classification catches up
Symptom: Unknown transactions could not post (accept rejected unknown), so income/expense statements were incomplete; fallback categories 6000/4000 would have mis-posted them as groceries/sales.
Cause: No suspense bucket; unknown had nowhere balanced to go.
Fix: 9999 Suspense - Unclassified Pending Review type expense in all templates (QuickBooks Ask-Accountant pattern: P&L-complete parking, trial always balances, net profit correct; unknown inflows land as contra-expense). Unknown suggests/routes to 9999; decide() auto-transfers the posted leg on category change so 9999 nets to zero with gross legs auditable; failures record transfer_error visibly, never block. suspense_status counts only stuck money (per-txn 9999 net != 0 HAVING form, portable sqlite+pg) + completeness (confirmed-without-journal must be 0) + 5%/30d thresholds via GET /v1/journal/suspense. Existing tenants gain 9999 on next seed (only-missing insert). Files config/banks.yaml apps/api/ledger.py:transfer_posting,suspense_status apps/api/classify.py:decide apps/api/main.py:/v1/journal/suspense tests/test_suspense_9999.py 9 passed.
Applies when: Any unclassified-but-confirmed item must hit the statements - park in suspense with correct debit/credit, re-decode via transfer, watchdog that it stays small.

## 2026-10-28-27 Posted edits must reverse + repost; source balances stay frozen
Symptom: Editing amount/date on a posted txn updated the row but left journals stale, so trial/KPI/reports disagreed with the corrected data; naive "apply forward" would have rewritten bank-printed balances.
Cause: No repost path; and stored balance_after are extracted source facts (parsers persist abs() printed values per fnb.py:172, nothing recomputes them), so cascading deltas into them would falsify evidence.
Fix: ledger.repost_transaction reverses EVERY posted entry (mirror lines append-only) + one fresh post at current values with latest classification (else inferred original target, else 9999); atomic with row update + revisions (rollback on collision/repost failure); description-only and unposted edits post nothing. Forward effects: reverify_chain re-runs opening/closing + running both directions (reused reconcile fns, abs-normalized for signed/unsigned rows) over the affected chain, outcome in response + review.reverify audit; derived statements read live so they follow automatically. New apps/api/audit.py: human_changes legal report (revisions old/new/reason/actor + journal actions, all bound params) + verify_integrity (chain recompute + vault rehash); endpoints GET /v1/audit/human-changes + /v1/audit/verify. Test proves source rows byte-identical after edit + forged audit row detected. Files apps/api/ledger.py:repost_transaction,reverify_chain apps/api/main.py:_apply_txn_updates,review_edit apps/api/audit.py tests/test_edit_repost_legal.py 12 passed.
Applies when: Any human correction to posted data - reverse/append, never update/delete; re-verify forward; report everything; prove hashes.

## 2026-10-28-28 Dedup index was plain, not unique - old files never enforced it
Symptom: Fingerprint-collision rollback test got 200 instead of 422 - duplicate (tenant, account, fingerprint) rows insertable despite UNIQUE in CREATE TABLE.
Cause: Live file predates the inline constraint (CREATE TABLE IF NOT EXISTS never upgrades); the compensating index idx_transactions_tenant_account_fingerprint was created as plain CREATE INDEX, not UNIQUE. Accounts had a real UNIQUE index, which is why only txn dedup was unenforced.
Fix: _ensure_dedup_index migrates DROP INDEX + CREATE UNIQUE INDEX on sqlite+pg at every init_db; loud-but-safe on dupes (prints GROUP BY finder, data untouched). Probed dev file first: 0 dupe groups, migration applied, rollback test green. Applies when: Any constraint that old files predate - ship DROP+CREATE migration, probe dupes first, never assume inline UNIQUE covers old files.

## 2026-10-28-29 Nixpacks system-pip breaks with PEP 668 - venv in the build
Symptom: 15 consecutive API deploys FAILED Oct27 at `pip install --upgrade pip` with externally-managed-environment; running API stuck on Oct27 08:03 build.
Cause: nixpacks.toml installed into Nix system Python; newer pip refuses. railway.json `|| true` masked the same failure on its path, and it was unclear which file won (log proved nixpacks.toml phases ran).
Fix: nixpacks.toml builds /opt/venv (pinned python312) and installs all deps inside; start cmd uses /opt/venv/bin/python. railway.json buildCommand removed (single source of truth), startCommand + Procfile updated to venv python. Never --break-system-packages. Files nixpacks.toml railway.json Procfile. Full proof at next deploy.
Applies when: Any Nix/Debian-based Python build - always venv, pin the interpreter, keep exactly one build definition.

## 2026-10-28-30 sqlite DDL reached psycopg2 and killed Railway boot
Symptom: Deploy f408c321 CRASHED at startup with IndexError: tuple index out of range in db.py executescript on Postgres.
Cause: _translate only handled ?/AUTOINCREMENT/INSERT OR REPLACE - strftime() view DDL, CREATE VIEW IF NOT EXISTS and CREATE TRIGGER passed through raw; one bad statement aborted the whole schema script.
Fix: apps/api/db.py _translate maps strftime->EXTRACT (DOW matches %w), views->CREATE OR REPLACE VIEW; executescript skips trigger DDL and warns-per-statement instead of aborting; dim_entity subquery gained AS alias (pg requires it). Pinned by tests/test_pg_translate.py (4 tests, no live server). Deploy 77fef8ea SUCCESS, /health/ready 200 backend pg.
Applies when: Any dual sqlite/pg schema - audit every CREATE for dialect-specific syntax, never let one statement fail boot.

## 2026-10-28-31 Worker gate KeyError killed every upload silently
Symptom: process_one_document returned (exception, None) on EVERY document - zero transactions ever persisted via worker; e2e still green.
Cause: reconcile.py returns opening_closing_top_bottom/... keys but worker/main.py read gate[opening_closing]/gate[running_balance] (stale names from scaffold). Broad except converted KeyError to (exception, None); e2e masked it with if result:.
Fix: worker reads the four real gate keys; drill tests assert result non-None unconditionally; PRAGMA busy_timeout=5000 for threaded TestClient flakes.
Applies when: Any pipeline with catch-all + optional-result tests - e2e MUST assert the happy path ran, never if result:. Verify with audit_log extraction.fail counts.

## 2026-10-28-32 Tenant lookup collapsed all sqlite users into one
Symptom: spy/run stored flags under the real tenant but GET /v1/flags returned [] - reads used default-tenant.
Cause: 15 endpoints used row[tenant_id] if isinstance(row, dict) else default-tenant; sqlite returns Row (never dict), so every tenant read as default-tenant. Writes used row[0] correctly - split-brain.
Fix: single _tenant_of(user_id) helper handling Row + dict; scripted repo-wide swap with asserted counts (13+1+1+2), grep proves zero else-default stragglers; full suite green.
Applies when: Any dual-backend row access - never branch tenant identity on isinstance; one helper, sweep to prove.

## 2026-10-28-33 Chat must be tools-first with mock detection
Symptom: /v1/chat returned a hardcoded mock string; naive LLM wiring would burn credit or hallucinate numbers.
Cause: No grounding boundary between model output and ledger facts.
Fix: chat.py runs deterministic DB tools first and templates the answer; a local model may only rephrase supplied facts; mock responses (no-key content or usage.error) are detected and skipped; 1s TCP pre-check avoids 16s SDK retry waits; hosted providers never attempted - zero credit.
Applies when: Any assistant over authoritative data - tools compute, model phrases, mocks never surface.

## 2026-10-28-34 pyHanko valid intact trusted are three verdicts
Symptom: tampered PDF still reported valid=True; signer CN lookup returned None.
Cause: valid covers CMS math only; digest breakage shows in intact; signer cert lives in status.signing_cert (asn1crypto), not status.signer. ByteRange gap bytes (CMS blob) are uncovered by design - flipping there proves nothing.
Fix: verify returns valid+intact+trusted+signer separately; tamper test parses /ByteRange and flips a covered content byte; assert intact False.
Applies when: Any signature verification - name which verdict each assertion pins.

## 2026-10-28-35 Pin cryptography on win-ARM64 before pip install
Symptom: pip install pyHanko tried building cryptography from source and failed (no Rust, no ARM wheel for latest).
Cause: Resolver upgrades transitive deps past what has wheels.
Fix: pip install pyHanko cryptography==<installed> keeps the working native build and adds the pure-Python tree.
Applies when: Any pip add on ARM Windows - check native deps first.

## 2026-10-28-36 Reset tokens are dev-only response content
Symptom: /v1/auth/forgot returned the reset token openly (clearmind leak pattern).
Cause: No boundary between dev convenience and prod secrecy.
Fix: token returned only when no email key is configured; with a key it is emailed and the response carries sent:true only; red test pins the keyless dev path so the suite still covers reset.
Applies when: Any secret-bearing response - gate on the production capability, not on ENV flags.

## 2026-10-28-37 Bare except plus permissive assert masks NameError
Symptom: suite green for days while apps/worker/main.py:48 passed undefined `tenant` - NameError on every real worker extraction.
Cause: bare `except Exception` returned ("exception", None) and the e2e test asserted `status in (...)` with `if result:` guard - the failure path was indistinguishable from a legit exception.
Fix: one-char-class fix to tenant_id; ruff F821 now gated (was the single F821 in the 175-finding baseline); e2e/drill tests re-run green with real extraction rows.
Applies when: Any pipeline with a failure status - assert the success path produces rows at least once, and gate F821 in CI.

## 2026-10-28-38 Image and LLM clients consult configured() before network
Symptom: Day-8 image tests hit real 127.0.0.1:3001 connection-refused despite monkeypatched env.
Cause: _image_client built the client from defaults without checking image_configured() - implicit localhost fallback reached the network with no key.
Fix: _image_client raises 422-style ValueError unless explicitly configured; tests pin the 422 path; zero live calls, zero credit.
Applies when: Any billable/network client - fail closed on missing config, never default to a live endpoint.

## 2026-10-28-39 Pyright raise of Optional needs an assert
Symptom: pyright reportGeneralTypeIssues on `raise last` after a retry loop (None does not derive from BaseException).
Cause: flow analysis cannot prove the loop body assigned the variable - pragma comments do not narrow types.
Fix: `assert last is not None` before raise; 0 errors on new modules.
Applies when: Any raise-after-loop - assert the invariant instead of commenting it.

## 2026-10-29-40 Checklists measured construction, not presentation
Symptom: All Day1-8 gates green while the landing page showed fake KPIs, a hero-flow checklist, and an architecture block to every visitor.
Cause: Every checkbox was backend-verifiable (endpoints exist, pytest green) - no gate ever said "zero mock data on landing" or "view as a stranger".
Fix: Rewrote landing with real copy + live API badge; add a UI-as-stranger review to Day9 polish before video/submit.
Applies when: Any "done" claim on user-visible UI - construction gates never prove presentation.

## 2026-10-29-41 NEXT_PUBLIC vars bake at build time
Symptom: Web service env var set on Railway but the live bundle still called localhost.
Cause: Next.js inlines NEXT_PUBLIC_* at build; setting the var without a rebuild changes nothing, and the Dockerfile never declared it.
Fix: Explicit ARG/ENV NEXT_PUBLIC_API_URL before `pnpm build` in apps/web/Dockerfile; process is set-var-then-redeploy; verified baked URL in the live JS bundle.
Applies when: Any Next.js-on-Railway wiring - declare the ARG, set, then rebuild.

## 2026-10-29-42 Stale hardcoded CORS origin from research project
Symptom: Deployed web could never call the API from a browser (preflight would fail each origin).
Cause: allow_origins hardcoded Clearmind's old Railway URL (web-production-ad9d4) copied during research, never replaced with FIN_SPY's.
Fix: `_cors_origins()` helper - localhost dev defaults + WEB_ORIGIN env (comma-separated); stale URL deleted; live OPTIONS preflight returns 200 + correct allow-origin.
Applies when: Adapting any config from a reference project - grep for the old project's URLs before calling it done.

## 2026-10-29-43 edit_file cannot match CRLF files
Symptom: muse.edit_file "no exact match found" on correct text in apps/api/main.py, Dockerfile, compose (0.95+ fuzzy scores).
Cause: Tool matches LF finds against CRLF bytes (verified 0D 0A via Format-Hex); .env.example (LF) worked in the same batch.
Fix: PowerShell fallback - [IO.File] read (preserves CRLF), Replace-Once with match-count==1 assertion, WriteAllText UTF-8 no BOM, git diff to verify; probe endings first when an edit fails.
Applies when: Any edit_file miss on a Windows checkout - check endings before rewording the find.

## 2026-10-29-44 Sandbox blocks node, uv store, and TestClient sockets
Symptom: tsc EPERM on typescript lib, `uv tool run` lock denied, TestClient tests fail on socket.socketpair - all green outside the sandbox.
Cause: Managed shell sandbox denies those paths/calls; files themselves are healthy (read_file opens them fine).
Fix: Run verification gates (tsc, build, pytest with TestClient, ruff via uv) unsandboxed with require_escalated; never "fix" code to satisfy a sandbox-only failure.
Applies when: Any gate fails with EPERM/lock/socketpair - confirm outside the sandbox before touching code.

## 2026-10-29-45 Local railway-up deploy playbook while GitHub frozen
Symptom: No auto-deploy (Lapjan1 frozen), dashboard Redeploy only rebuilds old commits, stray 914a9 domain unidentified.
Cause: Services still point at the frozen repo; only the local checkout has new code.
Fix: `railway service list` to inventory (proved 914a9 outside the project), `railway variables --set` for wiring vars, `railway up --service X --detach` (uploads working tree incl. uncommitted), poll `service list` for the new deployment ID, verify live (preflight/bundle/HTML). Vars print as a table, not KEY= lines - filter rows, never dump values.
Applies when: Any deploy while the git integration is dead - CLI up from the local repo is the release path.

## 2026-10-29-46 Backend trusts caller-supplied tenant_id
Symptom: Two users registering with the default tenant would share one workspace (isolation is by tenant, not user).
Cause: create_user takes tenant_id from the request (default "default-tenant") and creates the tenant row if missing - correct API, but the old UI hardcoded one tenant.
Fix: Frontend sends deterministic tenantIdForEmail (stable across browsers, unique per unique email); zero backend change; login returns the stored tenant.
Applies when: Any multi-tenant register flow - the client must mint a unique stable tenant or the backend must (pick one, never default-share).

## 2026-10-29-47 Paystack callback must carry user_id + public host
Symptom: Paystack browser redirect to /v1/billing/callback would 401 (no X-User-Id on a redirect) and APP_BASE_URL defaulted to localhost.
Cause: callback_url built without auth context; require_login accepts query user_id but nothing sent it.
Fix: callback_url = {APP_BASE_URL}/v1/billing/callback?user_id={user_id} (Paystack appends trxref with &); APP_BASE_URL set to the public API domain; webhook still activates independently.
Applies when: Any payment redirect flow - the return URL must authenticate the browser, not just the API.

## 2026-10-29-48 PowerShell 5.1 has no -SkipHttpErrorCheck
Symptom: Invoke-WebRequest OPTIONS preflight probe failed with ParameterBindingException, then NullReference in catch.
Cause: -SkipHttpErrorCheck is PS7+; PS5.1 throws on non-2xx and mishandles the manual check.
Fix: curl.exe for header-level probes (OPTIONS + Origin, status + allow-origin lines); keep Invoke-RestMethod for simple JSON GETs.
Applies when: Any HTTP-header verification on Windows PS5.1 - reach for curl first.

## 2026-10-29-49 Thrown Error drops the HTTP status pages need
Symptom: Upload page could not distinguish 402 trial-exhausted from generic failures - every error rendered the same red box.
Cause: api() helper threw `new Error(detail)` with no status attached.
Fix: Attach res.status to the thrown error (backwards compatible) + isPaywallError/isAuthError helpers; upload branches 402 to a PaywallNotice with plans.
Applies when: Any typed API client - carry status on errors so UI can branch (paywall, re-login) instead of string-matching messages.

## 2026-10-29-50 SQLite rebuild must drop views first, backup first, restore never drop
Symptom: First per-tenant migration lost 18 dev rows: DROP old + RENAME failed on dim_document view, except-path dropped the only surviving copy; table later recreated EMPTY by the fresh template (looked migrated, data gone).
Cause: SQLite refuses DROP+RENAME while any view references the name; cleanup assumed the copy was expendable.
Fix: Save/drop dependent views first, VACUUM INTO backup first (abort if backup fails), rebuild, recreate views, restore-on-failure (rename back, never drop the survivor); durable tests/test_doc_migration_rebuild.py rebuilds a scratch old-schema DB and byte-compares rows + views + backup. Prod pg untouched (ALTER-only path, constraint ops cannot drop rows).
Applies when: Any SQLite table rebuild - views, backup, restore, and a scratch-copy proof before the real file.

## 2026-10-29-51 Content store global, registration per-tenant
Symptom: Second tenant uploading identical bytes got HTTP 200 with ZERO db row - nothing to extract, nothing in inbox; trial receipt looked normal.
Cause: `if not storage_key.exists()` wrapped both the bytes-write AND the row insert, plus a global UNIQUE(sha256) schema constraint - first tenant wins, rest get phantoms.
Fix: Bytes written once globally; rows always per tenant (doc_id = sha256(tenant|sha)[:16]); same-tenant re-upload returns duplicate:true with the existing row and consumes no quota; schema migrated both backends (pg ALTER, sqlite rebuild per learning 50).
Applies when: Content-addressed storage + multi-tenancy - dedup the bytes, never the registration.

## 2026-10-29-52 Python splice script for CRLF edits beats long PowerShell
Symptom: A ~6KB PowerShell Replace-Once command died with weird parse errors (fingerprint: failures start mid-command) while short ones always worked.
Cause: Transport/proxy mangles very long commands; PowerShell quoting of code-bearing strings does not scale.
Fix: Write the snippet + a tiny splice script (markers, single-match asserts, byte-exact CRLF) as files via write_file, run `python splice.py`, verify with git diff + py_compile. Used for the 185-line db.py migration.
Applies when: Any CRLF edit longer than a few lines - file-splice, never mega-commands.

## 2026-10-29-53 Suggester must speak the active books + seed sentinel must be a template row
Symptom: Accept failed on a fresh tenant with "code '9999' does not exist ... Seed COA first", and the suggester proposed sme_cc codes (6200/6100/6600) while the tenant worked in personal books, shown as a bare code with no name.
Cause: (1) COA was seeded only via POST /v1/books/select, which the upload->review->accept flow never calls. (2) classify._category_for hardcodes sme_cc numbering, unvalidated against the active template. (3) First fix attempt gated seeding on COUNT(accounts) - but extraction creates a bank ledger row (same template, account_number set) first, so the count lied.
Fix: registry.ensure_coa_seeded sentinel = template row 9999 with account_number IS NULL (seed_coa is idempotent, fills the rest); wired into ledger.resolve_account + classify suggest + GET /v1/accounts; classify remaps raw codes per template (e.g. 6200->6030 personal, salary inflow 6300->4000) and enriches {account_name, account_type, active_template, mapped_from}; review UI shows code-name-type + dropdown from /v1/accounts + Use-suggestion. Tests tests/test_suggest_seed_wiring.py (16).
Applies when: Any "seeded?" gate on a table that holds more than one row kind - gate on the sentinel row, never a bare count.

## 2026-10-29-54 Dead-default LLM + duplicate-trap blocks all retries
Symptom: 3-page FNB text statement processed to exception + 0 rows; re-uploading did nothing (duplicate:true, no reprocess); Settings model switch unreachable (admin-only, user is owner-role).
Cause: (1) resolve_model default is freellmapi/localhost:3001, unreachable in Railway, so any doc below the 10% deterministic threshold gets 0 LLM rows in prod. (2) No requeue path existed.
Fix: MODEL_EXTRACTION=muse-spark-1.3 env on FIN_SPY (standard tier, user-approved, never contributor) + POST /v1/documents/{id}/requeue (owner-only, exception->queued, no trial use, 5 tests) + Inbox Retry button + PII-free parser-attempt counts in logs. Deployed both, verified live.
Applies when: Any pipeline with dedup-on-identical-bytes MUST ship a requeue path, and every localhost default must fail loudly in prod, not silently return empty.

## 2026-10-29-55 First-col-PK assumption + pg autocommit = partial garbage per retry
Symptom: Every persist crashed on pg 42P10 InvalidColumnReference AFTER the txn row committed (pg autocommit=True): each Retry added exactly one more visible row with no bbox link (user's R8/R1/R1 from 3 retries of Absa-garbage; "rows 0" log hid it because result=None on crash).
Cause: _translate rewrote every INSERT OR REPLACE to ON CONFLICT (first_col), but transaction_sources PRIMARY KEY is (transaction_id, span_id) composite - no such single-col constraint. SQLite never caught it (no ON CONFLICT there). No test pinned translation output.
Fix: Per-table conflict targets in _translate + PK-ensure migration for pg + worker FAILED prints include message text only for schema-shape error classes (identifiers, never row values). 2 translate tests; all OR REPLACE tables audited first-col-PK (only sources is composite).
Applies when: Any SQL-dialect translation layer - pin EVERY generated statement shape with a pure unit test, and never assume key shape; autocommit + crash = partial writes, so persist order must fail toward invisible leftovers.

## 2026-10-29-56 SQL comment text reaches the driver - strip it before execute
Symptom: GET /v1/me/export 500 on Railway (UndefinedTable merchant_memory) while the full local suite was green; boot log showed WARN tuple-index-out-of-range on the merchant_memory statement.
Cause: A `--` schema comment above the CREATE contained a literal `%` ("% allocation"). executescript pg path passed the whole statement (comments included) to psycopg2, whose %-format param substitution choked with empty params - so the CREATE never ran on Postgres. SQLite executescript ignores comments, so local never caught it.
Fix: executescript pg path strips full-line `--` comments before execute (apps/api/db.py:119-125); regression test_executescript_pg_strips_comment_percent in tests/test_pg_translate.py. Redeployed API, table created at boot, export 200 live.
Applies when: Any code that hands multi-statement SQL (with comments) to a %-formatting driver - sanitize or strip comments first; pin with a pure test.

## 2026-10-29-57 Vault path must be the volume mount + duplicates must heal missing bytes
Symptom: user stuck on already in your vault with zero extraction after several redeploys.
Cause: (1) VAULT_PATH defaulted to ./data/vault (ephemeral /app/data/vault) while the Railway volume sat empty at /data/vault (0MB used) - every deploy wiped bytes but DB rows survived. (2) Duplicate re-upload restored bytes but kept the old status, so the worker never re-ran.
Fix: VAULT_PATH=/data/vault env on FIN_SPY (volume now in use) + duplicate-with-restored-bytes resets to queued with requeued:true (tests/test_upload_restore.py 2). Receipt UI shows restored state. User re-uploads once to heal.
Applies when: any content-addressed store - assert at boot that the store path is on persistent disk, and make dedup verify bytes exist, not just the row.

## 2026-10-30-58 Picker counts must come from the filter's source of truth
Symptom: live bank-accounts offered "unknown (93)" but selecting it filtered to 0 rows - extractor writes account_number="unknown" on the accounts row but "" on transactions.
Cause: picker listed accounts-table labels while every filter matched transactions.account_number. Two sources of truth for one concept.
Fix: bank-accounts excludes the placeholder and synthesizes the unknown row from transaction counts (bbbe977); pinned by test_bank_accounts_synthesizes_unknown_row, red-verified via stash.
Applies when: any faceted picker - count from the same table + predicate the filter uses, or the counts lie.

## 2026-10-30-59 Single-quoted Python strings eat SQL '' literals in splices
Symptom: sqlite3.OperationalError near ")" on the __unknown excel path; file showed t.account_number=) with the '' gone.
Cause: splice replacement written as '...account_number='')' - the '' closed the Python string early and adjacent-literal concatenation silently dropped the quotes.
Fix: double-quoted Python strings for any replacement containing SQL literals; fixed in .fin_spy_tmp/fix_uf.py, audited all 9 unknown clauses by grep.
Applies when: generating code with nested quoting - prefer the quote style that never collides, and grep the output for the literal you meant to write.

## 2026-10-30-60 Every branch of a conditional query needs its own param tuple
Symptom: sqlite3.ProgrammingError 2 placeholders vs 3 bindings on powerbi __unknown - the _fj/_dd unknown branches added no ? but the execute still passed account_number.
Cause: query-string splice updated but the param tuple two lines below kept the old shape; known-account tests passed because that branch was consistent.
Fix: _unk-aware param tuples + tests/test_unknown_scope_reports.py covering unknown on trial/dashboard/auditor/powerbi, not just transactions.
Applies when: any query built by string branches - test every branch, because the green branch proves nothing about its siblings.

## 2026-10-30-61 A splice that prints green is not a splice that landed
Symptom: worker attribution hunk reported success but tests showed the old behavior; the hunk was absent on disk while a later splice referencing its variables silently no-op'd inside try/except.
Cause: trusted the script's print instead of reading the file; the swallowing try/except around the doc UPDATE hid the NameError for a full cycle.
Fix: every splice script asserts its marker by reading the file back before printing green (see splice_worker_attribution2.py); fixed silently-swallowed NameError the same hour.
Applies when: any generated edit - verify by reading the artifact, never by the generator's own report.

## 2026-10-30-62 .get(key, default) returns stored None, and class-only logs hide it
Symptom: every CSV tamper verdict missing live; worker log showed stage=tamper exc=TypeError with no message.
Cause: text-reader pages store width/height as None, so page.get('width', 1000) returns None (the key exists) and None + 10 raises. Tests only ran tamper on PDFs (dims set). Class-only log line cost a full debug cycle.
Fix: `or`-defaults for dims/bbox (e5dfea2), CSV tamper test pinned, metadata-stage logs include truncated messages (metadata errors carry no row values).
Applies when: any .get() default over nullable columns/pages - use `or` when None is a live value; and log messages on metadata stages where PII cannot appear.

## 2026-10-30-63 Content sniffs must skip framing lines, not just blank ones
Symptom: titled bank CSVs extracted 0 rows; the title row broke the uniformity check so bytes fell to the splitlines path where raw commas fused amounts.
Cause: _looks_csv required the FIRST rows uniform; real exports frame the table with title/balance lines.
Fix: skip leading <3-cell rows, then require the uniform run to hold (same 2+/3+ bar); prose still rejected, TXT-amount guard intact (9c755e8, tests/test_csv_sniff.py 4).
Applies when: any format sniff - frame lines are data about the file, not rows of the table; skip them before judging shape.
## 2026-10-30-64 Stated totals beat derived totals; y-sort changes row order
Symptom: golden reconciliation failed after row-major regrouping - opening 2109055/closing 1189055 vs stated R12 340.55/R20 790,55.
Cause: two stacked issues. (1) FNB parser CLOBBERED stated balances with row-derived estimates, which assume chronological rows. (2) y-sorted grouping returns visual order, not emission order; the synthetic PDF is emitted bottom-up, so rows run reverse-chronological and the estimates went wrong. Native grouping had masked (1) by preserving emission order.
Fix: stated balances are ground truth, derivation is fallback-only (apps/worker/parsers/fnb.py:182-199); pinned both directions with tests. Period year anchors on the END year (years[-1]) since ranges span Dec/Jan.
Applies when: any parser combining stated + computed values - stated wins, computed fills gaps only; and any grouping change must re-check order assumptions downstream (golden suite is the tripwire).

## 2026-10-30-65 Auth failures must raise, never mock
Symptom: live Meta key 401s, LLM fallback dead, zero-row docs marked proposed - silent scam state.
Cause: MetaClient.complete swallowed EVERY exception into a mock zero-row result; worker proposed anything the gate didn't fail, and an empty gate passes vacuously.
Fix: 401/403 (by SDK name or status code) raise ModelAuthError naming provider/model (key never echoed), re-raised through llm_fallback, worker audits extraction.auth_fail + marks exception; decide_doc_status forces zero rows to exception with a re-extract warning (tests/test_loud_failures.py 6/6). Chat keeps its broad catch (best-effort rephrase, tries next provider).
Applies when: any fallback chain - distinguish 'no key configured' (mock OK for tests) from 'key rejected' (loud, human must rotate); and any gate over empty input must fail closed, never pass vacuously.
## 2026-10-30-66 A passing test can pin a bug; whitespace matches poison strips
Symptom: live FNB rows had fused descriptions (`SHOP A` -> `SHOPF100.00-`); fixing it turned the bank-gate test red.
Cause: (1) FNB's loose amount regex matches inter-word spaces, and the desc-strip loop `replace(' ','')` deleted every space then failed later strips. (2) The bank-gate test passed ONLY because `parse_sa_amount(' ')` crashed on those same whitespace matches (0 rows -> None); its premise comment ("FNB dates do not match DD/MM/YYYY") was false - the pattern matches.
Fix: filter amount matches to digit-bearing spans (FNB 4 sites; STDB immune by regex construction, ABSA already filtered - verified, no redundant lines); rewrote the gate test to its true contract (right parser + right values on valid rows, fall-through on unparseable lines) with the history in its docstring (5e8d3ad).
Applies when: any regex with `\s` inside a `+` class feeding `str.replace` - filter digitless matches; and any test that passes via an exception path deserves a premise check (HEAD-vs-mine probe on the exact fixture line settles it in seconds).
