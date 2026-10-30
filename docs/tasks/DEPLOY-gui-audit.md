# DEPLOY: First-Test-Run GUI Audit — Evidence

Script: `.fin_spy_tmp/gui_audit.py` (throwaway probe, not committed).
Live on API `d7a99c47` + web `8bb18690`: **44 passed, 0 failed**.

## Pages (16/16 HTTP 200)
/ /dashboard /transactions /upload /inbox /chat /review /books /debt
/reports /help /privacy /terms /refund /settings /account.

## Functional pass (fresh probe tenant, synthetic FNB CSV)
- register/login/plans 200; upload 200 queued.
- Worker: 48 transactions proposed in seconds.
- Review queue 48 → suggest `4000` → accept posts (confirmed) →
  trial balanced, debits R6,889.90 → reject voids second txn.
- Txn sources 200 with bbox proof; books select sme_cc round-trip;
  suspense ok; debt defaults from real ledger (4 months) + avalanche
  order Bank45,Card10; spy 8 flags; dashboard 200; chat answers from
  tools; prefs round-trip.
- Downloads with real bytes: excel 23,943b, powerbi 27,329b,
  auditor-csv 14,305b, evidence-pack 58,987b, POPIA ZIP 15,251b
  (all `PK`/header magic verified); sync `POST /v1/reports?kind=excel`
  → `ready`.

## Gaps the audit caught (all fixed, committed, redeployed)
1. CSV → PDF-only RuntimeError → text reader (`0eca6ee`).
2. Vault `.pdf` naming defeats suffix dispatch → content sniff (`4d8e72c`).
3. Duplicate + wiped bytes strands user → restore+requeue, volume env
   (`5f97b33`, Learning 57).
