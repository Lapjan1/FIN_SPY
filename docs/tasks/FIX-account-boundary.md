# FIX: Account Boundary (exports scoped per account, intake attribution)

## Goal
Tenant = subscriber (one subscription, usage-metered). Account = privacy
boundary. No export may contain rows or originals outside its scope.
Uploads are attributed to an account at intake (user asserts, worker
verifies) so per-account exports can be trusted.

## Steps
1. [x] Evidence-pack + signed-pdf + POPIA accept account_number (+__unknown);
   manifests state scope honestly.
2. [x] Intake: upload takes optional account_number; worker verifies vs
   extracted number; mismatch surfaces; match stored.
3. [x] Reports UI: picker drives all six downloads.
4. [ ] Full re-verify + commit + deploy + live smoke.

## Evidence
- `tests/test_scoped_packs.py` 4 passed (red-first TypeError/KeyError):
  evidence originals/audit filtered + manifest scope, POPIA tables +
  originals filtered + manifest scope, signed summary txn_count scoped,
  whole-tenant default intact (scope null, 2 originals).
- `tests/test_intake_attribution.py` 3 passed (red-first): upload asserts
  new account (bank row auto-created, asserted stored), assertion wins
  filing + mismatch audited + visible as mismatch with extracted value,
  pre-extraction docs read user-only.
- Full suite 299 passed, tsc 0, secret-print grep 0.
- Migration: source_documents.asserted_account_number +
  extracted_account_number inline + _ensure_schema ALTER (both backends)
  + one-shot backfill of pre-attribution findings.
- Model correction: tenant = subscriber (one subscription, usage-metered);
  account = privacy boundary. All six downloads honor the picker.
