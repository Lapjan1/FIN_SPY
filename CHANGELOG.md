# Changelog

## v0.2.0-db-auth-paystack - 2026-10-26
- DB adapter: apps/api/db.py dual SQLite/Postgres per clearmind pattern is_postgres() _translate ?->%s datetime('now')->LOCALTIMESTAMP INSERT OR REPLACE->ON CONFLICT, WAL+FK, tables tenants/users(paystack cols)/settings/reset_tokens/source_documents content-hash/pages/extraction_runs/source_spans bbox/transactions fingerprint SHA256(date|amount|desc_norm)/transaction_sources/classifications/accounts/journal_entries/lines/flags/audit_log hash-chain prev_hash/row_hash/anchors/reports/subscriptions trial pages/usage_events/webhook_events/partner_profiles
- Auth: bcrypt not SHA256 hex (clearmind weak), FastAPI Depends require_login/require_subscription/require_admin, is_admin allowlist, trial pages free 20 vs clearmind 5 sessions, 402 exhausted, reset token uuid hex 1h expiry, check_session_secret fail-closed like ClearFlag
- Paystack: env_or_setting, has_paystack sk_test|sk_live bugfix, plan mapping free 20 R0 individual 200 R149 sme 1000 R599, timing-safe verify HMAC SHA512 raw body hmac.compare_digest per ClearFlag, initialize/callback/webhook idempotent, upsert subscriptions builds_allowed reset
- API wired: startup init_db() + session secret guard, auth register/login/forgot/reset/me, health/ready, documents upload require_subscription trial check audit_log hash-chain isolation, sources isolation 403 cross-tenant, dashboard trial, reports isolation, billing plans/checkout/callback/webhook, audit read-only, privacy/terms/refund placeholders
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
