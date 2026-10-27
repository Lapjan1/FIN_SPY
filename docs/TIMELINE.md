# TIMELINE.md - 10-Day Plan for FIN_SPY (Oct26-Nov4) - Stay true to planning per user

Based on homework Part 8 + previous agent plan + Clearmind pattern.

## Day 1 - Oct 26 (Kickoff) - Baseline
- Watch kickoff livestream, accept Official Rules, confirm Startup track "Build for Your World"
- Verify scaffold: `uv sync`, `pnpm --dir apps/web install`, `uv run pytest -q` 12 passed, generate synthetic PDFs `scripts/generate_sa_statements.py --banks FNB,STDB,ABSA`
- Git v0.1.0-baseline, chase META_API_KEY $150 credits (freellmapi dev fallback)

## Day 2 - Oct 27 - Intake + Vault + Worker Skeleton + Auth + Email Note
- `apps/api` upload `POST /v1/documents` SHA256 content-hash vault `data/vault/` + timestamp token -> queue Procrastinate SQLite -> worker text+bbox extraction -> reconciliation gate
- **Auth + Email Note (user question): Do we need mailback service/no-reply mail for login? YES for production grade - add Resend free tier per homework Part 5.14 + clearmind SMTP**
  - Clearmind `app.py:31-54` `send_email()` SMTP_HOST/PORT/USER/PASS/FROM via `smtplib.SMTP` starttls, timeout 10s, welcome email `app.py:185-191`, reset link `forgot_password.html:10-14` shows link openly (security leak), should use email
  - FIN_SPY needs no-reply mail for: welcome email on register, reset password link (uuid hex +1h expiry per `database.py:335-347`), subscription notifications (payment_failed, renewal), forensic flag alerts (optional stretch)
  - For hackathon demo, can return reset_token directly in API response like clearmind did (dev mode), but for production grade Startup track, implement Resend `EMAIL_API_KEY` env worker only, never browser, `apps/api/email.py` abstraction `send_email(to, subject, body)` with fallback to log if no key, templates `emails/welcome.html`, `reset.html`, `payment_failed.html`
  - Add to planning Day2: create email service abstraction, add `EMAIL_API_KEY` to `.env.example`, Railway env, test with Resend test domain `onboarding@resend.dev` -> your email, no-reply address `noreply@fin-spy.example`
  - Note for Day9 polish: legal pages need contact email `admin@fin-spy.example` + no-reply for transactional

## Day 3 - Oct 28 - Extraction Quality
- Wire Meta adapter dev base URL freellmapi:3001 dev muse-spark-1.1 low effort, line-ID grounding prompts `prompts/extract_sa_bank_v1.md`, spans page/bbox/line_id/text_hash, fingerprint dedup, validate quote exists + line IDs exist, all lines accounted or noise
- Validate `pytest tests/golden -v` >=99% digital accuracy, 100% reconcile pass

## Day 4 - Oct 29 - Books + Review UX + Private/Business
- Dynamic per-tenant COA no hardcoded, private/business/mixed classification rules-first AI-second human-last + merchant memory, journal entries trial balance, tenant isolation tests RLS
- Review queue UI accept/edit with reason creates revision append-only

## Day 5 - Oct 30 - Spy + KPI + Debt
- Spy engine subscriptions duplicates F-010 fee Benford F-020 leak score R/mo, KPIs runway burn savings debt-to-income, debt module snowball vs avalanche Decimal what-if
- Validate R45k/R20k/R10k debt fixture ordering

## Day 6 - Oct 31 - Dashboard + Drill + Chat + Settings UI for Meta Models
- Next.js screens per `docs/UI_SPEC.md` KPI cards waterfall treemap heatmap subscription radar, ECharts cross-filter, drill transaction -> grid -> pdf.js bbox highlight via `/v1/transactions/{id}/sources`, Spark tool-calling chat over DB
- Settings UI for Meta models per competition rules: admin-only keys ***REDACTED***+last4, user-visible read-only model/effort/cost, pure Meta no openai phi4 ollama-local only privacy fallback, freellmapi active badge green + meta pending warning yellow, cost guards per-tenant pages 20/200/1000 global daily budget 10 kill_switch No-AI, docs/SETTINGS.md

## Day 7 - Nov 1 - Exports + Billing + Email Service Implementation
- Excel live SUMIFS trial balance + star-schema, signed PAdES PDF + RFC3161 TSA pyHanko, Evidence Pack ZIP + `scripts/verify_pack.py`
- **Paystack test-mode billing + Email Service Implementation:**
  - Paystack initialize transaction from backend never expose secret key in frontend per `accept-payments` docs, callback_url test/live separate, verify via webhook or verify endpoint data.status + data.amount, webhook must be publicly available localhost can't receive events per go-live checklist, signature HMAC SHA512 raw body x-paystack-signature, IP whitelist
  - Email service Resend free tier: `POST https://api.resend.com/emails` with `EMAIL_API_KEY` env, from `noreply@fin-spy.example`, to user email, subject welcome/reset/payment_failed, body with reset link `APP_BASE_URL/reset?token=...` or `https://finspy-production.up.railway.app/reset?token=...`
  - Test mode instant sk_test, live 1-3 days after KYC + live URL proof privacy/terms/refund/AI disclosure, product description pricing contact, HTTPS - we have `https://finspy-production.up.railway.app` ACTIVE + `https://fin-spy-web-production.up.railway.app` building

## Day 8 - Nov 2 - Meta Depth + Wow + Harden + Uptime Ping
- Wonder second-opinion low-confidence extractions, Muse Image finance-health poster, SAM 3.1 receipt image -> masks -> OCR flow, Paystack test-mode billing already done
- Harden: 100 RPM global limiter + fairness + no-double-charge retries, full gate ruff check format --check pyright tsc --noEmit pnpm lint golden, uptime ping Cron `*/5 * * * *` to `/health/ready` every 5 min per user note sleep after given time - Railway free tier sleeps, GitHub Actions `.github/workflows/uptime.yml` + UptimeRobot/Better Stack free tier

## Day 9 - Nov 3 - Polish + Deploy + Video + Legal
- Deploy API/worker Railway + web Vercel + Supabase Postgres/Storage prod RLS, code freeze, record 2-3 min video per README hero flow: problem pile PDFs no proof -> upload 3 statements hash+timestamp -> extraction line-ID grounding + reconciliation gate one failure fixed -> private vs business AI rationale mixed split merchant memory -> dashboard click bar grid PDF highlight -> forensic flags duplicate Benford + Leak Score -> KPI peek runway burn savings + debt snowball vs avalanche -> Generate Excel + signed PDF + Evidence Pack verify_pack.py green -> billing test-mode Paystack + Built with Meta Muse Spark/Wonder/Image/SAM3.1
- Legal: privacy/terms/refund web templates `apps/web/src/app/privacy/page.tsx` etc copying clearmind `privacy.html` POPIA July 5 2026 adapted forensic + API `/privacy` real markdown

## Day 10 - Nov 4 - Submit
- Re-run verify pack on deployed build, README Meta-usage proof, .env.example clean, git diff secrets check, live demo smoke test, submit by 12:00 SAST buffer hard cutoff 9:00 PM ET

## Email Service Note for Relevant Day (User Question)

**Do we need mailback service/no-reply mail for login? YES - Day2 auth + Day7 billing.**

- For hackathon demo, can mock email by returning reset_token directly in `/v1/auth/forgot` response like clearmind `forgot_password.html:10` shows link openly - we do this now `reset_token` in JSON note "In prod, this is emailed, not returned. Dev mode returns for testing."
- For production grade Startup track, need Resend free tier:
  - Env: `EMAIL_API_KEY` (Resend API key) worker only, `EMAIL_FROM=noreply@fin-spy.example`, `SMTP_HOST` etc fallback clearmind pattern
  - Service: `apps/api/email.py` `send_email(to, subject, body, html=None)` tries Resend API `POST https://api.resend.com/emails` with Bearer key, if no key logs to console + audit_log, never exposes key in browser
  - Templates: `emails/welcome.html` welcome + get started link `APP_BASE_URL`, `reset.html` reset link `APP_BASE_URL/reset?token=...` 1h expiry, `payment_failed.html` dunning 7 days read-only
  - Routes: `/v1/auth/register` after create_user sends welcome email via Resend if EMAIL_API_KEY set else logs, `/v1/auth/forgot` creates token + sends email with reset link, not returns token in prod (dev returns for testing), `/v1/billing/webhook` on `invoice.payment_failed` sends payment failed email
  - No-reply: from `noreply@fin-spy.example`, reply-to `support@fin-spy.example`, footer unsubscribe optional
  - Privacy: email contains personal info, log redacted, never log body with token in production logs per AGENTS.md Never print secrets

**Time needed:** Resend free tier setup 10 min, domain verification for fin-spy.example optional, test domain `onboarding@resend.dev` works to your email instantly. For Paystack application, need contact email `admin@fin-spy.example` + no-reply for transactional.

**Planning Day:** Day2 auth (welcome + reset) + Day7 billing (payment_failed renewal) + Day9 polish (legal contact email). Add to STATE.md Next 3 steps after privacy templates: implement email service abstraction with Resend.

**Evidence for hackathon:** Show email sending in logs for demo, or mock with console log + audit_log entry `auth.email.sent` with hash-chain, not token content.
