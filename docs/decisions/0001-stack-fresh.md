# 0001 Fresh Build Stack - Date: 2026-10-26 Status: accepted

Context: Previous FINSPIB had one hardcoded company COA, same output for any input, no GUI, not competition wow, pre-existing code penalized by Meta judging what was built before vs during hackathon. We have reference extractor 25+ adaptors but BANNED import for hackathon compliance. Need dynamic multi-tenant books + spy + KPI + debt strategies + wow dashboard in 10 days solo as team startup track. Homework docs recommend full forensic SaaS but need lean path.

Options considered:
A. Reuse FINSPIB wheel: fast but hardcoded, still spits same COA, not dynamic, violates FINSPIB ban rule in AGENTS.md, judges see old commits.
B. Full SaaS per homework Part 5 (Supabase+Railway+Paystack+PyMuPDF+Spark+ReportLab+pyHanko+TSA+Sentry+Resend): complete but heavy for solo 10 days, risks 16GB RAM overload.
C. Lean fresh MVP: SQLite vault content-hash + hash-chain audit_log (from homework) -> later migrate to Supabase, Next.js+FastAPI monorepo, Meta adapter local-first (freellmapi:3001 dev 1.1, ollama fallback, official 1.3 prod), deterministic parsers 3 SA banks + LLM fallback line-ID grounded, dynamic COA generic SA seed + merchant memory per tenant, double-entry ledger, classify private/business/mixed, spy detectors rule-first + AI explain, KPI engine (runway/burn/savings/debt-to-income), debt snowball/avalanche pure Decimal maths + Spark narrative, dashboard ECharts PowerBI look + pdf.js highlight, reports Excel live formulas + signed PDF + Evidence Pack ZIP + verify script, billing mocked test-mode Paystack if time else skip.

Decision: C Lean fresh MVP DB-first architecture. Reasons:
- Extract -> persist to .db -> all products read DB is more reliable than extract->report direct (user's question)
- SQLite single file fast, no Docker Desktop RAM pressure, single file backup, migrate to Supabase Pro $25/mo later for RLS prod story.
- Next.js + FastAPI fastest zero-config for hackathon per Railway docs, pnpm + uv exact commands.
- Meta models isolated in one client module, prompts versioned files, schemas JSON validated at boundaries, router shows exact text before hosted call (privacy gate).
- Reference extractor design can be READ for adaptors pattern, not copied, build new line-ID grounding v1 from scratch for compliance.

Consequences:
+ Builds during hackathon window -> commits Oct26-Nov4 prove Meta build
+ Dynamic, not hardcoded, passes isolation tests
+ Wow demo: click number -> grid -> PDF bbox highlight + Leak Score + debt plan + signed pack verification
+ Easier to test: golden tests on synthetic PDFs 99% accuracy target, verifier independent
- Need to rebuild deterministic parsers 3 banks (mitigated by 25+ adaptors reference for pattern, not code)
- Need synthetic data generator for SA formats: R prefix, space thousands, 1 234,56 comma, (450) negative, Cr/Dr suffix, dates 2026/10/25, 25 Oct, 25-10-2026
- Paystack KYC may block live, so test-mode demo acceptable per homework Risk

Verification: `uv run pytest -q` + `pnpm --dir apps/web lint` + golden + RLS isolation after scaffold.
