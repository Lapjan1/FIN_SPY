# Disclaimer - FIN_SPY - Informative with Reference to Acts

Last updated: October 27, 2026

**This disclaimer is informative per user decision: all accounts should be recorded as private or business. Only in startup exceptional cases should it be mixed and then it gets complicated, so we respect and give info and the user deals with his auditor and SARS. For our usage we document transactions and we can view and represent the data in any way we would like to use it to enhance personal or SME business.**

## 1. No Legal, Tax, or Accounting Advice

FIN_SPY is a forensic documentation tool, not a legal, tax, or accounting advisor. All classifications, KPIs, debt strategies, and reports are bookkeeping aids for personal or SME business enhancement. You must consult a qualified South African attorney, SAICA-registered accountant, and SARS-registered tax practitioner before relying on any output for legal, tax, or CIPC/SARS filing purposes.

We provide export package CSV that auditor can use to input in their bookkeeping package.

## 2. Private vs Business Classification - User Decision

**Our call per product owner:** All accounts should be recorded as private or business. Only in startup exceptional cases should it be mixed and then it gets complicated. We respect and give info and the user deals with his auditor and SARS.

- **Normal case:** Each transaction is classified as `private` (100% personal) or `business` (100% for trade). No mixed.
- **Exceptional case (startup):** Where a person is trading as personal business mixed with personal finances (sole proprietor, person trading as), a transaction may be genuinely mixed (e.g., Telkom bill household + shop, fuel mixed use, vehicle). In this exceptional case, we allow `mixed` with business_pct and private_pct and rationale, but we flag it as complicated and requiring professional review.

**How we implement:**
- Classification engine: rules first (merchant memory per tenant), deterministic hints (account type, merchant category, keywords), AI suggestion second (Muse Spark 1.3 low effort with prompt `classify_private_business_v1.md`), human decision last. AI never finalizes, unknown stays unknown.
- Output per transaction: nature `business|private|mixed|unknown`, business_pct for mixed, category_id, rationale, source rule/ai/human, confidence, decided_by, decided_at, supersedes revision chain per `apps/api/db.py` classifications table.
- For `mixed`, we create split lines in journal: debit Expense 60% and debit Drawings 40% etc., reference classification revision that caused them.

**Reference to Acts - Informative so user is aware if he/she uses software:**

- **Companies Act 71 of 2008:**
  - **s19 Legal status:** Company is juristic person, exists continuously until deregistered. Property of company != property of director/shareholder. Using company bank for personal is using another person's property.
  - **s24 Form and standards for company records:** Any documents, accounts, books, writing, records or other information that a company is required to keep must be kept in written form for 7 years. Your product mirrors per `docs/METHOD_STATEMENT.md:21` commonly 5 years tax, 7 years company.
  - **s28 Accounting records:** Company must keep accurate and complete accounting records in official language, accessible from registered office, offence with intention to deceive to fail to keep accurate or complete or to falsify. If personal transactions run through company account without separate ledger, records not accurate per s28(1).
  - **s29-30 Financial statements:** Must present fairly state of affairs per IFRS, offence if false/misleading s29(2)(a) s29(6).
  - **Directors duties s76:** Fiduciary best interests, care, s75 conflict disclosure personal financial interest, s77 joint several liability for loss, s22 reckless trading trading with liability to defraud creditor includes mingling.
  - **Piercing veil s20(9):** If company funds treated as personal alter-ego, court can declare not separate.
  - **Source:** CIPC official PDF `CompaniesAct71_2008.pdf` downloaded via `default.read` from https://www.cipc.co.za/wp-content/uploads/Legal/Regulations/CompaniesAct71_2008.pdf

- **Tax Administration Act 28 of 2011:**
  - **s29:** Records 5 years from filing date, in official language, accessible. That includes proof of trade vs private. Full financial picture required.
  - **s46:** SARS can request 12 months statements.
  - **Source:** SARS website Tax Administration Act.

- **Income Tax Act 58 of 1962:**
  - **s11(a):** Only wholly/exclusively for trade deductible - mixing defeats proof.
  - **s23(a)(b):** Personal living expenses disallowed.
  - **Source:** SARS Small Business guides advise separate account strongly recommended to substantiate s11(a).

- **VAT Act 89 of 1991:**
  - **s55:** Tax invoices, **s28:** VAT records must be identifiable.

- **POPIA Protection of Personal Information Act 4 of 2013:**
  - **s1:** Bank statement = personal information + special personal info (financial).
  - **s8-14:** Open processing, minimal, security safeguards, retention justified and deletion/de-identification when no longer needed with legal-hold exceptions.
  - **s11(1):** Lawful basis consent, contract, legal obligation, legitimate interest, or s12(2)(a)-(c) legal proceedings/investigation of offence, or s18 historical/statistical. Forensic under legitimate interest + legal proceedings.
  - **s19:** Security safeguards.
  - **s26:** Prior authorisation from Information Regulator if processing on large scale.
  - **Source:** POPIA official act.

- **FICA/POCA, Banks Act s33, CPA s205, ECTA s15:**
  - Banks Act s33 bank secrecy overridden by court order / POPIA legal basis.
  - CPA s205 subpoena for bank statements.
  - ECTA s15 data messages admissible, weight assessed with regard to reliability of generation, storage, integrity maintained, originator identified.

**We respect and give info and user deals with auditor and SARS:** We provide the classification with rationale, source, confidence, decided_by, and flag mixed as complicated. User must consult auditor and SARS. For company entity, any private or mixed in company bank = flag as exception/potential breach per s28, should be drawings/director loan/deemed dividend and require auditor review. For sole prop / person trading as, mixed is expected and allowed per no separate juristic person, but must still apportion for tax.

## 3. Export Package for Auditor

We provide export package that auditor can use to input in their bookkeeping package:

- **PowerBI Pack:** Excel file with star-schema sheets `fact_transactions, fact_journal, dim_date, dim_account, dim_category, dim_entity, dim_document` + CSVs per `apps/api/reports.py` `generate_powerbi_pack()` via `GET /v1/reports/powerbi` per homework Part 5.10.
- **Excel Workbook:** Per Appendix G Cover, Summary, Transactions Table, Journal, Trial_Balance live SUMIFS, Private_vs_Business, Flags, Source_Register, Method_Notes, Dictionary via `GET /v1/reports/excel`.
- **CSV for Auditor:** `GET /v1/reports/powerbi` returns CSV dir with `fact_transactions.csv` etc that auditor can import into Pastel, Xero, QuickBooks, Sage. Also `GET /v1/transactions?tenant_id=...` returns JSON.
- **Evidence Pack ZIP:** Originals, derivatives, extraction_runs raw outputs, audit_excerpt.jsonl, manifest.json + manifest.sha256 + .tsr tokens + verification instructions per Appendix D via `scripts/verify_pack.py`.

Auditor can use data export to csv and input in their bookkeeping package per user decision.

## 4. For Our Usage - Document Transactions and View/Represent Data

For our usage we document transactions and we can view and represent the data in any way we would like to use it to enhance personal or SME business per user decision:

- **Document:** Every transaction extracted with line-ID grounding, stored with spans page bbox line_id text_hash, fingerprint `SHA256(date|amount|desc_norm)`, audit_log hash-chain `prev_hash/row_hash SHA256(prev||canonical_json)`, content-hash vault `data/vault/<sha>.pdf` immutable per `AGENTS.md`.
- **View/Represent:** Dashboard per `docs/UI_SPEC.md` KPI cards leak score R/mo runway burn savings rate debt-to-income private vs business split waterfall treemap calendar heatmap subscription radar anomaly markers slicers cross-filter drill-through to transaction grid split screen PDF page with highlighted lines per signature demo moment: click any number -> grid -> PDF page with highlighted lines.
- **Enhance personal or SME business:** KPIs per `apps/worker/spy/kpi.py` `compute_kpis()` inflow vs outflow per direction credit inflow debit outflow, runway current_balance/burn_rate, savings_rate (inflow-outflow)/inflow, debt snowball/avalanche via `debt.py` Decimal, private vs business ratio, top vendors, subscription creep leak score.

## 5. Forensic Investigator Portfolio

A forensic investigator can put together a portfolio of accounts on one person under investigation if lawful mandate + POPIA basis, chain-of-custody preserved per `docs/METHOD_STATEMENT.md` + research in `explore` subagent: lawful basis client engagement letter, board resolution, divorce discovery rule 35, curator/insolvency s381, insurance, CPA s205 subpoena, FICA s37 disclosure, court order Anton-Piller. Must list lawful basis in report preamble, show mandate reference, show POPIA processing notice, keep subject isolation per investigation tenant isolation in code mirrors this.

## 6. Governing Law

These terms governed by laws of South Africa. POPIA compliance, ECTA s15 data messages admissibility. This document is engineering and product guidance only - not legal, tax, or accounting advice. Have attorney + registered accountant review report wording, retention policy, privacy notice, terms before charging real customers per homework Part 12 Sources.
