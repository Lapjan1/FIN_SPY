# Paystack Apply - Spec for FIN_SPY Live Webpage + Disclaimers + Time Needed

Per user question: Paystack wants live webpage, all disclaimers, web address, proof of live URL because integrates in payment system.

## Spec from Paystack Docs Fetched

**API Keys - Instant Test Status:**
- Docs `API Keys`: Every integration has public `pk_test_` + secret `sk_test_` for test mode and `pk_live_` `sk_live_` for live mode. Test keys instant upon signup dashboard.paystack.com - no business verification. Our code `has_paystack()` checks `sk_test|sk_live` bugfix clearmind PROJECT_NOTES.md:52.

**Accept Payments - Go Live Checklist (partial from docs/payments/accept-payments/ + webhooks go-live checklist):**
- Webhook URL must be publicly available (localhost can't receive events) - docs/webhooks go-live checklist: `Add webhook URL on dashboard https://dashboard.paystack.com/v2/developers, Ensure publicly available, trailing slash, test JSON body returning 200 OK, long-running tasks return 200 first, failed attempts retried every 3 mins first 4 tries then hourly 72h live, hourly 10h test timeout 30s`.
- Callback URL: Set `callback_url` in transaction data or on dashboard. Docs: `You can set test callback URLs for test transactions and live callback URLs for live transactions.` Our code `callback_url = APP_BASE_URL + /v1/billing/callback` like clearmind ProxyFix.
- Signature validation: `x-paystack-signature` HMAC SHA512 raw body signed with secret key per docs/webhooks signature validation - our `verify_paystack_signature()` timing-safe `hmac.compare_digest` per ClearFlag `routes/paystack.js`.
- IP whitelist `52.31.139.75, 52.49.173.169, 52.214.14.220`.

**Subscriptions - test mode instant:**
- Docs `Subscriptions`: Create plan via Dashboard `https://dashboard.paystack.com/v2/plans` or API `POST /plan` with `name interval amount` -> returns `plan_code PLN_...`, then create subscription via `plan_code` in transaction initialize or `POST /subscription` customer+plan. Events `subscription.create`, `charge.success`, `invoice.create` 3 days before, `invoice.payment_failed`, `subscription.disable`. Our code `initialize_transaction()` plan_code override, `create_subscription()` customer+plan+authorization, `handle_webhook_event()` active/free.

**Test Payments - instant demo:**
- Docs `Test Payments`: test cards `4084 0840 8408 4081` expiry any future CVV 408 no validation reusable, PIN validation `5078 5078 5078 5078 12`, PIN+OTP `5060 6666 6666 6666 666` OTP 123456 etc. Can demo without live approval.

**Live Account Requirements (not in dev docs, from Paystack support + SA compliance + homework Part 5.13):**
- Business registration SA CIPC, ID, bank account ZAR, business description, website URL live with:
  - Product description what you're selling (FIN_SPY forensic books + spy + KPIs + debt)
  - Pricing Free 20 R0 Individual 200 R149/mo SME 1000 R599/mo Practice custom per docs/decisions/0001
  - Contact info + physical address
  - Privacy Policy `/privacy` POPIA - we have `docs/legal/privacy.md` + web `apps/web/src/app/privacy/page.tsx` adapted from clearmind `privacy.html` July 5 2026: data on Railway isolated by tenant_id, HTTPS, Meta standard no training, retention 30 days legal_hold
  - Terms `/terms` - 20 pages trial auto-renew SA law - we have `terms.md` + page
  - Refund Policy `/refund` - digital immediate access no refund partial exception >48h downtime pro-rata - we have
  - AI disclosure `/ai-disclosure` - we have `ai_disclosure.md` + API `/ai-disclosure`
  - HTTPS (Railway TLS)
- Time: Test status instant, Live approval 1-3 business days SA up to 5 days after KYC docs submit. Homework Part 5.13 `live-mode activation requires business verification that may take days. Plan: build and demo in TEST MODE from Day7; submit KYC on Day1; present live-ready, test-mode demo if approval not done. Show test-card payments in demo video.`

## What FIN_SPY Has Ready for Paystack Application

**Legal pages for live webpage proof:**
- Web: `apps/web/src/app/layout.tsx` RootLayout Tailwind nav privacy/terms/refund/account + `page.tsx` hero KPI leak R187 runway 4.5 + `privacy/page.tsx` `terms/page.tsx` `refund/page.tsx` `account/page.tsx` + `settings/page.tsx` admin-only keys ***REDACTED***+last4 + `components/settings/MetaModelSelector.tsx` pure Meta no openai phi4 freellmapi active badge green + meta pending warning yellow
- Docs: `docs/legal/privacy.md` `terms.md` `refund.md` `ai_disclosure.md` + `METHOD_STATEMENT.md` court wording AI disclosure
- API: `/privacy` `/terms` `/refund` `/ai-disclosure` serve real markdown from `docs/legal/` with source Adapted from clearmind-ai/templates/privacy.html, last_updated, compliance POPIA, storage Railway/Supabase isolated, billing free 20 etc, models list spark 1.3 standard NOT contributor wonder image sam 3.1

**Paystack adapter ready for test demo:**
- `apps/api/paystack.py` `has_paystack()` sk_test|sk_live, `plan_details()` free 20 R0 individual 200 R149 sme 1000 R599, timing-safe `verify_paystack_signature()` HMAC SHA512 raw body `hmac.compare_digest`, `initialize_transaction()` callback_url _external metadata user_id tenant_id plan_code, `verify_transaction()`, `create_subscription()`, `handle_webhook_event()` charge.success/subscription.create -> active free -> active, disable -> free upsert subscriptions builds_allowed reset
- `apps/api/main.py` `/v1/billing/plans` free/individual/sme, `/v1/billing/checkout` plan_code require_login metadata, `/v1/billing/callback` trxref verify, `/v1/webhooks/paystack` raw body timing-safe idempotent `webhook_events` dup True
- Tests 25 red: invalid sig 400, duplicate webhook idempotent, free checkout 200 even without key (fixed free check before has_paystack), unconfigured individual 500/400, verify false empty sig wrong secret
- `.env.example` `PAYSTACK_SECRET_KEY sk_test_...`, `PAYSTACK_PUBLIC_KEY pk_test_...`, `PAYSTACK_PLAN_CODES_JSON {"free":"PLN_xxx"...}`, `APP_BASE_URL`

**Deployment ready for live URL proof:**
- `railway.json` build nixpacks buildCommand pip+pnpm build startCommand uvicorn healthcheckPath `/health/ready` restart always + `ops/railway.json` same + `apps/api/Dockerfile` healthcheck curl -f /health/ready interval 30s + `apps/web/Dockerfile` Next.js builder runner + `ops/docker-compose.yml` healthcheck curl + restart unless-stopped external volumes pattern DeepSH local-stack

**Checklist to apply now:**

1. **Test mode instant (for hackathon demo):**
   - Sign up dashboard.paystack.com - get `sk_test_*` `pk_test_*` instantly
   - Create plans via dashboard `https://dashboard.paystack.com/v2/plans` or API `POST /plan` name Individual interval monthly amount 14900 -> get `PLN_...`, name SME amount 59900
   - Set in Railway env + `.env` `PAYSTACK_SECRET_KEY=sk_test_...`, `PAYSTACK_PUBLIC_KEY=pk_test_...`, `PAYSTACK_PLAN_CODES_JSON={"free":"PLN_free","individual":"PLN_...","sme":"PLN_..."}`
   - Test with card `4084 0840 8408 4081` expiry any future 10/27 CVV 408 per Test Payments page - `POST /v1/billing/checkout?plan_code=individual` with `X-User-Id` -> returns `authorization_url` -> pay with test card -> Paystack sends `charge.success` webhook to your public URL or you call `/v1/billing/callback?trxref=...` verify
   - Demo video can show test-card payment per homework Risk

2. **Live mode 1-3 days (for Paystack to give account, need live webpage):**
   - Deploy API to Railway: `railway login` (OAuth token expired currently `invalid_grant`), `railway link` or `railway init`, `railway up` - uses `railway.json` startCommand uvicorn healthcheckPath /health/ready - get URL `https://fin-spy-production.up.railway.app`
   - Deploy Web to Vercel: `vercel` or import GitHub `Lapjan1/FIN_SPY` root dir `apps/web` build `pnpm build` - get URL `https://fin-spy.vercel.app`
   - Set in Paystack dashboard: webhook URL `https://...railway.app/v1/webhooks/paystack` (trailing slash per checklist) + callback URL `https://...railway.app/v1/billing/callback`, ensure `APP_BASE_URL=https://...railway.app`
   - Ensure live legal pages `https://...vercel.app/privacy`, `/terms`, `/refund`, `/ai-disclosure` + product description pricing contact - we have hero + KPI + pricing in code
   - Submit KYC in Paystack dashboard: business registration, ID, bank account ZAR, business description `FIN_SPY Financial Surveillance & Peak Insights forensic books`, website URL live vercel URL
   - Wait 1-3 business days, check email

**Time needed:**
- Test status: instant - if test plan and API wired we can demo today per your question - YES, we have test plan + API wired, `pytest` 40 passed including paystack red
- Live status: 1-3 days after KYC + live URL proof with all disclaimers legal side

**Evidence in repo:**
- `apps/api/paystack.py` timing-safe per ClearFlag, `main.py` webhook raw body, `docs/AUTH_PAYSTACK.md` env_or_setting pattern, `docs/legal/` POPIA, `railway.json` healthcheckPath, `ops/docker-compose.yml` healthcheck, `docs/SETTINGS.md` tradeoffs pure Meta, `apps/web/src/app/settings/page.tsx` admin-only keys redacted

**Next for live:**
- Run `railway login` then `railway link` then `railway up` for API + `vercel` for web, set env vars, create plans, set webhook URL, submit KYC
