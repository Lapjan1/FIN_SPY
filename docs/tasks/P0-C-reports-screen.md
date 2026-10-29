# P0-C: Reports screen — DONE 2026-10-29

Goal: /reports page with one download button per output + POPIA ZIP.

## RED (before)
No /reports route (404), no download helper in api.ts.

## IMPLEMENT
- `apps/web/src/lib/api.ts::downloadReport`: authed blob fetch + save,
  returns X-Report-Warning header, throws typed errors like api().
- NEW `apps/web/src/app/reports/page.tsx`: RequireSession gate, 6
  download rows with plain descriptions, optional from/to dates for
  dated reports, warning + error display (existing slate style).
- `apps/web/src/app/layout.tsx`: nav link added.
- One tsc error fixed during green (SessionBar me prop).

## GREEN (after)
- `pnpm exec tsc --noEmit` → exit 0.
- No web test harness in repo (pre-existing); live click-through of all
  6 buttons at deploy gate (record sha256 per file in STATE).
- Gates: pytest N/A (no py touched); ruff N/A; pnpm lint pre-existing
  broken (untouched).
