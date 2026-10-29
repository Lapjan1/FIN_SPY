# P0-E: Books Screen — Task Document

## Goal
`/books` page: template switch + trial-balance table (P0-D filter) +
suspense watchdog (promise 2: "trial balances per bank account").

## Red
No page existed: `/books` 404, no client wrappers for
`/v1/books/*`, `/v1/journal/trial-balance`, `/v1/journal/suspense`.

## Implement (web only, all endpoints already existed)
- `apps/web/src/lib/api.ts` — types `BookTemplate`, `BooksActive`,
  `TrialLine`, `TrialBalance`, `SuspenseStatus` + `fetchBookTemplates`,
  `fetchActiveBook`, `selectBook`, `fetchTrialBalance(acct?)`, `fetchSuspense`.
- `apps/web/src/app/books/page.tsx` — new page: template buttons (POST
  select + reload), bank-account filter form, trial table (zero rows
  hidden, totals footer, balanced flag), suspense panel (status, parked
  R, aging, unposted count, reasons).
- `apps/web/src/app/layout.tsx` — nav link `/books`.

## Green
- `pnpm --dir apps/web exec tsc --noEmit` → exit 0.
- No backend change; P0-D pytest evidence (3 focused, 244 full) still holds.
