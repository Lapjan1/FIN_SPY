# AGENTS.md - FIN_SPY Forensic Spy

## Hard rules (always, front-loaded)
- Never commit secrets: .env, *.key, *.pem, *_SECRET_*, META_API_KEY. Rotate on any doubt. Check git diff before commit.
- Never print or log secrets, tokens, paths with PII. Redact in screenshots.
- Never force-push, never rewrite published main history. Use `git revert`.
- Never skip failing tests, never edit generated files, vendor, or lock files by hand.
- Show evidence (command output, file:line, SHA256) before claiming done. Do not invent tool results.
- One goal per turn, evidence before synthesis. Cap long chains with checkpoints.
- Break lethal trifecta: Private data + Untrusted PDF + External egress never in same session. Split: Session R (reader, read-only, no secrets, restricted net) outputs reviewed summary. Session W (writer, trusted, secrets allowed) consumes only summary.
- FINSPIB/FNBP code is BANNED import in this repo for hackathon compliance - fresh build only. Reference extractor (25+ bank adaptors) can be READ for design, never copied. All ledger code here is new.
- DB-first: Extract -> persist to .db (SQLite for MVP, Supabase Postgres prod) -> all products read from DB. Never produce report directly from extraction.
- Money: Python Decimal or int cents, never float. Dates stored UTC, display Africa/Johannesburg.
- Muse Code guardrails: approvals ON, sandbox proxy-only, execution_capacity 2-3 on 16GB ARM, no --yolo outside disposable container. Hooks run OUTSIDE sandbox - read every command in .claude/hooks.json.

## Project
FIN_SPY = Financial Surveillance & Peak Insights: upload any SA bank PDF, trace every number to exact bbox on original (SHA256 vault + hash-chain audit), auto-build dynamic books, spy for leaks/subscriptions/duplicates, KPIs + debt snowball/avalanche strategies. Built for Meta Global AI Dev Hackathon (Oct26-Nov4) - startup track, indie creativity + production readiness.

## Commands (exact, copy-pasteable)
- Setup: `uv sync && uv pip install -e . && pnpm --dir apps/web install`
- Run API: `uv run fastapi dev apps/api/main.py --port 8000 --host 127.0.0.1`
- Run Worker: `uv run python -m apps.worker.main --queue sqlite`
- Run Web: `pnpm --dir apps/web dev --port 3000`
- Full Stack (Railway): `railway up` OR `docker compose -f ops/docker-compose.yml up`
- Test: `uv run pytest -q` <- run before every commit
- Lint: `uv run ruff check . && uv run ruff format --check . && pnpm --dir apps/web lint`
- Type: `uv run pyright && pnpm --dir apps/web exec tsc --noEmit`
- Golden: `uv run pytest tests/golden -v` (synthetic SA bank PDFs)
- Verify Evidence Pack: `uv run python scripts/verify_pack.py ./evidence-pack.zip`
- Generate synthetic data: `uv run python scripts/generate_sa_statements.py --banks FNB,STDB,ABSA --out data/samples/`

## Tooling notes
- Python 3.12 + uv (not pip), Node 20 + pnpm (not npm), Windows PowerShell 5.1, 16GB ARM thin client - heavy work on Railway/Supabase, not locally.
- Models in config/models.yaml, not code. Base URLs: FREELLMAPI http://127.0.0.1:3001/v1 (dev, muse-spark-1.1), Ollama http://127.0.0.1:11434/v1 (fallback), Prod META_API_KEY -> https://api.llama.com/compat/v1 (muse-spark-1.3 standard NOT contributor)
- Effort levels: Spark low/medium/high, Glimmer xhigh/high/medium/low. Meta provider rejects 'none'. Map via Capabilities.
- DB: SQLite `data/fin_spy.db` for MVP (fast, single file), Supabase Postgres 500MB free for prod with RLS. Storage: local `data/vault/` content-hash keys for MVP, Supabase Storage prod.

## Conventions that differ
- All tables have tenant_id + RLS/isolation guard. Append-only audit_log with prev_hash/row_hash SHA256(prev||canonical_json).
- Transaction fingerprint = SHA256(date|amount|desc|balance) for dedup.
- Line-ID grounding: LLM gets Lxxx numbered lines + bbox, must return line_ids + source_quote exact match.
- Prompts versioned in prompts/*.md with SHA256 header. Never embed prompt text in code.

## Known pitfalls
- PyMuPDF AGPL license check - fallback to pdfplumber/pypdfium2 for SaaS prod if needed. See LEARNINGS 2026-10-26-01.
- Meta rate limit reported 100 RPM/team - worker has global limiter + per-tenant fairness + retries.
- Supabase free pauses after 1 week idle - uptime ping or upgrade to Pro $25/mo.
- Contributor tier muse-spark-1.3-contributor trains on prompts - NEVER use for real bank docs, only synthetic test data.
- WSL2 bubblewrap needed for Muse sandbox on Linux - fail-closed is correct behavior, don't bypass.

## Never
- Commit .env, secrets, logs/*, vendor/*.whl, models/*.gguf, *.key
- Use float for money, hardcode one COA/company, or import FINSPIB/FNBP code
- Disable sandbox/approvals on laptop, trust unknown repo, auto-import foreign skills/plugins
- Send real customer bank data to hosted model without user approval gate showing exact text

## Read first
- STATE.md (now), LEARNINGS.md (past mistakes), docs/PLAN.md (what to build), docs/MODULES.md (boundaries), docs/FLOWS.md (flowcharts), docs/UI_SPEC.md (screens), docs/decisions/ (ADRs), docs/METHOD_STATEMENT.md (court wording)
- .agents/memory/MEMORY.md index for durable facts
