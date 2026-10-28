# RECAP Day 7 Finish - Exports + Billing + Email - 2026-10-28

Per docs/TIMELINE.md Day7: Excel live SUMIFS trial balance + star-schema, signed PAdES PDF + RFC3161 TSA pyHanko, Evidence Pack ZIP + `scripts/verify_pack.py`, Paystack billing, email service implementation. Billing was done pre-Day7 (HMAC, verify, idempotent webhook); everything else built this round.

## What We Have Done (Oct28 - Day 7, four slices)

### 1. Evidence Pack generation (was verifier-only)
- `generate_evidence_pack(tenant_id, report_id?, sign?)`: staging dir with vault originals (role original), PowerBI pack + CSVs, Excel workbook, auditor CSV (role report), audit.json (role audit), extraction_runs.json (role extraction_raw), manifest.json + manifest.sha256 per Appendix C, zipped. Returns file_key + sha + manifest + audit head.
- `GET /v1/reports/evidence-pack` (+ `?sign=true` embeds the PAdES PDF when a cert is configured, else skips with warning). Audit-logged.
- Proof is independent: `scripts/verify_pack.py` exits 0 on a produced pack, exits 1 on a byte-tampered copy (tests/test_pack_day7.py, 3 tests).

### 2. Excel-12 workbook (was 4 sheets)
- `generate_excel_workbook(tenant_id, from_date?, to_date?)`: Cover, Summary, Transactions, Journal, Trial_Balance (totals ALL codes, live SUMIFS per account + balanced check), Income_Statement (P&L, income minus expense, net formula), Balance_Sheet (A = L + E + earnings linked live from P&L net), Private_vs_Business, Flags, Source_Register, Method_Notes, Dictionary.
- 12-month window cap (`_validate_window`, 422 beyond), posted-only, 5000-row limit + truncation flag, per-sheet helpers after C901 split.
- `GET /v1/reports/excel?from_date&to_date` with 422 mapping. Verified with openpyxl: 12 sheets, posted-only, window filtering, formula strings, P&L->BS link (tests/test_excel_day7.py, 3 tests).

### 3. PAdES + TSA signing (was verify notes only)
- apps/api/signing.py: `build_report_pdf` (1-page DB summary via pymupdf), `sign_pdf_file` (pyHanko PAdES, RFC3161 via freetsa.org with honest untimestamped fallback + warning), `verify_pdf_file` (valid/intact/trust/signer split), `build_and_sign`.
- `GET /v1/reports/signed-pdf?from_date&to_date`: 422 when cert unconfigured or window bad. Cert via FINSPY_SIGN_CERT/KEY (+CHAIN, TSA_URL, LOCATION, REASON).
- Live evidence: freetsa.org probe returned timestamped=True with embedded token; verify reports valid+intact. 5 tests with ephemeral self-signed cert: roundtrip, ByteRange-targeted tamper breaks intact, unsigned reports zero, unconfigured refused, endpoint + pack-embed (tests/test_sign_day7.py).

### 4. Email wiring (was implemented but zero call sites)
- register -> welcome, forgot -> reset link, failed-payment webhook -> dunning (extracted `_maybe_send_dunning` to hold paystack complexity at baseline). All tenant-tagged, all exception-proofed so mail never breaks flows.
- Token leak closed: reset token returned ONLY in dev (no email key); with a key configured it is emailed and the response carries no token. Red test preserved (tests run keyless).
- 5 tests: welcome/reset mock audits, prod Resend call shape (auth header, link in body, no token out), dunning audit, SMTP-fallback behavior (tests/test_email_day7.py).

## Evidence
- `python -m pytest -q -p no:cacheprovider` 165 passed 0 failed (unblocked shell).
- `uvx ruff check` clean on all new/edited Day-7 files; paystack 10 findings verified byte-identical on untouched HEAD tree.
- `verify_pack.py` exit 0 on produced pack / exit 1 on tampered (independent oracle, not self-assert).
- Commits: 1187462 (pack + Excel-12), plus Day-7 close commit for signing + email + this recap.

## What We Learned
- LEARNINGS 34 (PAdES trust model): pyHanko `valid` (CMS math) vs `intact` (ByteRange digest) vs `trusted` (chain) are three separate verdicts - assert the right one; tamper tests must flip a ByteRange-covered byte, not the CMS gap.
- LEARNINGS 35 (ARM pip): never let pip rebuild cryptography on win-ARM64 (no wheel for latest, no Rust) - pin to the installed build when adding pure-Python deps like pyHanko.
- LEARNINGS 36 (reset tokens): returning tokens in API responses is a dev-only privilege - gate on email-key presence so prod can never leak, and keep a red test pinning the dev path.
- Journal balance triggers fire per-row: seed legs before flipping posted=1 (same as the real ledger path).
- xlsxwriter `write_formula` rejects non-strings: empty sections need plain zero writes, not `formula if items else 0`.

## Checklist vs plan (Day 7 honest)
- [x] Excel live SUMIFS + star-schema (+ P&L + balance sheet + window cap, beyond Appendix G)
- [x] signed PAdES PDF + RFC3161 TSA (live token verified; freetsa chain not locally rooted - expected)
- [x] Evidence Pack ZIP + verify_pack.py (generation + independent verification + tamper rejection)
- [x] Paystack billing (pre-existing, plus dunning hook)
- [x] Email service implementation (wired + tested, token leak closed)
- Day 7 CLOSED, no remainders.
