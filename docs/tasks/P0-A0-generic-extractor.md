# P0-A0: Generic extractor + last-resort routing — DONE 2026-10-29

Goal: bank-agnostic SA extractor (>=95% recall) between bank parsers and
whole-statement LLM; LLM failure persists zero rows (folds P0-I, Q3 YES).

## RED (before)
`python -m pytest tests/test_extraction_generic.py` → 4 failed:
ModuleNotFoundError (no generic module), mock-rows assertion failing,
PDF test erroring. Test file written first, observed red.

Two design bugs found by the red phase and fixed before green:
1. Fixture used FNB-readable dates → FNB parser claimed 13/26 rows, so
   generic never ran. Fixed: ISO-dash mystery-bank fixture (FNB-blind,
   still realistic); format superset covered by normalizer unit tests.
2. Tokenizer fused adjacent bare amounts ("75.50 5,574.50" → one invalid
   token) and stole R from words ("SPAR" → "R 234,56"). Fixed: thousands
   -aware space rule + R word-guard. Recall went 13/20 → 20/20.

## IMPLEMENT
- NEW `apps/worker/parsers/generic.py`: SA date/amount/balance line
  patterns + running-balance chaining; only validated rows kept.
- `apps/worker/parsers/extractor.py`: routing bank → generic → LLM;
  llm except branch returns rows=[] + loud warning (was: 2 mock rows).
- Tests updated per approved Q3: `test_llm_fallback_mock`,
  `test_llm_fallback_resolves_when_unset`,
  `test_llm_fallback_accepts_tenant` (zero-row expectations).

## GREEN (after)
- `pytest tests/test_extraction_generic.py` → 5 passed (20/20 recall,
  routing, zero-row failure, PDF end-to-end with LLM hard-disabled).
- Full `pytest tests` → 232 passed (incl. golden, bank-gate, e2e).
- Gates: ruff/pyright unavailable offline (not run, recorded); tsc N/A
  (no web touched); live smoke at deploy gate.

## LIMITS (v1, documented in module)
Year-bearing dates only; needs balance column to chain; single-line
rows; amount-then-balance order. Misses fall to LLM, then human review.
