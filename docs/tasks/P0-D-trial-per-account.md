# P0-D: Trial Balance Per Account — Task Document

## Goal
`trial_balance()` gains an `account_number` filter so the UI can show
per-bank-account books (promise 2: "trial balances per bank account").

## Red
New `tests/test_trial_per_account.py` (3 tests) run against unmodified code:
`TypeError: trial_balance() got an unexpected keyword argument 'account_number'`
plus endpoint 422-path missing.

## Implement
- `apps/api/ledger.py:trial_balance` — new optional `account_number` param:
  resolves the tenant's bank `accounts` row, raises `ValueError("Invalid
  parameters: unknown account_number ...")` when absent, restricts the
  journal-lines join to entries touching that bank account, echoes
  `account_number` in the payload.
- `apps/api/main.py` — `GET /v1/journal/trial-balance` accepts
  `?account_number=`, maps `ValueError` → 422.
- `tests/test_trial_per_account.py` — fixed own helper twice (real
  `decide()` 8-arg signature + `post_transaction()`, then CAT `6030`
  which exists in the personal template; `6200` does not).

## Green
- Focused: `3 passed` (`tests/test_trial_per_account.py`).
- Full: `244 passed` (`python -m pytest tests -q -p no:cacheprovider`).

## Evidence
- `tests/test_trial_per_account.py:55` filter math (111→10000, 222→25000,
  sum == full 35000, balanced both slices).
- `tests/test_trial_per_account.py:79` unknown account raises.
- `tests/test_trial_per_account.py:88` endpoint 200 + 422 paths.
