# FIX: Intake Forensic (verify + tamper + overlap + card tags)

## Goal (edited per owner)
One subscription = one subscriber + ALL their accounts: bank accounts,
credit cards, garage cards, family cards. Tenant = subscriber
(usage-metered). Account number = books + privacy boundary. A family
card number IS an account number: own books, own packs, hand it over
without handing over yours. Statements arrive per card number and are
filed under the asserted number; no card-tag concept.

## Confirmed picks
- Whole-tenant downloads stay available (subject-access right); every
  download is scope-labeled and multi-account tenants get warnings.
- Overlap: warn + persist new rows + flag. Never block, never silent.
- Upload account field stays optional; lenient validation only
  (6-16 digits after stripping spaces).

## Steps
1. [x] Intake bank-statement gate: non-statements 422 with verdict
   instead of silent exception; low-confidence uploads flagged
   needs_review. Response + docs list carry the verdict.
2. [x] Tamper wired: full_tamper_check in worker, verdict stored per
   doc, Inbox badge, GET /v1/documents/{id}/verification.
3. [x] Overlap honest: near-duplicate check pre-persist -> NDUP flag +
   warning + audit; known-account skip counter -> DUP-SKIP flag +
   warning + audit instead of silent continue.
4. [x] Guardrails: multi-account manifest + UI warnings; privacy copy
   (one login = one subscriber's finances; per-account packs for
   sharing; each card number is its own account).
5. [x] Re-verify + commit + deploy + live smoke.

## Live evidence (API e8a5a6bc + web a69b9db0, both SUCCESS)
- Invoice PDF upload -> 422 "not a bank statement (confidence 25%,
  invoice)" with verdict, no row, no quota.
- Statement CSV -> 200 with verification conf 0.625, needs_review
  false, asserted stored.
- Overlapping second CSV same account -> NDUP flag (5 of 6 overlap
  live_a.csv) + DUP-SKIP (skipped 5) + audit rows, only new rows kept.
- Verification endpoint combines gate + tamper + attribution live.
- Live-smoke catch (fixed e5dfea2, pinned): CSV pages carry
  width/height None and .get(key, default) returns the None ->
  TypeError killed every CSV tamper verdict silently (class-only log).
  None-safe dims + bbox; metadata-stage logs now include messages.

## Evidence
- Step 1 `tests/test_intake_verification.py` 3 passed (red-first):
  invoice 422 + no row + no quota, statement verdict conf>=0.5 in
  response + docs list, gray CSV needs_review. Migration
  source_documents.intake_verdict_json (both backends).
- Step 2 `tests/test_tamper_wired.py` 3 passed (red-first): processed
  doc carries verdict, appended-revision PDF flagged not-original with
  /Prev+EOF indicators via verification endpoint, cross-tenant 403.
  Fixed live bugs: per-doc audit prev-chaining (mathematically wrong
  on a per-tenant chain) -> per-row recompute; metadata skipped for
  non-PDF bodies (content sniff, vault suffix lies); visual text from
  pages; None-safe line join.
- Step 3 `tests/test_overlap_warning.py` 2 passed (red-first): 5+1
  overlap -> NDUP flag naming oct-a.csv + DUP-SKIP skipped=5 + 2
  audit rows; unknown docs never false-positive. persist returns
  counts; flag_links composite conflict target added + pinned.
- Step 4 `tests/test_pack_warnings.py` 2 passed (red-first): 3-account
  tenant warns in both manifests, single account silent. UI: tamper +
  needs_review inbox badges, scope label + share warning on reports,
  receipt needs_review hint, privacy copy both files.
- Full suite 310 passed, tsc 0, secret-print grep 0 new.
- Fixture updates (assertions untouched, bytes made statement-like
  for the new gate): test_upload_dedup_tenant, test_upload_restore.
- Found, not fixed (out of scope): _looks_csv uniformity breaks on
  one ragged preamble line (title rows kill CSV parsing).
