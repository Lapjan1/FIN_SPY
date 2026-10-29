# P0-A: Byte-download wrappers — DONE 2026-10-29

Goal: the 5 report endpoints stream file bytes (FileResponse) instead of
JSON with a server-local path the browser cannot use.

## RED (before)
`pytest tests/test_report_downloads.py` → 4 failed (content-type
application/json, no attachment), 2 passed (signed-pdf 422 gate when
unconfigured + 401s already correct).

## IMPLEMENT
- `apps/api/main.py`: 5 endpoints now FileResponse with media type +
  traversal-proof filenames via new `_safe_name()`; powerbi bundles
  xlsx+csvs through new `bundle_powerbi_zip()`; vendor filename
  sanitized (was raw user input in a server path); forensic warnings
  preserved as `X-Report-Warning` header (signed-pdf, evidence-pack).
- `apps/api/reports.py`: `bundle_powerbi_zip()` helper (reused by P0-B).
- Converted 3 tests pinning old JSON shapes to byte assertions with
  the same intent (sheet count via openpyxl, manifest via zipfile,
  PAdES verify on downloaded bytes, warning via header).

## GREEN (after)
- `pytest tests/test_report_downloads.py` → 6 passed (incl. auditor
  CSV cross-tenant isolation: B's file lacks A's marker row).
- Full `pytest tests` → 238 passed.
- Gates: ruff/pyright unavailable offline (not run, recorded); tsc N/A
  (no web touched); live smoke at deploy gate.

## NOTE (pre-existing, not fixed here)
Builder server paths embed raw tenant_id from register input; only the
new download filenames are sanitized. Server-path hardening is a
follow-up (would change file_key values other tests pin).
