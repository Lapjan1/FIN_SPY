# P0-H: Owner Settings Access — Task Document

## Goal
Tenant owners (default role) may read/change non-secret model/effort
preferences; keys stay admin-only + redacted; billing-ish keys stay
admin-only (D6, no per-tenant table).

## Red
New `tests/test_owner_settings.py` (3 tests): `/v1/settings/preferences`
404 before the endpoints existed.

## Implement
- `apps/api/auth.py` — `require_owner_or_admin` (login + role in
  admin/owner or ADMIN_EMAIL allowlist; members 403) + `is_admin_user`.
- `apps/api/main.py` — `OWNER_PREF_PREFIXES` (model, effort, ai_provider,
  ollama_url, freellmapi_, show_exact); `GET /v1/settings/preferences`
  returns only those keys and skips anything secret/billing;
  `POST /v1/settings/preferences` keeps the 400 secret fail-closed rule
  and 403s non-allowlisted keys for non-admins (admins keep full write).
  `/v1/settings` itself stays admin-only (pinned contract untouched).
  Spliced via `.fin_spy_tmp/splice_owner.py` (CRLF file).
- `apps/web/src/app/settings/page.tsx` — tries `/v1/settings`, falls back
  to `/v1/settings/preferences` for owners; model/effort editor works in
  both modes; cost guards + full table stay admin-gated.

## Green
- `tests/test_owner_settings.py` + `tests/test_settings.py`: 6 passed —
  owner reads model without secret leakage, writes model/effort, gets 400
  on meta_api_key and 403 on trial_pages; member 403; anonymous 401;
  admin writes trial_pages; existing admin-only pins still green.
- `pnpm --dir apps/web exec tsc --noEmit` → exit 0.
