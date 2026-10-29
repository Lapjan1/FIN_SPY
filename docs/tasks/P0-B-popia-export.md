# P0-B: POPIA ZIP builder — DONE 2026-10-29

Goal: GET /v1/me/export streams a ZIP with everything held on the
caller's tenant (Q1 YES: originals included), and nothing else.

## RED (before)
`pytest tests/test_popia_export.py` → 3 failed (404, no route).

## IMPLEMENT
- `apps/api/reports.py::build_popia_zip`: tenant CSVs (14 tables incl.
  doc-joins for pages/runs + entry-join for lines), profile.json,
  originals/ (byte copies; missing vault files listed honestly in
  manifest), manifest.json (counts + sha256 + excluded list), README.
  Secrets never included: password hashes, payment authorizations,
  reset tokens, webhook events, global settings.
- `apps/api/main.py`: GET /v1/me/export → FileResponse + audit entry.
- Bugs found by green phase (all fixed): splice quoting typo (line
  258); journal_lines/document_pages/extraction_runs need JOINs (no
  tenant_id of their own); test's own filename + count-query fixes.

## GREEN (after)
- `pytest tests/test_popia_export.py` → 3 passed (complete ZIP incl.
  manifest-vs-DB count match on 6 tables; cross-tenant isolation;
  401 logged-out).
- Full `pytest tests` → 241 passed.
- Gates: ruff/pyright unavailable offline (not run); tsc N/A (no web);
  live smoke at deploy gate.
