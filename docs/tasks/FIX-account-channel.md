# FIX: Account Channel (auto-book orphans + Move + filters + picker)

## Goal
Every function reachable per bank account: vendor auto-book writes
rule-sourced classifications (no more posted-but-unclassified orphans),
confirmed rows can Move out of suspense, transactions/documents carry
account+doc columns and filters, one global picker drives the app.

## Amendments to the pasted plan
- Debt screen excluded from the account filter: debts are hand-typed rows
  with no account link; filtering them would be fake precision.
- Picker includes "Unknown account" for the `""` scope.

## Steps
1. [x] Vendor auto-book: classification (source=rule) + confirmed + audit.
2. [x] `POST /v1/transactions/{id}/move` + "Move to" buttons.
3. [x] `GET /v1/bank-accounts`; doc/account columns + filters; reports
   `account_number` passthrough; global `AccountSelector`.
4. [x] Excel classification columns + 9999 method note.
5. [x] Full re-verify + deploy + audit.

## Evidence
- Step 1 `tests/test_vendor_auto_book_classifies.py` 2 passed:
  auto-book writes rule-sourced classification + confirmed + audit.
- Step 2 `tests/test_move_from_suspense.py` 2 passed:
  `POST /v1/transactions/{id}/move` transfers legacy orphans via
  `transfer_posting`, re-decides via `decide()`; UI Move buttons wired.
- Step 3 `tests/test_account_filtering.py` 3 passed +
  `tests/test_report_account_filter.py` 3 passed +
  `tests/test_unknown_scope.py` 2 passed +
  `tests/test_unknown_scope_reports.py` 2 passed:
  `GET /v1/bank-accounts`, transactions/document filters, excel +
  auditor-csv + powerbi `account_number` passthrough with 422 on unknown
  accounts (`_require_account`), `__unknown` sentinel selects
  empty-account rows on transactions / trial / dashboard / all three
  report builders. Evidence pack + signed PDF + POPIA stay whole-tenant
  by design. UI: `AccountSelector.tsx` + localStorage persistence drives
  Transactions, Books, Reports, Dashboard; Inbox badges; Transactions
  rows show doc + account + nature.
- Step 4 `tests/test_excel_classification_cols.py` 2 passed:
  Transactions sheet gains account_number | document | nature |
  category | rationale | status; Method_Notes documents 9999-on-P&L.
  Fixed live bugs found by the tests: eaten `''` in txns unknown filter,
  `_fj`/`_dd` param tuples for the unknown branch.
- Full suite: 291 passed (275 baseline + 16 new), 0 failed.
- `pnpm --dir apps/web exec tsc --noEmit`: 0 errors.
- Secret-print grep over touched backend files: 0 hits.
- ruff unavailable in this env (`uv run` broken: pyright>=1.15
  unsatisfiable, pre-existing); tests + tsc are the gates.
- Live-smoke catch (fixed in `bbbe977`, pinned by
  `test_bank_accounts_synthesizes_unknown_row`, red-verified via stash):
  extractor writes `account_number="unknown"` on the accounts row but `""`
  on transactions, so the picker offered "unknown (93)" while the filter
  matched 0 rows. `GET /v1/bank-accounts` now excludes the placeholder
  and synthesizes the unknown row from transaction counts.
- Live `c9578c4c` + web `90ab2962` (both SUCCESS): 401 unauth, 422 on bad
  account (transactions + excel), 2 CSVs queued -> 93 txns extracted,
  bank-accounts / __unknown filter / dashboard all agree 93, accept to
  9999 -> Move 9999->6030 (`je-55877673`), downloaded workbook shows
  classification columns with the moved row confirmed/6030.
