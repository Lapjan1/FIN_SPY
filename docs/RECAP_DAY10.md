# RECAP Day 10 — Promise Plan + Audit Fixes + 8.5 Closes (submit-ready)

Date: 2026-10-30. Baseline: `1779d45` (Day 9 close). Head: `3176043`.
Live: API `19965f33` + web `227b7516` (both SUCCESS, commit `f51ad5d` tree).
Suite: **275 passed**, 0 failed. `tsc`: exit 0. Live GUI audit: **44/44**.

## What we did (evidence per item)

**Promise plan P0+P1** (`9919715`, 57 files, plan `docs/PROMISE_PLAN.txt`):
- P0-A0 generic 95% extractor between bank parsers and LLM last resort
  (20/20 recall; LLM gets zero-row failure, never mock rows).
- P0-A byte-download wrappers; P0-B POPIA ZIP with originals (Q1 YES).
- P0-C/D/E/F: `/reports`, `/books`, `/debt` screens + trial-balance
  `?account_number` filter.
- P0-G reject/void via mirror-image reversals, history kept (Q2 YES).
- P0-H owner model/effort preferences, keys admin-only.
- P0-J dead report queue killed (sync + 422 on unknown kind).
- P1-A email wired (mock fallback live, Resend unverified); P1-B trial
  copy pages→uploads (meter counts `source_documents` rows); P1-C
  stranded-row runbook `docs/runbooks/stranded-rows.md`.
- Evidence: `docs/tasks/P0-*.md` + `P1-ABC-*.md`, each red/green.

**Audit fixes from the 44-check live GUI audit** (`docs/tasks/DEPLOY-gui-audit.md`):
- `0eca6ee` CSV/TXT/OFX text reader (upload accepted CSV, worker was
  PDF-only → RuntimeError, 0 rows).
- `4d8e72c` content-sniff dispatch (vault keys always end `.pdf`) + CSV
  shape sniff; `tests/test_text_upload.py` (4).
- `5f97b33` + Learning 57: duplicate-with-lost-bytes restores + requeues
  (`requeued: true`, no quota); `VAULT_PATH=/data/vault` volume env
  (volume was 0MB, app wrote ephemeral). Heals the user's `c681db6a` case.
- `f9a512d` Day-4 OSS research `docs/DAY4_OSS_SUGGESTIONS.txt` + 422 pins
  (`tests/test_invalid_params_422.py`) disproving the stale "500" claim.
- `fd4ebbd` doc-scoped fingerprints for unknown accounts + image uploads
  fail-fast 422 (no OCR yet).

**8.5 closes** (`f51ad5d`, `docs/tasks/FIX-8.5-closes.md`):
- DSN redaction (`redact_url`, 4 tests) — live logs show
  `postgresql://***@...`; grep proves 0 secret prints.
- `DEV_AUTH_ENABLED` gate + one-time WARN + README disclosure (Option A).
- Trigger-block skip — zero pg WARNs at boot.
- README Live Demo block (links, evidence, disclosure); email claim cut
  (live probe: `email.mock_sent`); privacy images→roadmap note;
  picker PDF/CSV/OFX parity.
- `docs/JUDGE_AUDIT.txt` re-verified at **8.5** (was 8.0).

## What we learned (new entries)

- 53: suggester must speak the active books; seed sentinel must be a
  template row (extraction bank row fooled COUNT).
- 54: dead-default LLM + duplicate-trap blocks all retries (led to
  restore+requeue design).
- 55: first-col-PK assumption + pg autocommit = partial garbage per retry.
- 56: SQL `--` comments reach the driver — `%` in a comment killed the
  `merchant_memory` CREATE on Postgres (POPIA export 500'd live).
- 57: vault path must be the volume mount; dedup must verify bytes exist.
- Cross-cutting: stale audits lie — the Day-4 note cited `50eae41`/130
  tests vs actual `c955037`/261; every claim was re-verified, two
  "bugs" (422→500, picker) were already fixed, one suggested fix
  (require known account) would have dropped rows and was rejected.

## Diff to main (Day 9 → now)

`git diff 1779d45..HEAD --stat`: **74 files, +4919/−155**, 11 commits
(`9919715` … `3176043`). Tree clean except user scratch:
`.agents/memory/.muse-memory.lock`, `pytest-of-dshan/`,
`tests/fakes/2025-05.pdf` (all untracked, left in place).
Remote `origin` untouched (frozen policy; Railway `up` is the deploy path).
Backup: `D:\FIN_SPY_backup_2026-10-30-0419` (7,128 files, ~528MB, at `c955037`).

## Left on the todo list

**Human clicks (cannot delegate):**
1. Rotate the Postgres credential in Railway (old URL is in old logs).
2. Record the 3-min demo video (`docs/VIDEO_SCRIPT.md`); host unlisted;
   link into README/hero/submission. Only remaining 8.5→submit gap.
3. Optional: set `RESEND_API_KEY` + verified domain to make email real.

**Parked (explicit go-ahead only, per owner):**
4. SHA stage cache `(sha256, pipeline_version, model_id)` — the actual
   speed/cost/offline saver. Half-day. Recommended if unparking one.
5. bbox 0-1000 normalization — highlight accuracy only, no speed/cost gain.
6. Postgres RLS policies — security depth; app-level isolation tested.
7. JWT sessions (Auth Option B) — half-day + migration; demo disclosure
   stands instead.

**Nits:**
8. Privacy page styling + upload page are fine; no open UI gaps from audit.
9. `tests/fakes/2025-05.pdf` is the user's unreferenced file — keep or
   remove at their call.
