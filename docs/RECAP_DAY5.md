# RECAP Day 5 Finish - Spy + KPI + Debt - 2026-10-28

Per docs/TIMELINE.md Day5: spy subscriptions duplicates F-010 fee Benford F-020 leak R/mo, KPIs runway burn savings debt-to-income, debt snowball vs avalanche Decimal what-if, R45k/R20k/R10k fixture ordering.

## What We Have Done (Oct28 - Spy/KPI/Debt)

### Detectors - apps/worker/spy/detectors.py (rewritten, was [] stubs)
- `detect_recurring`: groups debit outflows by normalized merchant, longest run with 25-35d gaps + amounts within 5% of anchor, >=3 occurrences -> SUB subscription with median monthly cost, cadence, tx_ids.
- `detect_duplicate`: exact fingerprint match -> DUP; same amount + same norm desc within 1 calendar day, different fingerprint -> NDUP 24h near-duplicate.
- `detect_fee`: F-010 keyword scan (fee/service charge/FX/commission/account fee/penalty/dishonour...) with amounts.
- `detect_anomaly_iqr`: F-030 per-merchant IQR, groups >=5, flags above Q3+1.5*IQR with fence + median evidence.
- `detect_benford`: BEN first-digit smoke on >=20 outflows, flags digit-1 share outside 15-45% (expected 30.1%).
- `leak_score_per_month` F-020: sum of recurring monthly costs. `flag_id` deterministic SHA256(tenant|code|key) so re-runs overwrite.
- `detect_private_use` kept + code RP.

### Debt - apps/worker/spy/debt.py (real amortization)
- `_simulate`: month-by-month Decimal loop (interest HALF_UP to cent, minimums, extra to first in order), 600-month cap + 3-strike no-progress guard (negative amortization breaks early with stuck=True instead of Decimal overflow on absurd APR - found via red test APR 150).
- `plan_debts`: snowball (smallest first) vs avalanche (highest APR first), months + total interest + interest_saved vs other method, warnings, narrative + not-financial-advice disclaimer. 422 on bad method/negative extra, empty-list safe.
- `what_if_extra`: base vs boosted months + interest saved.

### KPI + endpoints - apps/worker/spy/kpi.py, apps/api/main.py
- `compute_kpis.subscription_creep_minor` now real via leak_score_per_month (was `pass` stub); dashboard leak_score_per_month_minor flows through.
- POST /v1/debt/plan wired to plan_debts + what_if (was months:12/saved:0 hardcoded).
- POST /v1/spy/run (new): runs all detectors over tenant txns, INSERT OR REPLACE into flags with severity (DUP/NDUP high, F-030 medium, rest info/low), audit-logged, returns by_code + leak.
- BUGFIX: dashboard/review/flags/spy endpoints used inline `isinstance(row, dict) else "default-tenant"` which is always default-tenant on sqlite Rows - spy/run wrote real tenant, GET /v1/flags read default-tenant and returned []. All four now use `_tenant_of(user_id)`.

### Tests - tests/test_spy_day5.py (11 new)
- Recurring detect + tolerance/minimum/inflow-negative; dup exact+near; fee F-010; anomaly outlier + small-n; benford gamed + small-n; leak + KPI wiring; R45k/R20k/R10k ordering (snow [10,20,45], aval [45,20,10] by APR 21/18/9) + avalanche-saves + what-if + stuck-warning; debt endpoint real maths + 422; spy/run persist + flags GET + idempotent re-run.

## Evidence
- `python -m pytest -q -p no:cacheprovider` 141 passed 0 failed (unblocked shell).
- `uvx ruff check` clean on detectors.py/debt.py/test_spy_day5.py; kpi.py 4 + main.py 17 pre-existing untouched.
- Day-4 commit 4736476 landed first (45 files, bundle/lock/reports excluded, secrets scanned clean).

## What We Learned
- Tenant-lookup pattern `isinstance(row, dict) else default` silently collapses all sqlite tenants into one; single helper `_tenant_of` is the fix - audit remaining old endpoints for the same inline pattern.
- Amortization loops need a progress guard, not just a month cap: min-payments-below-interest grows balances exponentially and kills Decimal precision before any cap trips.
- Red tests earn their keep: test_debt_invalid_apr (APR 150) caught the overflow the happy-path fixture never would.
