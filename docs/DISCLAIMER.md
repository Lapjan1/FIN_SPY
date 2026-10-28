# Disclaimer - FIN_SPY - Informative with Reference to Acts

Last updated: October 27, 2026

**Our position: every account should be recorded as either private or business. Only in exceptional startup cases may an account be mixed - and mixed accounts get complicated. We give you the information and respect your decision; you settle the treatment with your auditor and SARS. In the product itself, we document every transaction and may view and present the data in any way that helps improve a personal or SME business.**

## 1. No Legal, Tax, or Accounting Advice

FIN_SPY is a forensic documentation tool, not a legal, tax, or accounting advisor. All classifications, KPIs, debt strategies, and reports are bookkeeping aids for personal or SME business enhancement. You must consult a qualified South African attorney, SAICA-registered accountant, and SARS-registered tax practitioner before relying on any output for legal, tax, or CIPC/SARS filing purposes.

We provide an export package (CSV) that your auditor can import into their bookkeeping package.

## 2. Private vs Business Classification - User Decision

**Our position:** All accounts should be recorded as private or business. Only in exceptional startup cases should an account be mixed - and then it gets complicated. We respect your decision, give you the information, and you settle the treatment with your auditor and SARS.

- **Normal case:** Each transaction is classified as `private` (100% personal) or `business` (100% for trade). No mixed.
- **Exceptional case (startup):** Where a sole proprietor trades through personal finances, a transaction may be genuinely mixed (e.g., a Telkom bill split between household and shop, mixed-use fuel or vehicle). In this exceptional case we allow `mixed` with business_pct, private_pct, and rationale, but we flag it as complicated and requiring professional review.

**How we implement:**
- Classification engine: saved rules first (per-tenant merchant memory), deterministic hints second (account type, merchant category, keywords), AI suggestion third (Muse Spark 1.3), human decision last. AI never finalizes; uncertain items stay unknown.
- Output per transaction: nature (`business`, `private`, `mixed`, or `unknown`), business_pct for mixed, category, rationale, source (rule, AI, or human), confidence, reviewer, timestamp, and a revision chain of superseded decisions.
- For `mixed` transactions we create split journal lines (for example, debit Expense 60% and debit Drawings 40%), each referencing the classification revision that caused it.

**Reference to the Acts - so you know what applies when you use this software:**

- **Companies Act 71 of 2008:**
  - **s19 Legal status:** Company is juristic person, exists continuously until deregistered. Property of company != property of director/shareholder. Using company bank for personal is using another person's property.
  - **s24 Form and standards for company records:** Any documents, accounts, books, writing, records, or other information that a company is required to keep must be kept in written form for 7 years. FIN_SPY mirrors this: commonly 5 years for tax, 7 years for company records.
  - **s28 Accounting records:** A company must keep accurate and complete accounting records in an official language, accessible from its registered office. It is an offence to fail, with intent to deceive, to keep accurate records, or to falsify them. If personal transactions run through a company account without a separate ledger, the records are not accurate as s28(1) requires.
  - **s29-30 Financial statements:** Must fairly present the state of affairs per IFRS; it is an offence if they are false or misleading (s29(2)(a), s29(6)).
  - **Directors' duties s76:** Act in the company's best interests with due care; s75 requires disclosing personal financial interests; s77 imposes joint and several liability for losses; s22 prohibits reckless trading, which includes mingling funds to defraud creditors.
  - **Piercing the veil s20(9):** If company funds are treated as a personal alter-ego, a court can declare the company not separate from its controllers.
  - **Source:** CIPC official PDF `CompaniesAct71_2008.pdf` at https://www.cipc.co.za/wp-content/uploads/Legal/Regulations/CompaniesAct71_2008.pdf

- **Tax Administration Act 28 of 2011:**
  - **s29:** Keep records for 5 years from filing date, in an official language, accessible - including proof of trade versus private. The full financial picture is required.
  - **s46:** SARS can request 12 months statements.
  - **Source:** SARS website Tax Administration Act.

- **Income Tax Act 58 of 1962:**
  - **s11(a):** Only wholly/exclusively for trade deductible - mixing defeats proof.
  - **s23(a)(b):** Personal living expenses disallowed.
  - **Source:** SARS Small Business guides strongly recommend a separate account to substantiate s11(a) claims.

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

**We respect your decision and give you the information; you settle the treatment with your auditor and SARS.** We provide each classification with rationale, source, confidence, and reviewer, and we flag mixed items as complicated. For a company entity, any private or mixed transaction in the company bank account is flagged as an exception and potential breach of s28: it should be treated as drawings, a director's loan, or a deemed dividend, and requires auditor review. For a sole proprietor or person trading as themselves, mixing is expected and allowed (there is no separate juristic person), but income and expenses must still be apportioned for tax.

## 3. Export Package for Auditor

We provide an export package that your auditor can import into their bookkeeping package:

- **PowerBI Pack:** Excel file with star-schema sheets (`fact_transactions`, `fact_journal`, `dim_date`, `dim_account`, `dim_category`, `dim_entity`, `dim_document`) plus CSVs, via `GET /v1/reports/powerbi`.
- **Excel Workbook:** Cover, Summary, Transactions Table, Journal, Trial Balance with live formulas, Private vs Business, Flags, Source Register, Method Notes, and Dictionary, via `GET /v1/reports/excel`.
- **CSV for Auditor:** `GET /v1/reports/powerbi` returns CSV files such as `fact_transactions.csv` that an auditor can import into Pastel, Xero, QuickBooks, or Sage. `GET /v1/transactions?tenant_id=...` returns JSON.
- **Evidence Pack ZIP:** Originals, derived files, extraction raw outputs, audit excerpt, manifest with hashes, timestamp tokens, and verification instructions, verifiable via `scripts/verify_pack.py`.



## 4. For Our Usage - Document Transactions and View/Represent Data

We document every transaction, and we may view and present the data in any way that helps improve a personal or SME business:

- **Document:** Every transaction is extracted with line-ID grounding and stored with its source spans (page, coordinates, line ID, text hash), a fingerprint of date, amount, and normalized description, a hash-chained audit entry, and an immutable copy of the original in the content-hash vault.
- **View/Represent:** A dashboard with KPI cards (leak score in R/mo, runway, burn, savings rate, debt-to-income), private-vs-business split, waterfall, treemap, calendar heatmap, subscription radar, and anomaly markers, with slicers, cross-filtering, and drill-through from any number to the transaction grid and the highlighted source lines in the PDF.
- **Enhance personal or SME business:** KPIs computed from the ledger - inflow vs outflow, runway (balance divided by burn rate), savings rate, debt snowball/avalanche plans, private-vs-business ratio, top vendors, and subscription-creep leak score.

## 5. Forensic Investigator Portfolio

A forensic investigator may compile a portfolio of accounts on one person under investigation where there is a lawful mandate and a POPIA basis, with chain-of-custody preserved. Lawful bases include a client engagement letter, board resolution, divorce discovery (rule 35), curator or insolvency appointment (s381), insurance investigation, CPA s205 subpoena, FICA disclosure, court order, or Anton Piller order. The report preamble must list the lawful basis, show the mandate reference and the POPIA processing notice, and subjects must stay isolated per investigation (mirrored by tenant isolation in the code).

## 6. Governing Law

These terms are governed by the laws of South Africa, including POPIA and ECTA section 15 on the admissibility of data messages. This document is engineering and product guidance only - not legal, tax, or accounting advice. Have an attorney and a registered accountant review the report wording, retention policy, privacy notice, and terms before charging real customers.
