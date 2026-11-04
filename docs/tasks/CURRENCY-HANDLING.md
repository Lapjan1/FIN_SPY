# Currency handling: exponents + symbols on totals - task record

User call (2026-11-03, post-hand-in): totals carry no currency symbols
and zero-decimal currencies would misbehave. Flow: document -> red
test -> green implement. Pre-work in this turn: tag pushed, LICENSE
added (see Done).

## Done (evidence)

- Tag `hackathon-submit` on 37082ee, pushed to GitLab (remote
  `gitlab`, `origin` still suspended GitHub): `[new tag]
  hackathon-submit -> hackathon-submit`, ls-remote HEAD == main ==
  37082ee.
- `LICENSE`: proprietary, J A Jansen trading as FIN_SPY Group,
  hackathon submission carve-out, attorney-review note.
- Discovery: `transactions.currency TEXT DEFAULT 'ZAR'` exists
  (db.py:333) and is SELECTed, but no insert path sets it and every
  consumer hardcodes `/100` + `(R)` labels (reports.py:488 auditor
  CSV, reports.py:666 Excel, dashboard/debt/review tsx). Vibe
  Trading checked: tickers + quote floats only, no fiat module -
  nothing to borrow (Learning 88).

## Learned

- 87: a column in SELECTs is not a feature - check the writes.
- 88: verify-before-borrow on sibling projects (grep first).

## Plan (minimal coherent slice)

1. New pure module `apps/api/money.py` (stdlib only, no app
   imports): ZERO_DECIMAL set per ISO 4217 (BIF CLP DJF GNF ISK
   JPY KMF KRW PYG RWF UGX UYI VND VUV XAF XOF XPF; 3-decimal
   codes like KWD are follow-up), CURRENCY_SYMBOLS
   (ZAR R USD $ EUR € GBP £ NGN ₦ KES KSh GHS ₵ JPY ¥ ...,
   fallback = code itself), exponent(), minor_to_major() ->
   Decimal, major_to_minor() -> int, format_money() ->
   "R35,231.28" (symbol + US-grouped, deterministic; locale
   styling is follow-up).
2. Auditor CSV: `amount_rands` value via minor_to_major(row
   currency); add `amount_display` with symbol; keep the old key
   for importer compat.
3. Excel summary: "Debits (R)"/"Credits (R)" derive the symbol
   from a report currency param (default ZAR -> byte-identical).
4. Dashboard summary: additive `currency` field (no shape break).
5. Follow-ups (NOT this task): web tsx /100 + (R) labels,
   mixed-currency totals policy, locale grouping (spaces+comma).

## Steps

1. [x] Document: this file + learnings 87-88.
2. [x] Red: collection ERROR (no money module); importorskip
   first gave a false skip, hardened to a hard import.
3. [x] Green: money.py + 11 CRLF splices (auditor/Excel/
   dashboard) with uniqueness asserts.
4. [x] Verify: 14/14 green (8 currency + 6 menu),
   py_compile clean on all three touched files. Full API
   suite still env-blocked (pre-existing, unchanged).

## Evidence

- `uv run --no-sync pytest tests/test_currency.py
  tests/test_menu_structure.py -q`: 14 passed.
- `py -m py_compile apps/api/money.py reports.py main.py`: 0.
- ZAR output byte-identical by construction: same labels,
  same values (minor_to_major(x,ZAR) == x/100 as Decimal),
  new keys/columns purely additive (amount_display,
  dashboard currency).
- tsc not run: no web files touched.
