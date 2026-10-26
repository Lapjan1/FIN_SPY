# PLAN.md - FIN_SPY Forensic Spy

## Purpose
One sentence: Give a South African business owner or individual a court-grade peek into their finances from a pile of PDFs - every number traces to exact bbox, dynamic books, spy for leaks/subscriptions, KPIs + debt snowball/avalanche.

## Inputs / Outputs
**In:**
- Bank statement PDFs (SA: FNB, Standard Bank, Absa, Nedbank, Capitec) or CSV/OFX, invoice/receipt images (JPG/PNG), user debts list (creditor, balance, APR, min payment)
- Config: tenant_id, entity personal/business, chart of accounts seed

**Out:**
- DB: SQLite `data/fin_spy.db` (MVP) -> Postgres prod with RLS - tenants, documents (sha256), pages, extraction_runs, spans (line_id,bbox,text_hash), transactions (fingerprint), classifications, accounts, journal_entries/lines, flags, audit_log hash-chained, reports
- Vault: `data/vault/<sha256>.pdf` immutable + derivatives (page images)+ timestamp token .tsr
- Excel: Cover, Summary KPIs, Transactions (Table with doc/page/line_ids deep link), Journal, Trial Balance live SUMIFS, Private_vs_Business, Flags, Source_Register, Method & Notes, Dictionary
- PDF Report: signed PAdES via pyHanko + RFC3161 TSA, methodology, source schedule with hashes, reconciliation results, classification decisions, limitations, glossary, sign-off block
- Evidence Pack ZIP: originals/, derivatives/, extraction_runs raw JSON, audit_excerpt.jsonl, manifest.json + manifest.sha256 + .tsr + verification instructions
- Dashboard: KPI cards, cashflow waterfall, category treemap, calendar heatmap, private vs business split, subscription radar, anomaly markers, slicers cross-filter, drill to grid -> PDF highlight
- PowerBI-ready: star schema Excel + CSVs: fact_transactions, fact_journal, dim_date, dim_account, dim_category, dim_entity, dim_document

## User Tasks (7 verbs)
1. **Upload** PDFs/images/CSV - drag drop, see hash + timestamp, progress
2. **Check** extraction + reconciliation gate (opening+sum=closing, running balance monotonic) - review queue accept/edit with reason creates revision
3. **Decide** private/business/mixed % + category - rules suggest first, AI second, human last, merchant memory per tenant
4. **Drill** any number -> grid -> source viewer split screen pdf.js with highlighted bbox lines
5. **Peek** KPIs: runway months, burn rate, savings rate, debt-to-income, top leaks, subscription creep, Benford/windf etc
6. **Kill Debt** - input debts, get snowball (psych win) vs avalanche (interest save) plan tailored to cashflow, SA context, with what-if simulator
7. **Export** Excel + signed PDF + Evidence Pack + ask Spy Chat "Where did my Woolworths money go?" with tool calling over DB

## Constraints
- Lang: Python 3.12 uv, Node 20 pnpm, Windows PowerShell 5.1, 16GB ARM thin client -> heavy work on Railway/Supabase or local light
- DB-first mandatory: Extract -> persist -> products read DB. Never direct report.
- Models: config/models.yaml not code. Base URLs freellmapi http://127.0.0.1:3001/v1 dev (muse-spark-1.1), Ollama http://127.0.0.1:11434/v1 fallback, Prod META_API_KEY -> https://api.llama.com/compat/v1 muse-spark-1.3 standard NOT contributor
- Money Decimal/int cents never float, dates UTC store, Africa/Johannesburg display
- Security: 20 rules from security guide, proxy-only net, no --yolo outside disposable container, hooks.json outside sandbox
- Cost: cheapest path safe, free tiers first, every paid flagged. Demo $5-10. AI ~$0.04/8p statement, $150 credit ~3000 statements
- Legal: "court-ready" = built to support admissibility (ECTA s15 reliability), not guaranteed. AI disclosure in every report. No FINSPIB import.
- Hardware: 16GB ARM can't run Glimmer 30B 16.8GB Q4 - use hosted or smaller local model for private mode roadmap

## Done Means (acceptance checks -> become /goal checks + tests)
- Given synthetic FNB CSV 200 tx, `pytest tests/golden` row accuracy >=99% digital, reconciliation pass 100% confirmed, 0 silent failures, every confirmed tx has >=1 source_spans line_id+bbox
- Given same pdf uploaded twice, fingerprint SHA256(date|amount|desc_norm) detects exact duplicate flag, second upload status duplicate but preserved
- Given transaction click in dashboard, API `/v1/transactions/{id}/sources` returns page_no+bbox, web pdf.js highlight overlays correct lines
- Given tenant A and B, RLS/isolation test fails cross-tenant read (DB-level)
- Given debts: R45k Capitec 21% + R20k FNB 15% + R10k Woolworths 0%, snowball plan shows payoff order Woolworths->FNB->Capitec, avalanche Capitec->FNB->Woolworths, interest saved calculated Decimal, not float
- Given evidence pack ZIP, `scripts/verify_pack.py` recomputes SHA256 each file vs manifest.json, manifest hash vs printed in PDF, TSA token verifies with openssl, PDF signature panel valid
- Given 1000 tx, analyze <5s without LLM, <15s with LLM, queue respects 100 RPM global limiter, no duplicate charges on retry
- Chat answers "What subscriptions can I cancel?" with tool calling, cites 3 subs with evidence links, no hallucination
