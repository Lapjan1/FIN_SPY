# FIX: Row-major word grouping (real PDFs extract)

## Goal
FNB-class PDFs emit text column-by-column; grouping by native
(block, line) shreds one visual row into 4-5 "lines" so no parser can
fire. Group PyMuPDF words row-major (y-band + x-sort, fresh code) so
each row reads date + description + amount + balance. LLM auth
failures fail loudly; zero-row extractions mark exception.

## Steps
1. [x] `_group_words_rows` unit-tested on synthetic words; primary
   path uses it; generic/deterministic fire on regrouped rows.
2. [x] 401/403 -> ModelAuthError; worker marks exception with clear
   message; zero rows -> exception, never proposed.
3. [x] Full suite + commit + deploy + live re-extract of synthetic
   column-major PDF (no PII in proof).

## Evidence
- Step 1 red->green: tests/test_row_grouping.py 3/3
  (column-emitted words regroup to clean rows); real-sample probe
  419 frag lines -> 125 clean rows (e.g. `04 Jul POS Purchase
  Superspar Karaglen ... 3,193.31Cr`), PII kept out of the repo.
- Step 1b year inference: Statement Period/Date year + Dec/Jan
  rollover only; end-year anchor (`years[-1]`) after Dec 2023/Jan
  2024 fixture caught first-year grab. tests/test_generic_year.py
  4/4; chaining drops the first raw row (no previous balance), so
  fixtures assert rows 2..n.
- Step 1c golden regression caught + fixed: y-sort returns visual
  (not emission) order; synthetic_statement.pdf is emitted
  bottom-up, so rows run reverse-chronological and FNB's
  row-derived opening/closing estimates (which CLOBBERED the stated
  R12 340.55/R20 790,55) went wrong. Fix: stated balances are
  ground truth, derivation is fallback-only
  (apps/worker/parsers/fnb.py:182-199). Pinned by
  test_fnb_stated_balances_survive_reversed_rows +
  test_fnb_balances_derived_when_unstated; golden suite green.
- Step 2 red->green: tests/test_loud_failures.py 6/6 (401 ->
  ModelAuthError naming provider/model, key never echoed;
  non-auth errors still mock; llm_fallback re-raises;
  decide_doc_status: 0 rows -> exception even on gate pass).
  Worker audits `extraction.auth_fail` with the full PII-free
  message; zero-row docs warn `0 rows extracted - re-extract or
  capture manually` and land `exception`, never `proposed`.
- Gates: `python -m pytest tests -q -p no:cacheprovider` 330 passed;
  `pnpm --dir apps/web exec tsc --noEmit` exit 0.
- Step 3 live (API 22efb244 + web 37704034): column-emitted probe
  `data/samples/fnb_column_shape.pdf` (synthetic, no PII) uploads
  gate True conf 1.0, extracts 6/6 rows with exact amounts/balances/
  directions, status `proposed`, account 62345678901/FNB/250655
  auto-attributed. Sources endpoint returns L010 + bbox
  [40,266,474,281] + doc sha256 per row - full number-to-source
  proof chain live.
- Step 3 live-caught defects (both red/green fixed, deployed):
  (a) FNB parsed the `Statement Period : ...` line as a txn (R31/
  R2023 garbage -> exception); all 3 bank parsers now skip
  `Statement Period|Date` framing (79d3bb2, 3 tests).
  (b) FNB desc-strip fused descriptions (`SHOP A` -> `SHOPF100.00-`)
  because the loose amount regex matches inter-word spaces and
  `replace(' ','')` stripped everything; digitless matches now
  filtered (5e8d3ad, 2 tests; STDB immune by construction, ABSA
  already filtered).
- Bank-gate test rewritten to its true contract: it passed only via
  the whitespace parse crash (FNB dates DO match DD/MM/YYYY); now
  pins right-parser-right-values on valid rows + fall-through on
  unparseable lines. Learning 66.
- Open findings (next todos, not this fix): FNB yearless dates
  default to current year (generic engine uses Period year
  correctly); ABSA bare `AMT BAL` pairs fuse in its tokenizer
  (paren shape works); one full-suite order-flake seen
  (trial-422 test failed once, green on re-run + in isolation).
