# P0-F: Debt Screen + Cashflow Default — Task Document

## Goal
`/debt` page (form + plan table + what-if) with extra-cash prefilled from
the tenant's own average monthly surplus (D3). Engine + R45k/R20k/R10k
ordering tests already existed in `tests/test_spy_day5.py`.

## Red
New `tests/test_debt_defaults.py` (2 tests): `GET /v1/debt/defaults`
returned 404 before the endpoint existed.

## Implement
- `apps/api/main.py` — `GET /v1/debt/defaults`: per-month net
  (credit inflow minus debit outflow, rejected excluded) averaged over
  months with postings; `extra_cash_default_minor` clamped at zero.
  Spliced via `.fin_spy_tmp/splice_debt.py` (CRLF file).
- `apps/web/src/lib/api.ts` — `DebtInput`, `DebtPlan`, `DebtDefaults`
  types + `fetchDebtDefaults`, `postDebtPlan`.
- `apps/web/src/app/debt/page.tsx` — new page: dynamic debt rows
  (creditor/balance/APR/min), method select, extra-cash input prefilled
  from defaults, payoff-order table, totals grid, what-if block,
  server disclaimer shown verbatim.
- `apps/web/src/app/layout.tsx` — nav link `/debt`.

## Green
- `tests/test_debt_defaults.py` + `tests/test_spy_day5.py`: 13 passed
  (avg 10500 over 2 months; empty → 0 months; negative avg → default 0).
- `pnpm --dir apps/web exec tsc --noEmit` → exit 0.
