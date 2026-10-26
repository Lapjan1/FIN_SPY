# Changelog

## v0.3.0-privacy-templates - 2026-10-26
- Docs/legal: privacy.md terms.md refund.md ai_disclosure.md copying POPIA from clearmind-ai/templates/privacy.html July 5 2026 adapted forensic - SHA256 vault immutable tenant_id+user_id isolation, HTTPS, Meta standard tier no training contributor only synthetic, retention 30 days legal_hold flag, free 20 pages R0 individual 200 R149 sme 1000 R599 vs clearmind 5 sessions R370, pro-rata refund >48h downtime
- Web: apps/web/src/app/layout.tsx RootLayout Tailwind nav privacy/terms/refund/account + page.tsx hero KPI leak R187 runway 4.5 + SourceViewer bbox highlight signature demo + architecture DB-first Mermaid, apps/web/src/app/privacy/page.tsx terms/page.tsx refund/page.tsx account/page.tsx adapted from clearmind privacy.html but forensic wording docs/METHOD_STATEMENT.md + docs/legal/*.md, footer privacy terms refund
- API: /privacy /terms /refund /ai-disclosure now serve real markdown from docs/legal/ with source Adapted from clearmind-ai/templates/privacy.html, last_updated 2026-10-26, compliance POPIA, storage Railway/Supabase isolated tenant_id+user_id, ai_disclosure Meta standard no training, retention 30 days legal_hold, billing free 20 etc, law SA, models list spark 1.3 standard NOT contributor wonder image sam 3.1 prompts_versioned hash anti_hallucination line-ID grounding
- Ops: railway.json build builder nixpacks buildCommand pip+pnpm build startCommand uvicorn healthcheckPath /health/ready restartPolicy always, ops/railway.json same, ops/docker-compose.yml healthcheck curl -f /health/ready interval 30s restart unless-stopped external volumes pattern DeepSH local-stack, check_same_thread=False fix for SQLite TestClient multi-thread per clearmind threading issue
- Tests: 12 passed + TestClient /privacy /terms /refund /ai-disclosure /health /health/ready all 200, ready previously failed thread id fixed

## v0.2.0-db-auth-paystack - 2026-10-26
- DB adapter: apps/api/db.py dual SQLite/Postgres per clearmind pattern is_postgres() _translate ?->%s datetime('now')->LOCALTIMESTAMP INSERT OR REPLACE->ON CONFLICT, WAL+FK, check_same_thread=False for TestClient, tables tenants/users(paystack cols)/settings/reset_tokens/source_documents content-hash/pages/extraction_runs/source_spans bbox/transactions fingerprint SHA256(date|amount|desc_norm)/transaction_sources/classifications/accounts/journal_entries/lines/flags/audit_log hash-chain prev_hash/row_hash/anchors/reports/subscriptions trial pages/usage_events/webhook_events/partner_profiles
- Auth: bcrypt not SHA256 hex (clearmind weak), FastAPI Depends require_login/require_subscription/require_admin, is_admin allowlist, trial pages free 20 vs clearmind 5 sessions, 402 exhausted, reset token uuid hex 1h expiry, check_session_secret fail-closed like ClearFlag
- Paystack: env_or_setting, has_paystack sk_test|sk_live bugfix, plan mapping free 20 R0 individual 200 R149 sme 1000 R599, timing-safe verify HMAC SHA512 raw body hmac.compare_digest per ClearFlag, initialize/callback/webhook idempotent, upsert subscriptions builds_allowed reset
- API wired: startup init_db() + session secret guard, auth register/login/forgot/reset/me, health/ready backend+has_paystack, documents upload require_subscription trial check audit_log hash-chain isolation tenant_id, list filter tenant, sources isolation 403 cross-tenant, dashboard trial remaining, reports isolation, billing plans/checkout/callback/webhook raw body timing-safe idempotent, audit read-only, privacy/terms/refund placeholders API
- Tests 12 passed: hash-chain, bcrypt $2b$, isolation tenant-a/b, timing-safe, trial pages 20->15->None unlimited
- Stack: passlib[bcrypt] bcrypt psycopg2-binary requests added, .env.example PAYSTACK_PLAN_CODES_JSON etc

## v0.1.0-baseline - 2026-10-26
- Fresh scaffold for Meta Global AI Dev Hackathon
- Monorepo: apps/web (Next.js+Tailwind+shadcn+ECharts), apps/api (FastAPI), apps/worker (Muse Spark)
- DB-first: SQLite vault content-hash + Postgres RLS path
- Forensic layer: SHA256 vault, hash-chain audit_log, line-ID grounding
- Spy layer: subscription/duplicate/fee/anomaly detectors + KPI engine + debt snowball/avalanche
- Stack: Python 3.12 uv, Node 20 pnpm, Meta models via adapter (freellmapi dev, llama.com prod)
- Docs: PLAN 7 tasks, MODULES 12 cards + Mermaid, FLOWS main+agent loop+router+verification, UI_SPEC 6 screens PowerBI look, TROUBLESHOOTING, METHOD_STATEMENT court wording + AI disclosure, decisions/0001 fresh build lean MVP
- Prompts versioned with hash header, schemas Appendix B/C, scripts verify_pack + generate_sa_statements FNB/STDB/ABSA synthetic, tests smoke + fakes FakeModelClient, CI secret scan + banned import
- Git: 771812d initial, 1770fe8 scaffold, commits during Oct26-Nov4 window
