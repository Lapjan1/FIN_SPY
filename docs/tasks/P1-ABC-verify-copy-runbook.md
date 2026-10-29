# P1-A/B/C: Verify Email, Fix Copy, Cleanup Runbook — Task Document

## P1-A: Verify EMAIL key live (no code; needs a human inbox)

Statically verified:
- `POST /v1/auth/register` calls `send_welcome_email`
  (`apps/api/main.py:197-198`).
- `POST /v1/auth/forgot` calls `send_reset_email` when a key exists
  (`apps/api/main.py:215-221`).
- `send_email` tries Resend (`RESEND_API_KEY` or `email_api_key`
  setting), falls back to SMTP (`smtp_host/user/pass`), else mock-logs
  + audit `email.mock_sent` (`apps/api/email.py:31-49`).

Live check (owner runs after deploy):
1. Set `RESEND_API_KEY` + `EMAIL_FROM` (or `email_from`) in Railway;
   verify the sender domain in Resend (free tier otherwise only sends
   to the account holder).
2. Register a new address → welcome arrives within a minute.
3. Forgot-password for that address → reset link arrives, token works,
   expires after 1h.
4. If nothing arrives: check Railway logs for `email.mock_sent`
   (key missing) vs Resend 4xx (domain/sender issue); SMTP fallback
   needs `smtp_host/user/pass/from` instead.

## P1-B: Trial copy "pages" → "uploads" (done)

The meter counts `source_documents` rows (uploads), not PDF pages
(`get_document_count`, `apps/api/auth.py:167-171`); the help page already
said uploads. Reworded every user-visible "N pages" trial string to
uploads; API/DB names (`trial_pages`, `trial_pages_remaining`, `pages`)
kept as contract:
- `apps/web/src/app/account/page.tsx` (trial banner, Pro badge, plans).
- `apps/web/src/app/refund/page.tsx`, `terms/page.tsx`, `privacy/page.tsx`.
- `apps/web/src/components/PaywallNotice.tsx`.
- `apps/web/src/app/settings/page.tsx` label (key unchanged).
- `apps/api/main.py`: 402 detail, terms/refund billing metadata strings.
- Left intact: help "however many pages it has" (real PDF pages),
  code comments/docstrings, API field names.

Green: `tsc` exit 0; `test_settings + test_db_auth_paystack +
test_pack_day7` 12 passed.

## P1-C: Stranded-row cleanup runbook (done)

`docs/runbooks/stranded-rows.md`: find linkless txns (NULL document_id
or zero `transaction_sources` rows), re-extract or void via P0-G
reject endpoint, re-verify trial balance per account + suspense +
human-changes audit, record in STATE.md.
