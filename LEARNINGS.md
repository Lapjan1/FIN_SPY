# LEARNINGS.md - Append-only mistakes log

## 2026-10-26-01 PyMuPDF AGPL licensing trap
Symptom: Chose PyMuPDF for bbox extraction, later realized SaaS distribution needs commercial license check.
Cause: Did not verify license before picking library (AGPL vs commercial).
Fix: Keep PyMuPDF for hackathon MVP, document fallback to pdfplumber/pypdfium2 for prod SaaS path with abstraction layer in apps/worker/parsers/.
Applies when: Picking PDF libraries for commercial product.

## 2026-10-26-02 Old hardcoded single-company COA
Symptom: Previous FINSPIB had one set books hardcoded, feeding any other company still spit same COA.
Cause: Built SaaS around one tenant's books, not dynamic multi-tenant COA seeding.
Fix: This repo builds dynamic COA per tenant - seed generic SA COA, learn from transactions, merchant memory per tenant, never hardcode one company.
Applies when: Designing ledger, tenant isolation tests mandatory.

## 2026-10-26-03 DB-first vs direct report generation
Symptom: Initially extracted and produced Excel directly, losing traceability and ability to re-run.
Cause: No intermediate DB, every report required re-extraction.
Fix: Extract -> persist to SQLite/Postgres with line IDs and bbox spans -> ALL products (dashboard, Excel, PDF, KPIs, debt strategies) read from DB. Verification script re-hashes DB-stored files.
Applies when: Any extraction pipeline, ETL.

## 2026-10-26-04 Meta contributor tier data leak
Symptom: Tempted to use muse-spark-1.3-contributor for cheap cost.
Cause: Did not read data-use warning: "Meta may train on prompts/completions".
Fix: Use standard tier only for customer docs. Contributor only allowed for synthetic test data. Document in AGENTS.md.
Applies when: Choosing Meta model IDs.
