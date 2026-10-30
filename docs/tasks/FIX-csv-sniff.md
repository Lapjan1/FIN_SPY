# FIX: CSV sniff tolerates ragged preamble lines

## Goal
Bank CSVs with title/preamble rows (e.g. "FNB Statement ...", "Opening
Balance ...") must still parse as CSV. Currently one ragged leading
line fails the uniformity check, the file falls to the splitlines
path, raw commas fuse amounts, and generic extraction finds nothing.

## Rule
Skip leading lines that are not table-shaped before the uniformity
check; require >=3 uniform data rows after the header. Behavior on
uniform files unchanged; behavior on PDFs unchanged.

## Steps
1. [x] Red test: titled CSV extracts rows.
2. [x] Green: preamble-tolerant sniff.
3. [ ] Full suite + commit + deploy + live smoke.

## Evidence
- `tests/test_csv_sniff.py` 4 passed (red-first): titled CSV sniffs
  True + extracts >=4 chained rows under a vault-realistic .pdf key;
  uniform CSV still True; prose still False.
- Rule: skip leading <3-cell rows, then require the uniform run to
  hold (same 2+/3+ bar). TXT-amount shredding guard preserved.
