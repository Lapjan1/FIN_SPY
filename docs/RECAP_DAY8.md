# RECAP Day 8 - Meta Depth + Harden + Uptime - 2026-10-28

Per docs/TIMELINE.md Day8: Wonder second-opinion, Muse Image poster, SAM receipt flow, 100 RPM limiter + fairness + retries, full gates, uptime cron. Built this round except Wonder second-opinion extraction hookup (stretch, endpoints exist).

## What We Have Done (Oct28 - Day 8, three slices)

### 1. Rate limiting: 100 RPM + fairness + retries (zero credit burn)
- apps/worker/llm/ratelimit.py: `TokenBucketLimiter` (RPM from META_RATE_LIMIT_RPM, default 100) with per-tenant fairness via last-served rotation; `with_retries` exponential backoff for 429/5xx/timeout/connection only, non-retryable raises immediately (no-double-charge); MAX_WAIT_S fallback returns a deterministic-fallback ModelResult instead of blocking forever.
- Wired at the single choke point: `MetaClient.complete(..., tenant_id)` in apps/worker/llm/client.py acquires + retries. `tenant_id` threaded through `extract_document` -> `llm_fallback`, worker `process_one_document`, and chat `_live_model_answer`.
- 8 tests (tests/test_ratelimit_day8.py): bucket refill, fairness rotation, retry-then-succeed, non-retryable fast-fail, exhaustion re-raise, MAX_WAIT fallback shape, tenant threading, env RPM override. All hermetic (injected clock/sleep, no network).

### 2. Wonder/SAM integration (endpoints wired, fail-closed, no credit)
- apps/worker/llm/image.py: `generate_image` (OpenAI-compatible images endpoint, freellmapi dev proxy default) + `segment_image` (self-hosted SAM service POST, masks+scores). Both refuse with 422 unless explicitly configured - no silent localhost calls, no keyless credit burn.
- `POST /v1/images/generate` + `POST /v1/images/segment` in apps/api/main.py, 401-guarded like all /v1 routes.
- 5 tests (tests/test_image_day8.py): 422 unconfigured for both, shape of mocked generate, SAM masks passthrough, invalid-b64 422. Fixed during the round: `_image_client` consulted no guard (connection-refused to :3001 in tests) -> now consults `image_configured()`; `requests` moved to top-level import.
- NOT done: Wonder second-opinion hookup into low-confidence extractions - deferred to Day 9 polish (stretch).

### 3. Full gates + uptime cron + one real bug fix
- Ruff: new files all clean; full-tree baseline recorded (175 pre-existing: 74 F401, 33 F841, 24 E722, 17 C901, ...); the single F821 was a REAL bug - `apps/worker/main.py:48` passed undefined `tenant` instead of `tenant_id` (NameError on every worker extraction, masked by bare `except Exception` -> ("exception", None) which the e2e test accepted). Fixed + F821 gate now green.
- Pyright 1.1.414: 0 errors on new modules (fixed one real `raise Optional` narrow with assert in `with_retries`); tsc --noEmit exit 0; golden suite green inside the 178.
- Uptime: `.github/workflows/uptime.yml` schedule `*/5 * * * *` re-enabled (was commented while GitHub frozen) - dormant until the account is restored, UptimeRobot covers the gap per the file comment.

## Evidence
- `python -m pytest -q -p no:cacheprovider` 178 passed 0 failed (165 + 8 ratelimit + 5 image), unblocked shell.
- `uvx ruff check` clean on all Day-8 files; `--select F821` All checks passed after the worker fix.
- `python -m pyright <ratelimit.py> <image.py>` 0 errors, 0 warnings; `pnpm --dir apps/web exec tsc --noEmit` exit 0.
- No live model calls made this round (all LLM/image tests mocked or 422-path); credit untouched.

## What We Learned
- Learnings 37-39: bare-except + permissive assert masks NameErrors (gate F821 in CI); image/LLM clients must consult their configured() guard before touching the network; pyright `raise Optional` needs an assert, not a pragma comment.
- Ruff full-tree baselines beat fix-the-world: record counts per rule, fix only the correctness-grade finding (F821), keep new code clean.
