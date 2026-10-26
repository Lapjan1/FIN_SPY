# 0002 Clearmind Adapter for DB+Auth+Paystack - Date: 2026-10-26 Status: accepted

Context: Previous project clearmind-ai has working login DB + privacy data in Railway DB + Paystack + LLM model integration. FIN_SPY needs same but with forensic enhancements: bcrypt not SHA256, hash-chain audit_log, tenant_id isolation, trial pages not sessions, timing-safe paystack webhook, FastAPI not Flask, Meta adapter local-first privacy gate.

Options considered:
A. Copy clearmind-ai Flask app directly - fast but weak SHA256, fail-open secret persisted, timing attack, Flask not FastAPI, sessions metering not pages.
B. Build from scratch ignoring clearmind - more work, loses proven Railway dual SQLite/Postgres pattern, paystack initialize/verify flow, trial gating.
C. Adapt clearmind pattern but upgrade security + forensic per homework: keep dual DB is_postgres() _translate ?->%s WAL+FK, require_login/require_subscription as FastAPI Depends, bcrypt passlib, hash-chain audit_log prev_hash/row_hash SHA256(prev||canonical_json), tenant_id isolation + RLS guard, trial pages 20/200/1000, paystack timing-safe HMAC SHA512 raw body + idempotent webhook_events, env_or_setting override, check_session_secret fail-closed.

Decision: C

Implementation details (file:line evidence):
- DB: `clearmind-ai/database.py:6-7` is_postgres() check DATABASE_URL, `database.py:74-87` _translate, `database.py:103-205` tables users/clients/sessions etc, `database.py:210-212` paystack cols ALTER, `database.py:566-573` get_trial_remaining -> adapted to `apps/api/db.py` dual support + all forensic tables per Appendix A + hash-chain helpers `compute_row_hash` + `append_audit_log`
- Auth: `clearmind-ai/app.py:152-172` require_login/require_subscription + `database.py:308` SHA256 weak + `app.py:10` FLASK_SECRET env>DB>random -> upgraded to `apps/api/auth.py` bcrypt $2b$, FastAPI Depends, get_trial_pages_remaining free 20, 402 trial exhausted, reset token uuid hex 1h expiry used flag, check_session_secret fail-closed like ClearFlag `server.js` env-check
- Paystack: `clearmind-ai/app.py:63-71` has_paystack sk_test|sk_live bugfix PROJECT_NOTES.md:52, `app.py:253-281` initialize 37000 ZAR, `app.py:283-326` callback verify, `app.py:328-360` webhook charge.success -> adapted to `apps/api/paystack.py` plan mapping free 20 R0 individual 200 R149 sme 1000 R599, timing-safe verify `hmac.compare_digest` SHA512 raw body per ClearFlag `routes/paystack.js`, upsert subscriptions builds_allowed reset on renewal, idempotent webhook_events
- LLM: clearmind `query_ai()` dispatcher ai_provider openai|ollama, model setting -> FIN_SPY keeps more advanced `apps/worker/llm/client.py` Meta adapter capabilities effort map local-first router privacy gate show_exact_text_before_hosted true per Flowchart #2

Consequences:
+ Reuses proven Railway dual DB + paystack flow + trial gating + POPIA privacy template, but upgrades security: bcrypt not SHA256, fail-closed secret, timing-safe webhook, hash-chain audit per AGENTS.md, tenant_id isolation tests
+ Tests: test_db_dual_init, test_hash_chain, test_bcrypt_not_sha256, test_user_isolation, test_paystack_timing_safe, test_trial_pages - 12 passed
+ Hackathon grade: documents what was built before (clearmind) vs during (FIN_SPY) per Meta judging what was built by meta and what was built before/elsewhere - no code copy, only pattern read, fresh implementation
- Need to create privacy/terms/refund web templates copying structure of clearmind `templates/privacy.html` but SA forensic wording from docs/METHOD_STATEMENT.md, need frontend auth UI
- Need to add railway.json healthCheckPath /health/ready per ClearFlag pattern

Verification:
- `uv run pytest -q` 12 passed
- Secrets audit: git check-ignore .env, data/vault/, data/*.db, no .key/.pem, banned imports no FINSPIB/FNBP
- Git commits during hackathon window: 771812d,1770fe8,2a49ac6
