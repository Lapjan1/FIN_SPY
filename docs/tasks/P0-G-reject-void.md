# P0-G: Reject/Void Flow — Task Document

## Goal
`POST /v1/review-queue/{id}/reject`: proposed → rejected with no journals;
posted → mirror-image reversals + rejected, append-only (Q2: voided rows
stay visible as history). UI buttons in review + transactions.

## Red
New `tests/test_reject_void.py` (3 tests) against missing endpoint: 3 failed.

## Implement
- `apps/api/ledger.py` — `void_transaction(tenant, txn, reason, by)`:
  validates (reason/isolation/existence), reverses every posted entry via
  `_reverse_entry`, sets status rejected, appends a status revision row.
  Spliced via `.fin_spy_tmp/splice_reject.py` (CRLF file).
- `apps/api/main.py` — `ReviewRejectIn{reason}` + `POST
  /v1/review-queue/{txn_id}/reject` reusing `_load_owned_review_txn` /
  `_require_review_reason`, audit action `review.reject`.
- `apps/web/src/lib/api.ts` — `RejectResult` + `rejectTransaction`.
- `apps/web/src/app/review/page.tsx` — "Reject / void" button (confirm
  dialog, shared reason field).
- `apps/web/src/app/transactions/page.tsx` — "Void with reversals" box
  under the selected row (own reason field, hidden once rejected).

## Green
- `tests/test_reject_void.py`: 3 passed — proposed leaves zero journals;
  posted nets d==c==20000 over 2 entries, trial balanced, audit row present;
  blank reason 422, missing txn 422, cross-tenant 403.
- `pnpm --dir apps/web exec tsc --noEmit` → exit 0.
