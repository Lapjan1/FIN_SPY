# FIX: Duplicate-With-Lost-Bytes Restore + Vault Volume — Task Document

## Goal
User stuck on "already in your vault - no quota used" (sha `c681db6a…`,
127KB) with zero extraction, after several redeploys.

## Root causes
1. `VAULT_PATH` defaulted to `./data/vault` (ephemeral `/app/data/vault`)
   while the Railway volume sat empty at `/data/vault` (0MB used):
   every deploy wiped bytes, DB rows survived.
2. Duplicate re-upload rewrote the bytes but kept the old dead status,
   so the worker never re-ran.

## Implement
- `apps/api/main.py` `upload_document`: duplicate branch tracks
  `bytes_restored`; when bytes were missing and status isn't already
  queued, the row resets to `queued` + `document.restore_requeue` audit,
  returning `requeued: true` (still no quota used). Intact duplicates
  unchanged (no churn).
- `apps/web/src/app/upload/page.tsx`: receipt shows "file bytes were
  missing - restored, extracting again" when `requeued`.
- Ops: `VAULT_PATH=/data/vault` set on Railway FIN_SPY (Learning 57).
- Red first: `tests/test_upload_restore.py` (restore+requeue fails,
  no-churn passes) → green after.

## Green
- Focused: `test_upload_restore + test_upload_dedup_tenant + test_requeue`
  9 passed. Full suite: 261 passed, `tsc` 0. Commit `5f97b33`.
- Live: volume 0MB → in-use; probe upload 200 + 48 rows on deploy
  `14a9d9cc`; web `b86364f6` SUCCESS. User re-uploads once to heal.
