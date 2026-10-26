# Changelog

## v0.1.0-baseline - 2026-10-26
- Fresh scaffold for Meta Global AI Dev Hackathon
- Monorepo: apps/web (Next.js+Tailwind+shadcn+ECharts), apps/api (FastAPI), apps/worker (Muse Spark)
- DB-first: SQLite vault content-hash + Postgres RLS path
- Forensic layer: SHA256 vault, hash-chain audit_log, line-ID grounding
- Spy layer: subscription/duplicate/fee/anomaly detectors + KPI engine + debt snowball/avalanche
- Stack: Python 3.12 uv, Node 20 pnpm, Meta models via adapter (freellmapi dev, llama.com prod)
