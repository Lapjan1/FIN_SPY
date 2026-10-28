# RECAP Day 4 Finish - Books + Review UX + Private/Business - 2026-10-28

Per docs/TIMELINE.md Day4: dynamic per-tenant COA no hardcoded, private/business/mixed classification rules-first AI-second human-last + merchant memory, journal entries trial balance, tenant isolation tests, review queue accept/edit with reason (append-only revisions).

## What We Have Done (Oct28 - Books)

### Ledger-core - apps/api/ledger.py (new)
- `post_transaction(tx, classification, created_by)`: int-cents money only (rejects float/bool/zero), nature/business_pct validation, target resolved in active_template first else any template else UnknownAccount 422, bank via tx account_id/account_number, balanced lines (outflow Dr expense/Cr bank, inflow Dr bank/Cr income, mixed 3-line split via 3300/7000/3210/3200), Python debits==credits==amount check, then UPDATE posted=1 with rollback + UnbalancedEntry on trigger abort.
- `trial_balance(tenant_id, as_of, entity_id)`: per-account debits/credits/net + totals + balanced + zero, tenant-isolated.
- `get_journal_entries(tenant_id, transaction_id, limit)` with lines + account code/name.

### Classify - apps/api/classify.py (new)
- `suggest_classification`: rules-first merchant_memory per merchant per account (source rule), AI-second deterministic heuristics with acts rationale (Companies Act s19 s28 s76 company-private exception, Income Tax s11(a) sole-prop mixed 60%), human-last unknown confidence 0. Mixed only when entity sole_prop/mixed + shared keyword (fuel/vehicle/rent).
- `decide`: reason required, category must exist for tenant, isolation PermissionError 403, append-only classification row with supersedes_id + transaction_revisions + merchant_memory learn + audit_log.

### Endpoints - apps/api/main.py Day4 block
- POST /v1/journal/post, GET /v1/journal/trial-balance?as_of=&entity_id=, GET /v1/journal/entries?transaction_id=
- POST /v1/classifications/suggest|decide
- POST /v1/review-queue/{id}/accept (suggest-fill, decide+post+confirm) and /edit (field revisions + fingerprint recompute + duplicate-collision 422 + optional decide). Reason required everywhere; 422 Invalid parameters / 403 isolation guard. (Accept first rejected unknown; 9999 addendum below routes it to suspense instead.)

### Trigger fix - LEARNINGS 2026-10-28-24
- Old count>=2 prefix check rejected legal 3-line splits. New: journal_entries.posted + guard triggers (balance enforced only when posted=1, >=2 lines to post, posted lines guarded, unpost to delete). init_db DROPs old triggers + _ensure_schema migrates posted (existing data/fin_spy.db migrates on next init). vendor._post_entry same mechanism; cleanup via _cleanup_journals unpost-first.

## Evidence
- Tests: 16 new tests/test_ledger_day4.py, full suite `python -m pytest -q -p no:cacheprovider` = 104 passed + 1 pre-existing env failure (test_llm_fallback_mock needs live freellmapi:3001; apps/worker + test file untouched, fails identically on pristine tree).
- Ruff: new files `ruff check` + `ruff format --check` clean; edited files match HEAD baseline exactly (main 17, db 6, vendor 6 pre-existing; db cleanup 20->18 improved). Removed-lines oracle f5059256... equality after format restore per LEARNINGS 2026-10-28-25.
- Files (Day4 close totals): apps/api/ledger.py, classify.py, audit.py (new), apps/api/main.py +560, apps/api/db.py +145, apps/api/vendor.py +17, config/banks.yaml +6 (9999), apps/web review page + api.ts +114, tests/test_ledger_day4.py (16) + test_suspense_9999.py (9) + test_edit_repost_legal.py (12) new, tests/test_db_powerbi.py +11.

## Learned
- 2026-10-28-24: DB invariant over multi-row group -> enforce at completion event (post), never on intermediate prefixes.
- 2026-10-28-25: Formatter hunks merge across intent boundaries -> snapshot removed-lines hash before formatting; new files format-clean, edited files keep surrounding style.

## 9999 Suspense Addendum (same day, per user research)
- Unknowns post under proper debit/credit to 9999 Suspense - Unclassified Pending Review (expense, all templates + coa_seed, auto-migrates on reseed) so income/expense stay complete; trial always balances.
- Re-decode auto-transfers the posted leg 9999 -> real account (gross legs auditable, 9999 nets 0); same-category or unposted re-decides transfer nothing; failures visible via transfer_error.
- GET /v1/journal/suspense watchdog: stuck money only + unposted-confirmed completeness check + 5%/30d thresholds -> ok/review.
- 9 tests, suite 113 passed + 1 pre-existing env failure, ruff zero new findings.

## Repost + Legal Addendum (same day, per user rule)
- Amount/date edits on posted txns reverse all entries + post fresh at current values (latest classification, else inferred target, else 9999), atomic with rollback; description-only and unposted edits post nothing.
- Forward done forensically: stored balances are immutable bank-printed facts (never rewritten); reverify_chain re-runs all affected checks after each edit; trial/KPI/reports read live.
- GET /v1/audit/human-changes (full correction record with reasons) + GET /v1/audit/verify (chain + vault rehash proof); source rows proven byte-identical after edits; forged audit rows detected.
- Dedup gap fixed: fingerprint index migrated plain -> UNIQUE (dev file had 0 dupes).
- 12 tests, suite 125 passed + 1 pre-existing env failure, ruff zero new findings.

## Review UI Addendum (same day - Day 4 fully closed)
- Thin review queue page over existing endpoints (no UI logic): queue list, auto suggestion, accept/edit with required reason, result shows journal + repost + reverify outcome.
- Typed api.ts client wrappers added for Day 6 reuse; Review link in nav + home.
- tsc clean, next build green with /review prerendered; review-queue payload += account_number (e2e+smoke green).

## Next (Day5)
- Spy detectors + forensic F-001..F-050 + KPI wired to ledger + debt snowball/avalanche Decimal + R45k/R20k/R10k fixture; vendor auto-book delegate to ledger.post_transaction.
