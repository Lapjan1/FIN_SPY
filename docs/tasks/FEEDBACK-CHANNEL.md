# Feedback channel + About/Contact - task record

User asked (2026-11-02): first-functional release needs a way to hear about
unprogrammed cases and unknown bugs. Built: `POST /v1/feedback` (authed,
rate-limited, owner-notified) + `/about` + `/contact` + contextual links on
failure states. Deliberately NO new top tabs (bar already crowded at 12) -
menu/submenu regrouping proposed separately, not implemented here.

## Steps

1. [x] Red: `tests/test_feedback.py` 6 tests (401 no-auth, 200 persist,
   422 short message, 422 bad category, 404 unknown doc, 429 rate limit).
   5 failed as 404 pre-implement; the 404-doc test passed vacuously
   pre-route (missing route is also 404) and now passes for the right
   reason (route exists + tenant doc check).
2. [x] Backend (`apps/api/db.py`, `main.py`, `email.py`, all CRLF spliced):
   `feedback` table in `init_db` (auto-migrates on startup, sqlite + pg;
   comment-free DDL per pg executescript quirk) + index; `FeedbackIn`
   (subject 1..120, message 10..4000, optional document_id/page_url) +
   `POST /v1/feedback` (require_login, tenant guard, category allowlist
   422, doc-ownership 404, 5/user/hour 429 via Python-computed UTC cutoff
   so both backends compare plain strings); owner notify via
   `env_or_setting("admin_email")` + `send_feedback_notify`, fail-open
   (notify failure never fails the submit, `emailed` bool in response).
   Reporter text is never forwarded to any model (stated in code + mail).
3. [x] Web (`apps/web`, LF direct): `submitFeedback` in `lib/api.ts`
   (existing `api()` POST shape); `/about` static (what it does, honest
   limits, data handling, legal links, dark app theme like /help - NOT the
   light-theme legal-page classes); `/contact` authed form (RequireSession,
   category/subject/message/doc-id, 10..4000 + ≤120 client-validated,
   sent reference ID, 429 detail surfaced, no-account-numbers warning);
   links from /help ("Something wrong?" section), Review subtitle + empty
   state, Reports blurb, new-page footers. Legal pages untouched.
4. [x] Verify: tsc clean; 6/6 feedback + 18/18 with neighboring
   auth/settings suites (unsandboxed per Learning 44); staged-diff secrets
   scan clean. `docs/API.md` Feedback section appended (via file script -
   PS double-quoted `python -c` ate backticks twice, Learning 85).
5. [x] Deploy: `railway up --service FIN_SPY` + `--service web` from local
   tree (GitHub frozen, no push involved); sandbox blocks Railway/backboard
   net, so runs went through one-time-approval escalation.

## Evidence

- Pre-commit: `tsc --noEmit` exit 0; `pytest tests/test_feedback.py
  tests/test_red_auth.py tests/test_settings.py` 18 passed.
- API live: fresh boot (`Application startup complete`, uvicorn :8080);
  `/health/ready` 200 `{"ready":true,"backend":"pg"}`; `POST
  /v1/feedback` no-auth -> 401 with valid JSON file-body (side-effect
  free; earlier 422s were PowerShell/curl.exe single-quote mangling, not
  product - Learning 86).
- Web live: `/about` 200, `/contact` 200, `/help` 200 on
  web-production-74f81.up.railway.app.
- Contract: `POST /v1/feedback {category, subject, message,
  document_id?, page_url?} -> {id, emailed}`; 401/404/422/429 coded above.

## Open

- Menu/submenu regrouping (proposal delivered, awaiting user pick).
- ADMIN_EMAIL must be set in Railway env for owner notifications,
  else reports persist silently (`emailed: false`).
- Commit not yet made (no commit instruction in the deploy turn).
