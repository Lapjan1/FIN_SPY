# FIX: 68-vs-61 recall (order-free chaining + lossy-dedup + pair-pick)

## Goal

Statement claims 68 rows (10 cr R21,735.74 + 58 dr R13,430.54);
deterministic extraction persists 61. Proven accounting on the
working bytes (tests/fakes/2025-05.pdf, UNTRACKED, same SHA as doc
33f19573 - public demo data, not customer PII, committable):
68 candidates -> 5 dropped by exact sequential chaining -> 63 chained
-> 2 eaten by fingerprint dedup -> 61 persisted. The 12 rejected
fiction rows are unrelated (voided, runs 1-2 era tokenizer).

## User row contract (the spec this fix implements)

1. Every line starts with a date; a date starts a new row.
2. Every transaction is amount (+/-) plus running total.
3. Accrued amounts sum-check against balance movement
   (opening + sum = closing, both directions - the existing gate).
4. Table shape: Date | Description | Amount | Balance.
5. Row order rule: top-to-bottom, date == previous date or later;
   bottom-to-top, date == date or earlier. Violations are review
   flags, never silent drops.

Today's grouping already yields 68/68 candidates, so segmentation
satisfies (1) and is untouched. This fix implements (2), (4), (5)
in candidate pairing + chaining, keeps (3) as the arbiter.

## Bugs (all reproduced, amounts-only evidence)

- B1 lossy dedup: fp = SHA(date|amount|desc) has no balance, so
  same-day repeat R110 payments (L073/L074 bal 883.86/773.86,
  L078/L083 bal 308.86/123.86 - different lines AND balances)
  collide and one of each pair is skipped at persist.
- B2 3-token positional pick: amount=toks[-2], balance=toks[-1]
  misreads L081 [50.00, 258.86Cr, 4.40] as amount 258.86 /
  balance 4.40 (truth 50.00 / 258.86); L082 is cascade collateral.
- B3 ref+amount fusion: "56 300.00Cr" (L086) reads as R56,300
  though the R433.86 balance disproves it; row drops.
- B4 exact sequential chaining (`==`, zero tolerance) drops real
  rows at line-order jumps (L052 R150, L066 R2,500Cr); the gate
  itself tolerates R1.00 - inconsistent.
- B5 lowercase suffix: `parse_sa_amount` rejects `dr`/`cr`
  (case-sensitive endswith) after the regex accepts them.
  0 lines in this doc; latent.
- REJECTED G6 unicode-minus sign loss: census shows 0 U+2212 and
  no detached markers on L052/L065. Not the cause.

## Steps

1. [x] G1 pair-pick (generic.py): per line, candidate (amount,
   balance) pairs - last-two, middle-two (3+ tokens), ref-split
   of space-grouped amounts ("56 300.00Cr" -> "300.00Cr").
   First pair that chains wins; default keeps today's behavior
   on clean lines.
2. [x] G2 sequential + gap-fill chaining (generic.py): pass 1
   walks line order (pair-pick, R1.00 tolerance, date
   non-decreasing per user rule 5, balance resync on refusal);
   pass 2 inserts leftovers into chain slots (both sides
   linked, dates fitting) to a fixpoint. Leftovers ->
   unaccounted reason "unchained" (NEW, distinct from "noise")
   + per-row warning. (Pure order-free greedy tried first:
   spurious exact links poisoned the chain 23/68 - line order
   carries signal, keep it primary.)
3. [x] G3 fp includes balance: canonical
   `date|amount|desc|balance_after`, base.py + main.py wrapper,
   all call sites pass balance; big-bang migration recomputes
   stored fps (probe collisions first, skip+warn, never delete).
   AGENTS.md formula line updated.
4. [x] G4 lowercase suffix: case-fold Dr/Cr handling in
   `parse_sa_amount` (also kills the rstrip-charset accident).
5. [x] G5 date-order gate check: `check_date_order` in
   reconcile.py, reported in gate results, EXCLUDED from
   overall_pass (emission order != chronological on column
   PDFs; balances accept, dates flag).
6. [x] Green: focused red->green (10/10), full pytest (258
   runnable green; 123 failures all sandbox/pre-existing),
   golden 5/5, ruff UNAVAILABLE on this box (no module, uv
   store locked - CI gate pending); healed local vault bytes
   (identical-SHA copy, vault is gitignored) + worker
   re-extract of doc 33f19573; interim acceptance was 66 rows
   + 2 loud Unchained + gate exception on R2,220 gap -
   SUPERSEDED by G6 (68 + gate pass, see step 7).
7. [x] G6 signed chaining + money-flow hints (generic.py):
   overdraft re-sign (exact-only, hint-gated: To/debit,
   From/credit, airtime/debit); direction conflicts warn but
   plain links stand; settled rows re-link plain-only.
   L052+L066 placed, L053+L065 unflipped (old rows voided via
   product reject as superseded-g6), 68/68 + GATE PASS +
   doc proposed + statement totals EXACT (10/R21,735.74 +
   58/R13,430.54, diff R0.00).
8. [x] G7 FNB bare-Dr rule (user mandate 2026-11-02: no +/-
   signs on FNB; `Cr` after amount = credit (+); bare amount
   = debit (Dr never shown); FNB-SCOPED, other banks keep
   plain positives). Trace: worker passes bank_hint="FNB"
   (main.py); extractor resolves bank = detected-or-hint
   (detect_bank_from_text finds FNB in demo text:
   "fnb"+"first national"+"250655" present; NOTE "absa"
   substring also present - FNB wins by banks.yaml order,
   fragile) but DROPS it before generic (both call sites).
   Generic signs bare balances +ve at exactly 2 token sites:
   _candidate_pairs:374 (balance = parse_sa_amount) and
   _first_money:279 (abs! opening/closing forced +ve); chain
   helpers consume signed pairs, so NO threading needed
   there (_link_direction's resign branch never fires for
   rule-negatives: balance > 0 gate). Design:
   parse_generic_lines(..., bank=None) -> bare_dr via
   get_bank_config(bank).deviations.bare_means_dr
   (fail-closed False); _is_bare(tok) = no Cr/Dr/+-/parens;
   negate bare balances at both sites (amounts stay
   magnitudes - _link_direction does base +/- amount);
   band_rows gets bank (FNB header vocab, the designed path -
   68 gate proves no recall harm, else restrict to signing);
   extractor passes bank at both generic calls; stamp stays
   "GENERIC" (intake-owned label, follow-up). banks.yaml FNB
   truth-fix (cr_dr_suffix true, trailing_+/- false - flags
   consumer-less/doc-only, fnb.py reads only regex keys) +
   bare_means_dr: true; STDB (explicit Dr AND Cr) untouched
   so scoping is structural, not an if-bank hack. Fixture
   realism (test DATA, intent preserved): cascade#1 fixture
   +Cr (bare FNB positives impossible per rule);
   show_side_by_side.py both lines-lists -> realistic FNB
   (bare debit amts, Cr credits/balances/open/close) + regen
   synthetic PDF (untracked) + side_by_side.html (tracked).
   G6b/G6c need NO retarget (bank defaults None -> legacy;
   G6a's "FNB"-in-text fixture also unaffected - bank comes
   only from the param, never sniffed). RED predictions:
   G7a/a2 TypeError (no bank kwarg) then value asserts bite
   post-implement; G7b/None always green (guard), G7b/STDB
   TypeError->green (scoping proof); G7c None-or-all-debit
   (fallthrough yields legacy); G7d None is True.
   GREEN 2026-11-02: 5/5 red->green for predicted reasons;
   cascade#1 fixture +Cr (cascade intent kept); synthetic
   rewritten realistic-Cr + y-origin fix (PyMuPDF top-left:
   y=750-descending stacked the page inverted while the
   reportlab branch was correct; extractor ascending-y is
   top-first-correct) + regen PDF (untracked) + html
   (tracked); worker re-extract 68/68 IDEMPOTENT (persist
   0/skipped 68 - all positives Cr-marked, G6 overdraft fps
   stable), gate PASS, totals EXACT, live 68 + rej 14.

## Evidence

- tests/test_chain_recall.py 10/10 red->green (G1a/G1b/G2a/G2b/
  G3a/G3bc/G3d/G4/G5a/G5b), each red observed for the predicted
  reason before its fix.
- Real bytes offline repro: generic 63 -> 66 chained; leftovers
  exactly L052 (R150/51.14) + L066 (R2,500/2383.86) with
  per-row Unchained warnings; signed sum 586020 -> 608520.
- DB: doc 33f19573 live 61 -> 66 (+L081/L082/L086/L074/L083),
  rejected 12 untouched, worker E2E re-extract green
  (persist 0/skipped 66 idempotent, status exception correct).
- Full pytest: 258 passed; 123 failed = 121 WinError 10013
  socket + 2 PAdES-socket + 2 pristine-proven pre-existing
  (account_isolation teardown, sign assert) - zero regressions.
- Golden: 5/5. Ruff: runner unavailable (see step 6).
- Box caveat: sqlite CANTOPEN flakes under this sandbox
  (crash row moved 0 -> 14 across identical runs); product
  paths verified via suite + reruns. Learning 81.
- G6 close-out: 13/13 focused green (G6a overdraft stretch +
  gate pass, G6b hint-blocked resign, G6c conflict warn);
  real bytes 68/68 chained, signed sum 830520 = truth exact,
  zero warnings (all To/From/airtime hints agreed); worker
  re-extract persist 4/skipped 64, GATE PASS, doc proposed,
  live 68 + rejected 14 (12 fiction + 2 superseded flips);
  full suite 261 green, same 123 sandbox/pre-existing
  failures, golden 5/5. Learning 82.
- G7 close-out: 18/18 focused green (G7a/a2 FNB bare-Dr,
  G7b scope guard, G7c detected-threading, G7d config);
  cascade 2/2 (fixture +Cr), golden 5/5 (realistic-Cr
  synthetic, FNB-fail -> generic 5 chained, gate pass);
  full suite 266 green + 123 failed = mine-only 0 vs HEAD
  (19 fixed = session's own red->green tests; in-suite
  chain 1-flake non-repeating, standalone 18/18 x2);
  live re-extract idempotent 68 + gate PASS + totals EXACT.
  Learnings 83-84.
