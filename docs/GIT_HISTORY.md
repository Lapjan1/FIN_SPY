# GIT_HISTORY.md - commit history as documentation

Why this file exists: the GitHub account is frozen, so the 87-commit
hackathon history cannot be browsed online. This document is the history:
full graph, per-day counts, and most-touched files, exported 2026-11-01
from the local checkout (HEAD 7b54c86, 49 ahead of origin/main).
If GitHub access returns, push and this file becomes a bonus.

Bundle backups (offline images of this same history) live next to the
repo root: `FIN_SPY-backup-2026-10-28.bundle`,
`FIN_SPY-backup-2026-10-28-day7.bundle`,
`FIN_SPY-backup-2026-10-28-day8.bundle`,
`FIN_SPY-backup-2026-10-28-day9start.bundle`,
`FIN_SPY-backup-2026-10-29-day9auth.bundle`,
`FIN_SPY-backup-2026-10-29-day9part2.bundle`.
Verify any of them with `git bundle verify <file>`.

## Commits per day (window Oct 26 - Nov 1)

- 2026-10-26: 5 (scaffold, DB+auth+paystack, privacy, settings, red tests)
- 2026-10-27: 34 (Railway deploy fight, extraction v1, intake, Day2)
- 2026-10-28: 11 (reconciliation both directions, side-by-side, Day3)
- 2026-10-29: 7 (Day7/8/9: signing, limiter, prod wiring, auth UX)
- 2026-10-30: 27 (account channel/boundary, forensic, banding, row-grouping)
- 2026-11-01: 3 (billing live-proof, excel note, audit docs)

## Most-touched files (top 12, window)

- apps/api/main.py: 27
- STATE.md: 26
- LEARNINGS.md: 22
- apps/worker/parsers/extractor.py: 17
- apps/api/db.py: 13
- apps/web/src/lib/api.ts: 10
- apps/worker/main.py: 10
- apps/api/reports.py: 10
- .agents/memory/MEMORY.md: 9
- docs/TIMELINE.md: 9
- apps/worker/parsers/fnb.py: 7
- apps/web/src/app/upload/page.tsx: 7

## Full graph (newest first)

```
* 7b54c86 Docs: billing+excel evidence, learnings 73-78, hackathon audit 81, SA law index
* 3c95772 Excel totals recalc note on Cover + Reports + Help (370 green, tsc 0)
* af8419c Local docker + fiction fix + header/bank banding + rejected-excluded (369 green, ruff zero-new, learnings 67-72)
* 2595ebf Docs: STATE live deps + learning 66 + probe generator script
* 0b11023 Docs: row-grouping closed with live evidence (API 22efb244)
* 5e8d3ad FNB: drop digitless amount matches, descriptions survive
* 79d3bb2 Parsers: Statement Period/Date framing is header noise, never rows
* 7a79fd8 Row-major grouping + year inference + loud failures (330 green, tsc 0)
* bbc696d Docs: sniff STATE+learning 63, README boxes honest
* c47f956 Docs: csv-sniff live evidence API 91c232ff
* 9c755e8 CSV sniff tolerates ragged preamble lines (315 green)
* 1eb9288 Docs: STATE bullet for help refresh 29aaf2f (HEAD doc audit)
* 86b64d7 Docs: forensic live evidence, learning 62, STATE 311
* e5dfea2 Fix CSV tamper TypeError (None page dims) + metadata-stage log messages (311 green)
* 5bd1e49 Intake forensic: statement gate + tamper wired + honest overlap + pack guardrails (310 green, tsc 0)
* 6257a6a Docs: boundary live evidence, learning 61, STATE 299
* e7c3dad Account boundary: scoped evidence/POPIA/signed packs + intake attribution + picker on all six downloads (299 green, tsc 0)
* d7d41e3 Docs: learnings 58-60, STATE account-channel live, todo steps marked done
* 74e36fb Dashboard: Outflow by vendor treemap -> pie chart (tsc 0)
* 84fcc25 FIX-account-channel: live evidence API c9578c4c + web 90ab2962
* bbbe977 bank-accounts reports transactional truth: hide 'unknown' placeholder, synthesize unknown row from txns (292 green)
* 71bba5e Account channel: auto-book classifies, Move from suspense, per-account filters, global picker, Excel classification columns (291 tests green, tsc 0)
* 29aaf2f Help: cover Books/Debt/Reports + void flow + owner settings + CSV/OFX
* f729fc5 Docs: Day 10 recap (done/learned/diff/left)
* 3176043 Docs: audit 8.5 re-verified + closes task doc + STATE
* f51ad5d 8.5 closes: DSN redaction, DEV_AUTH gate, trigger-skip, README pitch+disclosure, email claim cut
* 50ab57b Copy: privacy images roadmap note; picker accepts PDF/CSV/OFX; commit audit backlog
* fd4ebbd Small fixes: doc-scoped fp for unknown accounts; images 422 (no OCR yet)
* f9a512d Day4: OSS research note + 422 pins (invalid-params 500 claim disproven)
* c955037 Docs: audit-fix task docs + GUI audit evidence + STATE
* 94acd9c Learning 57: vault volume + duplicate heal
* 5f97b33 Upload fix: duplicate with lost bytes restores + requeues; receipt shows restored state
* 4d8e72c Audit fix 2: content-sniff dispatch (vault keys always .pdf) + CSV shape sniff
* 0eca6ee Audit fix: text-reader for CSV/TXT/OFX uploads (was PDF-only RuntimeError)
* 9919715 Promise plan P0+P1: extractor, downloads, books/debt/reports UI, void, owner prefs, queue kill
* 1779d45 Day9 part2: session gates, cancel, help, worker live, per-tenant dedup
* 0baf627 Day9 part1: real landing, prod wiring, auth UX live
* c1f1a9e Scrub ClearFlag/clearmind from app copy + polish legal English
* 7652622 Day9 start: settings-driven model wiring + readiness audit + video script
* 5355101 Day8 done: 100RPM limiter+fairness+retries, image-SAM endpoints, gates green, F821 worker fix, recap + learnings 37-39
* 70db1c2 Day7 done: PAdES+TSA signing, email wiring, recap + learnings 34-36 + checklist
* 1187462 Day7: evidence pack builder + Excel-12 P&L/balance sheet + window cap
* de9f8a6 Day6 done: heatmap + recap + learnings 31-33 + checklist (cross-filter stretch noted)
* 995011f Day6p2: real chat over DB + upload/inbox/chat pages
* 8784315 Day6p1: worker gate fix + real spans/dims + sources/file endpoints + dashboard/transactions drill UI
* 7da3412 Day5: spy detectors + Decimal debt + leak KPIs + tenant-lookup sweep (17 sites -> _tenant_of)
* 4736476 Day4: books (ledger/classify/review/9999/repost/legal) + review UI + deploy config + audit docs
* a95f3f3 fix(pg): translate sqlite DDL for postgres boot (strftime->EXTRACT, OR REPLACE views, skip triggers) + regression tests
* 50eae41 chore: disable uptime cron while suspended + add Support appeal draft
* 8cca543 feat: Day3 close - 3 books choice, totals per period before pct, inflow/outflow flags, fix invalid parameters FK bug
* 6257681 docs: update to Day3 finish v0.7.0 hackathon grade with date+evidence - answer user are we at end of day 3
* 7b1b7c9 docs: update STATE to Day3 finish v0.7.0 with evidence 25+ commits 80 passed live API Online ready true backend pg
* 33e669a feat: disclaimer with acts reference private/business only mixed exceptional startup + auditor CSV export
* 508fac6 docs: recap Day3 finish - extraction quality + intake tamper + per bank account ledger + totals both directions + META audit
* 2ace643 feat: per bank account number ledger - no contamination, helps per customer 20 private 100 business
* fe7ddf3 feat: per bank account number ledger - each account number own ledger within same DB per tenant, not own DB
* f215b64 feat: Day3 perfect health - entity register bankcodes deviations per bank + global running balance + KPI inflow/outflow
* d33cbd4 feat: Day3 extraction quality - wire real Meta adapter line-ID grounding + spans bbox + fingerprint dedup + golden 99% accuracy
* 7d82e69 docs: recap Day2 finish - done, learned, documented up to Day2
* ab3836a feat: DB useful for Excel/PowerBI per conventions - indexes + dim_date + star-schema views + journal constraint + PowerBI pack
* c84a49b fix: totals +/- == balance from top to bottom and bottom to top - consolidation now passes
* 8e5ad69 fix: pnpm approve-builds ignored build scripts canvas@3.2.3 unrs-resolver@1.12.2
* e723d17 feat: side-by-side statement and extraction viewer per user request
* 4b42ad7 feat: extraction test opening balance +/- amount == running balance/total top->bottom + bottom->top per user
* d4c4aa8 feat: reconcile totals +/- == balance from top to bottom and bottom to top per user question
* 73a00d7 fix: Railway build pip not found - add python3Packages.pip to nixPkgs + use pip not python3 -m pip
* a187280 docs: audit hackathon grade - date+evidence, learnings, META meta compliance - answer user questions
* 1f99344 feat: intake capabilities - bank statement detection, duplicate files, exclude non-bank, original vs tampered
* ab663a6 fix: web build public not found - add public/.gitkeep + Dockerfile COPY without fallback
* 3f2a8e6 feat: handle encrypted/password protected PDFs - intake + extraction + tests
* a513a6c feat: Day2 extraction line-ID grounding v1 + fix web build JSX push issue
* 03d0279 fix: web build JSX escaping -> and {{{{ - Next.js 15.5.28 webpack error
* 66445dd feat: email service no-reply mail for login + Day2 Day7 planning note per user question
* 8e259f2 fix: web service build /package.json not found - Dockerfile context repo root
* 246d942 fix: Railway sleep after inactivity - add uptime ping Cron every 5 min to /health/ready
* 7ac4222 fix: Railway build pip not found exit 127 - use python3 -m pip
* 2228242 fix: Railway deploy email-validator missing - add pydantic[email] + email-validator
* 4f65d08 fix: Railway deploy uvicorn not found - add requirements.txt + pip install -r requirements.txt
* c514e7c fix: Railway deploy uvicorn not found - use python -m uvicorn
* 5c6b34b fix: Railway deploy - add Procfile + nixpacks.toml start command uvicorn apps.api.main:app per Railpack no start command detected
* 478ff01 feat: live deployment ready for Paystack application - Dockerfiles + railway.json healthcheck + PAYSTACK_APPLY spec
* 98a21e0 test: comprehensive red tests for auth, paystack, parsers - ensure fails for right reasons
* fce4747 feat: Settings UI for Meta models per hackathon guidelines - admin-only keys + user-visible read-only + pure Meta no openai phi4 + ollama-local fallback only
* 28bc951 feat: privacy templates POPIA from clearmind + Next.js legal pages + Railway healthcheck + API real markdown
* 98b069d docs: make DB+auth+paystack adapter hackathon grade - update STATE, CHANGELOG, LEARNINGS, README checklist, MEMORY index, ADRs
* 2a49ac6 feat: DB+auth+paystack adapter based on clearmind pattern with bcrypt + hash-chain audit + FastAPI deps
* 1770fe8 chore: initialize forensic SaaS scaffold v0.1.0-baseline
```

Regenerate: `git log --graph --oneline --since='2026-10-26'`.
