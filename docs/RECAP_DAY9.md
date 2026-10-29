# RECAP Day 9 (part 1) - Real App Live: Landing + Prod Wiring + Auth UX - 2026-10-29

Per docs/TIMELINE.md Day9 (polish + deploy + video + legal). Built this round: mock landing replaced with real copy, web-to-API prod wiring + both services deployed from local via Railway CLI (GitHub still frozen), frontend auth UX (session/nav/paywall) + billing callback fix + deployed again. NOT done: 2-3 min video, Paystack test-key checkout verification, session-token auth hardening (X-User-Id dev auth still in place).

## What We Have Done (Oct29, three slices)

### 1. Landing: mock removed, real copy live
- apps/web/src/app/page.tsx rewritten: removed hardcoded KPI cards (R187/4.5/12.5%), fake SourceViewer (a1b2 sha), hero-flow checklist, architecture block. Now: left-aligned hero, real feature/how-it-works copy, CTAs to working pages, live API status badge (fetches /health/ready), Built-with-Meta + POPIA trust strip.
- Why the mock survived: checklists measured construction (endpoints exist, pytest green), never presentation - no gate said "zero mock data on landing" (learning 40).
- tsc 0, next build green (13 routes, / at 2.63 kB then 3.09 kB after SessionNav).

### 2. Prod wiring + first live deploy from local
- Root cause found: API CORS hardcoded Clearmind's old Railway URL (web-production-ad9d4) - FIN_SPY web could never call it. Fix: `_cors_origins()` in apps/api/main.py (localhost defaults + WEB_ORIGIN env, comma-separated), stale URL deleted (learning 42).
- apps/web/Dockerfile: explicit ARG/ENV NEXT_PUBLIC_API_URL before build (learning 41). .env.example documents both vars. ops/docker-compose.yml web build fixed to repo-root context + build arg (pre-existing context bug).
- tests/test_cors_prod.py (5 tests: defaults, env, comma-list, no-stale-origin, live preflight) - written failing first (AttributeError), green after fix.
- Railway (project sweet-healing, service FIN_SPY + web + Postgres): set WEB_ORIGIN on API + NEXT_PUBLIC_API_URL on web via CLI, `railway up --service` for both (working tree incl. uncommitted, GitHub frozen so no auto-deploy). Verified live: OPTIONS preflight 200 + correct allow-origin, new landing HTML, API URL baked in live JS bundle. 914a9 domain is NOT in this project (learning 45).
- Tooling notes: edit_file cannot match CRLF files - PowerShell byte-exact Replace-Once fallback (learning 43); sandbox blocks tsc/uv/TestClient - verification gates run unsandboxed (learning 44); PS5.1 has no -SkipHttpErrorCheck - curl.exe for preflight (learning 48).

### 3. Frontend auth UX + billing callback fix, deployed again
- apps/web/src/lib/api.ts: session helpers (one finspy-user-id shared by all pages), status-carrying errors + isPaywallError/isAuthError (learning 49), typed register/login/forgot/reset/plans/checkout, tenantIdForEmail (one deterministic tenant per user, learning 46).
- New components/SessionNav.tsx (Trial-n-pages/Pro badge + sign in/out in nav) + components/PaywallNotice.tsx (402 panel with plans). /account rewritten: sign-in/register/forgot/reset tabs, logged-in user card + live plans + Subscribe redirect to Paystack, sign out. /upload shows paywall on 402.
- Backend 1-liner: checkout callback_url carries ?user_id= so require_login accepts the browser redirect (test_billing_callback_url written failing first, green after). APP_BASE_URL set on API service so callbacks use the public domain (learning 47).
- Deployed API dep a01a0665 + web dep 989a3ff1. Smoke live: new /account HTML (4 tabs), plans JSON (R0/R149/R599), /auth/me 401 without creds.
- Known gap (unchanged): X-User-Id dev auth, no session token/JWT - fine for demo/video/SaaS testing with trusted users, must fix before real customers or Paystack live.

## Evidence
- pytest: 11 passed (5 cors + 6 smoke), then 15 passed (callback + red_paystack + red_auth) - unsandboxed (sandbox blocks socketpair).
- tsc --noEmit exit 0 (twice); next build green both rounds, 13/13 routes prerendered.
- Ruff: main.py 24 before = 24 after (HEAD oracle, zero new findings; 17-count in older notes predates Day5-8 growth).
- Live: preflight `HTTP 200 + access-control-allow-origin: https://web-production-74f81.up.railway.app`; bundle contains `let t="https://finspy-production.up.railway.app"`; /health/ready `{"ready":true,"backend":"pg"}`.

## What We Learned
- Learnings 40-49: gate presentation not just construction; NEXT_PUBLIC bakes at build; CORS from env + live preflight proof; CRLF edit fallback; unsandboxed verification gates; local railway-up deploy playbook; per-user tenant from email; callback user_id + public APP_BASE_URL; curl for OPTIONS on PS5.1; status on thrown errors.
- Process: test-first held for both backend changes (cors, callback) - authentic pre-fix failure observed each time before the fix.
