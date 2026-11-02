# RECAP Post-Day10 - Books-vs-Excel rands + 68/68 chain recall + FNB bare-Dr rule - 2026-11-02

Follow-up hardening after RECAP_DAY10. Built this round: workbook money unit fixed (rands, was minor ints), extraction recall 61 -&gt; 68/68 on live doc 33f19573 via six chain fixes (G1-G6), FNB bare-Dr sign rule implemented FNB-scoped (G7), synthetic fixtures made realistic, everything committed as f795f14. NOT done: ruff gate on this box (CI pending), `tests/fakes/2025-05.pdf` was committed as declared demo data, negative-balance display polish (R-51.14 cosmetic).

## What We Have Done

### 1. Workbook rands fix (books R100.00 vs Excel 10000)
- Root cause: `apps/api/reports.py` wrote `amount_minor` ints into workbook cells while the webapp divides by 100. Fix: `_rands`/`_rands_or_blank` converters + `#,##0.00` number format (`reports.py:842`) across Transactions/Journal/Trial_Balance/P&amp;L/BS/Summary/Private_vs_Business; headers renamed (`amount_minor`-&gt;`amount`, `Debits (minor)`-&gt;`Debits (R)`); Cover/Method/Dictionary reworded. SUMIFS kept live over converted values.
- Scope contract: workbook display unit is rands; DB/API/auditor CSV stay minor ints; PowerBI pack stays `_minor` (headers honest).
- `tests/test_excel_rands.py` (new): red `[0,10000]` -&gt; green `[0,100]`. Applied via byte-precise CRLF splice (37 replacements, edit_file cannot match CRLF).

### 2. Chain recall 61 -&gt; 68 (G1-G6, user row contract)
- User contract implemented: a date starts a row; row = signed amount + total; amounts sum-check against balances; dates non-decreasing top-bottom (and bottom-top check).
- G1 pair-pick: 3-token middle pair + ref-split (`56 300.00Cr`), tie-break `(diff, date, line, rank)`.
- G2 sequential + gap-fill chaining (pure order-free poisoned to 23/68, abandoned).
- G3 fingerprint gains `balance_after` + big-bang migration (same-day repeat amounts kept distinct); skip+warn on collision, never delete.
- G4 lowercase dr/cr; G5 `check_date_order` reported in gate but excluded from `overall_pass` (column-PDF emission order != chronological).
- G6 hint-gated overdraft re-sign (App Payment To=debit, From=credit, airtime=debit): L052+L066 placed, L053+L065 corrected via product void (`superseded-g6`) + re-extract, never direct DB edit.
- Real-byte repros ran amounts-only (no descriptions/filenames/accounts in probes); scratch in gitignored `.fin_spy_tmp/`.

### 3. G7 FNB bare-Dr rule (user mandate, FNB-scoped)
- Mandate: no +/- on FNB; `Cr` after amount = credit (+); bare = debit (Dr never shown). Other banks keep plain positives.
- Trace: worker passes `bank_hint="FNB"`, extractor resolved `detected-or-hint` but dropped it before generic; generic signed bare balances +ve at exactly 2 token sites (`_candidate_pairs`, `_first_money` abs).
- Implement: `banks.yaml` FNB `bare_means_dr: true` (`config/banks.yaml:34`) + truth-fixed flags (was `trailing_minus: true`, `cr_dr_suffix: false`); `_is_bare_money_token` (`generic.py:277`) + `_bare_dr_rule` fail-closed resolver; `parse_generic_lines(..., bank=None)` (`generic.py:674`); bank threaded at both extractor call sites (`extractor.py:261` detected_bank, `:448` detect-only so unclaimed docs never inherit the FNB default hint). Stamp stays "GENERIC" (intake-owned, follow-up).
- 5 new tests red-&gt;green for predicted reasons: G7a/a2/b `TypeError: no bank kwarg`, G7c legacy all-debit fallthrough, G7d `None is True`. G7b pins FNB-only (STDB/None legacy). G6b/G6c needed no retarget (bank defaults None).
- Fixture realism (data, not intent): cascade#1 +Cr; synthetic rewritten realistic-Cr; PyMuPDF y-origin inversion fixed (insert_text is top-left; y=750-descending stacked inverted) + PDF/html regenerated. Golden now exercises the cascade: `fnb_recon_fail -&gt; generic 5 chained`, gate pass.
- Fragility noted: `detect_bank_from_text` finds FNB in the demo doc but an "absa" substring is also present; FNB wins by YAML order (task doc step 8).

### 4. Commit f795f14
- 21 files, 1298+/187-: 17 modified + task doc + 2 test files + `tests/fakes/2025-05.pdf` (declared synthetic public demo bytes, user-cleared as committable). Secrets scan clean; junk (`None`, pytest residue, memory lock) excluded; no push.

## Evidence
- Focused (fresh, pre-commit): 26 passed = chain 18/18 (G1a/b, G2a/b, G3a/bc/d, G4, G5a/b, G6a/b/c, G7a/a2/b/c/d) + cascade 2/2 + golden 5/5 + excel-rands 1/1.
- Full suite: 266 passed, 123 failed; stash-vs-HEAD FAILED-set diff = **mine-only 0** (19 fixed = session's own red-&gt;green tests; 123 = 121 WinError 10013 socket + PAdES-socket + pristine-proven). One in-suite chain failure non-repeating, standalone 18/18 x2 (sandbox flake family).
- Live doc 33f19573 (`e2e_worker_again.py` + `check_statement_totals.py`): `generic 68 chained`, `gate pass=True`, `persisted=0 skipped=68` idempotent, totals EXACT MATCH 10/R21,735.74 + 58/R13,430.54, opening R3,400 + cr - dr = closing R11,705.20 diff R0.00, live 68 + rejected 14 (12 fiction + 2 superseded-g6).
- Commit: `f795f14 Extract: workbook rands + 68/68 chain recall + FNB bare-Dr rule`.
- Ruff: runner unavailable on this box (no module, uv store locked) - CI gate pending, unchanged.

## What We Have Learned
- 79-80: pair-pick tie-breaks + sequential-first chaining (order-free only as rescue).
- 81: sandbox sqlite CANTOPEN / WinError 10013 flakes are environmental - rerun, verify via suite, never chase code.
- 82: overdraft balances lose sign in text extraction - exact-only hint-gated re-sign.
- 83: bank reading conventions belong in `banks.yaml` deviations as structural opt-ins, resolved fail-closed, with cross-bank scoping tests - never parser defaults or if-bank hacks.
- 84: synthetic PDF builders must match their library's y-origin (PyMuPDF top-left vs reportlab bottom-left); probe L001/LAST after regen; golden#1 is the inversion regression test.
- (Full text in LEARNINGS.md 79-84; method in docs/tasks/FIX-68-vs-61.md steps 1-8 + Evidence.)

## Open / Next
- CI: ruff check + format --check + full gate (source of truth over sandbox).
- Intake-owned "GENERIC" stamp on FNB docs (cosmetic follow-up); `detect_bank_from_text` order-fragility ("absa" substring).
- Negative-balance display polish (R-51.14 truthful but ugly; FNB shows red/Dr).
- Continuation/wrapped multi-line rows remain single-line-only in generic v1.
