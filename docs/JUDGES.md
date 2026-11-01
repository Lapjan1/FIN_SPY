# JUDGES.md - click FIN_SPY in 7 minutes (3-minute express in bold)

Live app: https://web-production-74f81.up.railway.app
Live API: https://finspy-production.up.railway.app (`/docs` for the API)
Video: (link added on submit day) - watch this first if short on time.

> Cold start: the free tier sleeps. First page load can take ~60s to wake.
> Everything after that is fast. This is a hosting tier, not the app.

## What this is (15 seconds)

Upload any South African bank statement, and every number is traced to the
exact highlighted line on the original (SHA256 vault + hash-chain audit),
books build themselves, and a spy finds leaks, subscriptions, and duplicates.

## Express path (3 minutes) - **do this much at minimum**

1. **Register** at `/account` with any email (trial: 20 uploads, no card).
2. **Upload** `FNB_synthetic_1.csv` from `data/samples/` at `/upload`.
   Watch the receipt: vault SHA256 + queued status.
3. **Dashboard** at `/dashboard`: totals, charts, leak score.
4. **Click any number** -> transaction grid -> the exact highlighted line
   on the source. This drill-to-proof is the whole product.
5. **Reports** at `/reports`: download the Excel workbook. If totals show
   0: Enable Editing, then F9 (live formulas - the file tells you too).

## Full path (7 minutes) - the rest of the marks

6. **Inbox** (`/inbox`): upload statuses, doc hashes, Retry on exceptions.
7. **Review queue** (`/review`): accept 2-3 private/business suggestions -
   each accept posts a balanced journal (watch Debits == Credits).
   Unsure items park in 9999 Suspense for the accountant.
8. **Books** (`/books`): switch personal/SME/mixed templates, read the
   trial balance per bank account.
9. **Debt** (`/debt`): snowball vs avalanche on your real surplus.
10. **Spy Chat** (`/chat`): ask "what subscriptions can I cancel?" -
    every number is cited to the ledger, never invented.
11. **Evidence pack** (`/reports` -> Evidence pack): originals + manifest
    + audit chain. Verify offline:
    `python scripts/verify_pack.py ./evidence-pack.zip`
    (recomputes every SHA256 vs the manifest).
12. **Help** (`/help`): the whole product in one page, written for a stranger.

## Where the hard parts live (for technical judges)

- Line-ID grounding + reconciliation gate (both directions):
  `apps/worker/parsers/extractor.py`, `prompts/extract_sa_bank_v1.md`.
- Money as int cents, never float; UTC stored, SAST displayed.
- Per-bank parsers (FNB/STDB/ABSA) + generic 95pc + Meta Spark fallback.
- Hash-chain audit: `apps/api/audit.py`, `GET /v1/audit/verify`.
- 370 tests + 5 golden: `pytest -q` (see `docs/HACKATHON_AUDIT.md`).
- Full commit history: `docs/GIT_HISTORY.md` (GitHub frozen, see below).

## Meta usage (for sponsor-track judges)

- `muse-spark-1.1` (dev) + `muse-spark-1.3` standard tier (prod) for
  extraction fallback and classification - never contributor tier on
  real documents. 100 RPM limiter + per-tenant fairness + no-double-
  charge retries at the choke point. Models in `config/models.yaml`,
  prompts versioned in `prompts/`.

## Code access

Primary: https://github.com/Lapjan1/FIN_SPY (account frozen at audit
time - if it is back, this doc is a bonus). Fallback, committed in-repo:
`docs/GIT_HISTORY.md` (full 87-commit graph + stats) plus the
`FIN_SPY-backup-*.bundle` images on the submission drive.
