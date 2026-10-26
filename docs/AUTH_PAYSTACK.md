# AUTH + PAYSTACK - Clearmind Pattern Adapted

## DB Adapter (apps/api/db.py)

**Pattern:** clearmind-ai/database.py:6-7 `is_postgres()` checks DATABASE_URL, dual SQLite/Postgres, `DbHandle._translate()` per `database.py:74-87`.

**Translation:**
- `?` -> `%s` for PG
- `datetime('now')` -> `LOCALTIMESTAMP`, `date('now')` -> `CURRENT_DATE`
- `INTEGER PRIMARY KEY AUTOINCREMENT` -> `SERIAL PRIMARY KEY`
- `INSERT OR REPLACE INTO table (cols) VALUES` -> `INSERT ... ON CONFLICT (pk) DO UPDATE SET ...` per regex

**SQLite specifics:** `PRAGMA journal_mode=WAL` + `foreign_keys=ON` for concurrency per clearmind.

**Tables vs clearmind:**
- clearmind: users(email,password_hash paystack cols), clients(user_id), sessions, progress_markers, share_links, intakes, settings, reset_tokens, feedback, partner_profiles
- FIN_SPY: tenants, users(tenant_id + paystack cols + referred_by partner_demo), settings, reset_tokens, source_documents(sha256 content-hash vault), pages, extraction_runs(model_id,prompt_sha256,raw_output hash,reconciliation), source_spans(line_id,bbox,text_hash), transactions(fingerprint SHA256(date|amount|desc_norm)), transaction_sources, classifications, accounts, journal_entries/lines debits=credits, flags F-001..F-050, **audit_log hash-chain** prev_hash/row_hash SHA256(prev||canonical_json) append-only per AGENTS.md, anchors TSA, reports, subscriptions trial pages builds_allowed/builds_used, usage_events, webhook_events idempotent, partner_profiles

**Isolation:** Every row tenant_id, app-level filter `WHERE tenant_id=?` like clearmind `WHERE user_id=?`, plus RLS path Supabase prod, test `test_user_isolation` asserts cross-tenant denied.

**Hash-chain helpers:**
```python
compute_row_hash(prev_hash, canonical_json) = SHA256(prev||canonical_json)
get_last_audit_hash(tenant_id) = SELECT row_hash ORDER BY id DESC LIMIT 1 or 0*64
append_audit_log(tenant_id, actor_id, action, object_type, object_id, payload) = inserts with prev/row_hash
```

## Auth (apps/api/auth.py)

**Clearmind pattern:** `app.py:152-172` @require_login checks session['user_id'] redirect, @require_subscription checks is_admin bypass else get_trial_remaining() None if active else max_trial(5) - COUNT sessions.

**FIN_SPY upgrade:**
- **bcrypt not SHA256**: clearmind `database.py:308` `hashlib.sha256(password.encode()).hexdigest()` no salt -> FIN_SPY `bcrypt.hashpw(pw[:72], gensalt())` $2b$ 60 chars, verify with `bcrypt.checkpw`, legacy SHA256 fallback for migration, test `test_bcrypt_not_sha256` asserts $2b$ not 64 hex.
- **FastAPI Depends**: `require_login(request)` returns user_id or 401, checks Bearer token numeric dev or X-User-Id header or query param user_id for local dev (prod should JWT). `require_admin` checks role admin or ADMIN_EMAIL allowlist per clearmind `app.py:56-61`.
- **Trial pages**: `get_document_count(user_id)` counts source_documents uploaded_by, `get_trial_pages_remaining()` max_trial 20 from settings trial_pages default 20 (not trial_sessions 5), returns None if subscription_status active/trialing else max - used, `require_subscription` raises 402 Trial exhausted vs 302 redirect.
- **Reset token**: uuid4 hex +1h expiry like clearmind `database.py:335-347`, verify expires_at>now and used=0, `use_reset_token` sets used=1, audit log append.
- **Session secret**: `check_session_secret()` fail-closed REQUIRED in production like ClearFlag `server.js` env-check, not random persisted like clearmind `app.py:10` bug where FLASK_SECRET generated and saved to settings table.

**Routes in main.py:** `/v1/auth/register` tenant creation, `/v1/auth/login` returns id for X-User-Id dev header, `/v1/auth/forgot` returns reset_token in dev (prod emailed), `/v1/auth/reset`, `/v1/auth/me` with trial remaining.

## Paystack (apps/api/paystack.py)

**Clearmind pattern:** `app.py:63-71` `get_paystack_sk/pk/plan()` env_or_setting, `has_paystack()` sk_test|sk_live bugfix PROJECT_NOTES.md:52, `database.py:114-116` paystack_customer_code cols via ALTER, `app.py:253-281` /subscribe initialize amount 37000 ZAR callback_url _external, `app.py:283-326` callback verify transaction reference then create subscription, `app.py:328-360` webhook charge.success subscription.create -> active, deactivated -> free.

**FIN_SPY adaptation:**
- Plans: `free 20 R0, individual 200 R149, sme 1000 R599` vs clearmind single R370, mapping `get_paystack_plans()` parses PAYSTACK_PLAN_CODES_JSON env JSON, `plan_key_from_paystack_code` like ClearFlag `lib/plans.js`.
- `plan_details(plan_code)` returns name pages amount_minor price_display.
- **Timing-safe verify**: `verify_paystack_signature(payload bytes, signature, secret)` HMAC SHA512 raw body `hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()` + `hmac.compare_digest` constant time per ClearFlag `routes/paystack.js` verifyPaystackSignature, not plain ==.
- `initialize_transaction(email, plan_code, callback_url, user_id, tenant_id)` metadata user_id tenant_id plan_code, amount from plan_details, plan from plans JSON, like clearmind /subscribe.
- `verify_transaction(reference)` GET verify.
- `create_subscription(customer_code, plan_code, authorization_code)` POST subscription.
- `handle_webhook_event(event_type, event_data)` handles charge.success subscription.create invoice.success -> active upsert subscriptions builds_allowed reset, disable/failed -> free, like ClearFlag upsertSubscription + clearmind deactivation.
- **Idempotency**: `webhook_events` table stores event_id signature_ok payload_json, duplicate insert caught -> return dup true.
- **Env guard**: `has_paystack()` checks sk_test|sk_live, secret key only in api (worker not needed), never in browser per AGENTS.md.

**Routes in main.py:**
- `GET /v1/billing/plans` returns free/individual/sme
- `POST /v1/billing/checkout` plan_code, require_login, builds callback_url from APP_BASE_URL, calls initialize_transaction, returns authorization_url
- `GET /v1/billing/callback` trxref/reference verify, update users paystack_customer_code authorization_code subscription_status active
- `POST /v1/webhooks/paystack` reads raw body, verifies timing-safe, stores webhook_events idempotent, calls handle_webhook_event

## Privacy/Legal (TODO next)

Clearmind `templates/privacy.html:27-37` POPIA: data on Railway isolated by user_id, HTTPS, OpenAI no training, deletion 30 days, last updated July 5 2026. Terms 5 sessions R370, refund no partial. FIN_SPY needs same structure but forensic wording from docs/METHOD_STATEMENT.md: SHA256 vault immutable, tenant_id+user_id isolation, HTTPS, Meta standard tier no training, retention 5y tax 7y company [VERIFY], legal hold flag, deletion certificate.

## Deployment

Clearmind `Procfile` gunicorn, `PROJECT_NOTES.md:7` https://web-production-ad9d4.up.railway.app/, ProxyFix for HTTPS callbacks, no explicit /health, tunnel health loop `start_tunneled.py`. ClearFlag `render.yaml` healthCheckPath /health + `server.js` boot guards REQUIRED env fail-closed.

FIN_SPY: `ops/docker-compose.yml` minimal, need `railway.json` healthcheckPath /health/ready, env guard REQUIRED SESSION_SECRET in prod, uptime ping for Supabase free idle-pause.

## Tests

`tests/test_db_auth_paystack.py`: db dual init, hash-chain prev chain, bcrypt $2b$, isolation tenant-a/b, timing-safe, trial pages 20->15->None.

Run: `uv run pytest -q` 12 passed.
