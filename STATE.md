# STATE (updated 2026-10-26 - v0.2.0 DB+auth+paystack)

## Working
- Git: 6 commits during hackathon window Oct26 (771812d initial, 1770fe8 scaffold v0.1.0-baseline, 2a49ac6 DB+auth+paystack, 98b069d docs hackathon grade, 28bc951 privacy templates) - now 7 commits with settings UI, origin https://github.com/Lapjan1/FIN_SPY.git branch main, pytest 15 passed (12 + 3 settings), health/ready ok backend sqlite, privacy/terms/refund/ai-disclosure 200, settings admin-only 403 non-admin 200 admin, forbidden secret 400 per docs/SETTINGS.md
- Scaffold: AGENTS.md hard rules front-loaded, README hero flow + Mermaid + Meta model matrix checklist, docs/PLAN,MODULES,FLOWS,UI_SPEC,TROUBLESHOOTING,METHOD_STATEMENT, decisions/0001 fresh build 0002 clearmind adapter, AUTH_PAYSTACK, SETTINGS.md for Meta compliance per tradeoffs, docs/legal/privacy.md terms.md refund.md ai_disclosure.md copying clearmind templates privacy.html POPIA July 5 2026 adapted forensic, .agents/memory index 15+ entries, .claude/hooks.json audit logging, config/models.yaml capabilities routing local-first privacy gate + cost guards
- Monorepo: apps/web Next.js typed api.ts SourceViewer KpiCards + src/app/layout.tsx root + page.tsx hero KPI + privacy/terms/refund/account/settings pages + components/settings/MetaModelSelector.tsx pure Meta models per hackathon guidelines no openai phi4, ollama-local only privacy fallback, freellmapi active badge green + meta_official pending warning yellow per STATE.md Blocked, apps/api FastAPI /v1 health/ready + privacy/terms/refund/ai-disclosure serving real markdown + settings GET admin-only redacted secrets + POST admin-only for non-secret model/effort/trial_pages with forbidden secret check must be env var fail-closed, apps/worker llm/client.py Meta adapter capabilities effort map local-first, parsers/base.py SA amount, spy/detectors.py + debt.py Decimal
- DB+Auth+Paystack+Settings: db.py dual + check_same_thread=False fix, tables + hash-chain, auth.py bcrypt + FastAPI Depends trial pages 20/200/1000 402 exhausted reset token fail-closed, paystack.py timing-safe HMAC SHA512 idempotent, main.py wired
- Tests 15 passed: 6 smoke + 6 DB/auth/paystack + 3 settings admin-only + forbidden secret + privacy terms endpoints
- Secrets audit: .env ignored, data/vault ignored, data/*.db ignored, .env.example present, no .key/.pem, banned imports no FINSPIB/FNBP, CI secret scan + banned import
- Web legal + settings: privacy/terms/refund/account/settings pages Tailwind CDN adapted from clearmind but forensic wording, account shows security improvements over clearmind, settings shows MetaModelSelector + cost guards + env guards REQUIRED fail-closed + privacy gate + forbidden keys via POST 400

## In progress
- Privacy/terms/refund web templates - API placeholders done, need apps/web/src/app/legal pages copying clearmind privacy.html POPIA template
- Frontend auth UI - API has /v1/auth/* + X-User-Id dev header, need Next.js login/register pages that call typed api.ts
- Extraction line-ID grounding v1 wiring - prompts/extract_sa_bank_v1.md versioned + schema ready, need apps/worker/parsers/fnb.py deterministic + LLM fallback + reconciliation gate opening+sum=closing
- Ledger-core dynamic COA seeding + journal posting debits=credits + trial balance live SUMIFS
- Dashboard ECharts PowerBI look + drill-to-bbox pdf.js highlight overlay - components SourceViewer KpiCards exist but not wired to live data
- Reports Excel live formulas + signed PAdES PDF pyHanko + FreeTSA + Evidence Pack ZIP + verify_pack.py independent verifier (script exists but not end-to-end tested)
- KPI + debt spy engine + chat tool calling over DB - debt.py Decimal maths exists but API only mock ordering
- Deployment: ops/docker-compose.yml minimal, need railway.json + render.yaml healthCheckPath /health/ready per ClearFlag pattern, env guard REQUIRED vs OPTIONAL, uptime ping for Supabase free idle-pause

## Broken
- ruff not installed in global python (needs uv sync dev), pyright not run yet, pnpm web lint not run (apps/web package.json exists but node_modules not installed)

## Blocked
- META_API_KEY official muse-spark-1.3/wonder/image still pending 1-2 days from Cerebral Valley. Mitigation active: freellmapi/muse-spark-1.1 dev at http://127.0.0.1:3001/v1 + ollama-local/llama3.2 fallback via config/models.yaml routing local_first_hosted_on_approval privacy_gate show_exact_text_before_hosted true. No Contributor tier for real docs per AGENTS.md.

## Next 3 steps
1. Add ADR 0002 clearmind adapter + docs/AUTH_PAYSTACK.md documenting auth flow, DB schema, paystack webhook timing-safe, trial pages vs clearmind 5 sessions, bcrypt upgrade, hash-chain audit - makes this commit documented hackathon grade
2. Build privacy/terms/refund templates in docs/legal/ and apps/web/src/app/legal/ copying clearmind templates but SA forensic wording from docs/METHOD_STATEMENT.md
3. Implement extraction v1: apps/worker/parsers deterministic FNB parser + LLM fallback line-ID grounding per prompts/extract_sa_bank_v1.md + validation schema + quote exists + reconciliation gate, persist to source_spans/transactions, then wire dashboard drill-to-bbox via /v1/transactions/{id}/sources
