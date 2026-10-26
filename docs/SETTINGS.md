# SETTINGS.md - Meta Models Compliance for Hackathon

Per competition rules: Build with Muse Spark series, Wonder, Image, SAM 3.1 via Meta Model API, open-weights via Baseten/Modal, Muse Code. Startup track judged on technical execution + production readiness + effective Meta use.

Clearmind pattern: `settings.html:13-40` ai_provider openai|ollama, model phi4/llama3.2, ollama_url, openai_api_key plaintext. For FIN_SPY, adapt to Meta models now per hackathon guidelines.

## Tradeoffs Confirmed

**OpenAI as optional fallback? Remove entirely to stay pure Meta.**
- Decision: Keep `ollama-local only` as privacy fallback per docs/FLOWS.md Flowchart #2 local-first, remove openai phi4 option to avoid judges confusion.
- Rationale: Judges verify Meta tool use via README Meta model matrix + prompts versioned + git commits during Oct26-Nov4. OpenAI primary would weaken scoring. Ollama-local `llama3.2:latest` stays as privacy fallback when user denies hosted approval gate `show_exact_text_before_hosted=true`.

**Settings UI admin-only vs user-visible?**
- Decision: Admin-only for keys, user-visible read-only for model/effort/cost.
- Clearmind had admin-only exposing keys plaintext `value="{{ openai_api_key }}"` risky. FIN_SPY: admin-only page `apps/web/src/app/settings/page.tsx` checks `require_admin` via `X-User-Id` + role admin or ADMIN_EMAIL allowlist, shows `***REDACTED*** + last 4 chars` for keys, input type password, not value. User-visible read-only component `MetaModelSelector` shows current model, capabilities, cost estimate, effort, no keys.

**META_API_KEY pending?**
- Still waiting 1-2 days Cerebral Valley per STATE.md Blocked. Settings UI shows `freellmapi dev active badge` green + `meta_official pending warning` yellow, like STATE.md Blocked. Once key arrives, swap env var META_API_KEY, no code change - adapter `apps/worker/llm/client.py` reads `config/models.yaml` + env.

## Env Guards (per ClearFlag lib/env-check.js + server.js)

**REQUIRED in production (fail-closed):**
- `SESSION_SECRET` - 32+ chars, never random persisted like clearmind bug `app.py:10` persisted to settings table. `check_session_secret()` in `apps/api/auth.py` raises RuntimeError if missing in prod.
- `DATABASE_URL` - if starts with postgres, use PG backend else SQLite `data/fin_spy.db` per `is_postgres()` clearmind `database.py:6-7`
- `META_API_KEY` - worker only, never browser per AGENTS.md Hard rules, never in `settings` DB table - must be env var

**OPTIONAL (env_or_setting pattern clearmind `app.py:28-29`):**
- `FREELLMAPI_API_KEY`, `FREELLMAPI_BASE_URL=http://127.0.0.1:3001/v1` - dev proxy with 278 models including `muse-spark-1.1`
- `OLLAMA_API_KEY` optional, `OLLAMA_BASE_URL=http://127.0.0.1:11434/v1` - local fallback
- `PAYSTACK_SECRET_KEY` api only, `PAYSTACK_PUBLIC_KEY` web, `PAYSTACK_PLAN_CODES_JSON` per `.env.example`
- `ADMIN_EMAIL` allowlist for is_admin bypass, `APP_BASE_URL` for Paystack callback_url _external like clearmind ProxyFix

**Forbidden in DB:**
- `META_API_KEY`, `PAYSTACK_SECRET_KEY`, `SESSION_SECRET` must be env var, not `settings` table key/value - if attempted via `POST /v1/settings`, reject 400 per security guide hooks outside sandbox.

## Config/models.yaml

Already exists with providers:
- `freellmapi` base_url `http://127.0.0.1:3001/v1` api_key_env `FREELLMAPI_API_KEY` models `spark=muse-spark-1.1` `spark_dev=auto`
- `ollama` base_url `http://127.0.0.1:11434/v1` api_key_env `OLLAMA_API_KEY` optional models `llama_local=llama3.2:latest`
- `meta_official` base_url `https://api.llama.com/compat/v1` api_key_env `META_API_KEY` models `spark=muse-spark-1.3` standard NOT contributor, `spark_contributor=muse-spark-1.3-contributor` ONLY synthetic, `wonder=muse-wonder-1.0`, `image=muse-image-1.0`, `sam=sam-3.1`

Capabilities per model:
- `muse-spark-1.1`: max_context 128k, supports_images true, parallel_tools true, structured_output true, effort low/medium/high
- `muse-spark-1.3`: 1M context, 131k output, effort low/medium/high/xhigh
- `muse-wonder-1.0`: frontier, same
- `sam-3.1`: is_segmentation true
- `llama3.2:latest`: 131k, supports_images false, parallel true

Routing per Flowchart #2:
- `policy: local_first_hosted_on_approval`, `privacy_gate: true`, `show_exact_text_before_hosted: true`, `rate_limit_rpm: 100`, `per_tenant_fairness: true`, `retries: 3`

Cost guards:
- `per_document_token_ceiling 15000`, `per_tenant_pages_per_month free 20 individual 200 sme 1000`, `global_daily_budget_usd 10`, `kill_switch_to_no_ai true`

## Settings UI Design

**Admin page `apps/web/src/app/settings/page.tsx`:**
- Checks `require_admin` via `GET /v1/auth/me` role admin or ADMIN_EMAIL env allowlist, redirects non-admin to `/`
- Badges: `freellmapi dev active` green if `FREELLMAPI_API_KEY` present and `/health` backend sqlite + `has_paystack` false? Actually freellmapi check via `/health` calls freellmapi ping `http://127.0.0.1:3001/api/ping` per local_services.yaml, `meta_official pending warning` yellow if `META_API_KEY` missing - like STATE.md Blocked
- Sections: Provider (radio freellmapi/meta_official/ollama-local), Model selector dropdown from `config/models.yaml` capabilities, Effort low/medium/high/xhigh, URLs (freellmapi_base_url, ollama_base_url, meta_base_url) read-only, Cost guards number inputs per_tenant_pages, global_daily_budget, kill_switch checkbox, Privacy gate checkbox show_exact_text_before_hosted
- Keys section: inputs type password, placeholder `sk-...` or `***REDACTED*** + last4`, never value from API, POST to `/v1/settings` only for non-secret keys (model, effort, trial_pages, ollama_url) - secret keys must be env var, if attempted reject 400.

**User-visible component `apps/web/src/components/settings/MetaModelSelector.tsx`:**
- Read-only, shows current model from `GET /v1/settings` model key, capabilities max_context, supports_images, effort_levels, cost estimate per document $0.045 per 8p, token usage via `usage_events` est_cost_usd, no keys.

**API:**
- `GET /v1/settings` admin-only returns key/value from settings table ORDER BY key, but filters out secret keys like `paystack_secret_key`, `meta_api_key`, `session_secret` - returns redacted.
- `POST /v1/settings` admin-only, body key/value, rejects if key in forbidden list `['meta_api_key','paystack_secret_key','session_secret','paystack_public_key']` must be env, only allows `model, ai_provider, ollama_url, trial_pages, trial_sessions, cost guards, privacy gate`.

## Competition Rules Compliance

- Effective Meta use: README Meta model matrix table Spark 1.3/Wonder/Image/SAM3.1 + adapter `apps/worker/llm/client.py` + `config/models.yaml` + prompts versioned with SHA256 header never embedded in code per AGENTS.md + git commits during Oct26-Nov4 evidence.
- No Contributor for real docs: `muse-spark-1.3-contributor` warning in Settings UI if selected for real tenant - only synthetic test data `data/samples/` per AGENTS.md Known pitfalls, LEARNINGS 2026-10-26-04.
- Privacy gate: local-first per Flowchart #2, show exact text before hosted, user approval, audit_log hash-chain.
- Cost guards per-tenant pages 20/200/1000 vs clearmind 5 sessions, global daily budget alarm, kill switch No-AI.

## Verification

- `uv run pytest -q` 12 passed + new test_settings_admin_only
- TestClient `/privacy /terms /refund /ai-disclosure /health /health/ready` 200, `/settings` 403 non-admin, 200 admin with X-User-Id
- Secrets audit: no env in git, no .key/.pem, banned imports no FINSPIB/FNBP, .env.example names only
- Git commits during window, README Meta usage proof, .agents/memory index updated
