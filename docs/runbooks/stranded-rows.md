# Runbook: Stranded-Row Cleanup (P1-C)

Stranded rows = transactions with no path back to source evidence:
`document_id IS NULL`, or no rows in `transaction_sources` for the txn.
They break promise 1 (proof, not just numbers) and must be re-linked or
voided — never deleted (append-only books).

## 1. Find them (per tenant)

SQLite (MVP):

```sql
SELECT t.id, t.txn_date, t.description_raw, t.amount_minor, t.status
FROM transactions t
LEFT JOIN transaction_sources s ON s.transaction_id = t.id
WHERE t.tenant_id = '<TENANT>' AND t.status != 'rejected'
GROUP BY t.id
HAVING COUNT(s.span_id) = 0 OR t.document_id IS NULL;
```

Postgres (prod): same query; qualify schema if needed.

## 2. Decide per row

- Row matches a real statement line (re-uploaded doc exists) → re-link:
  1. `POST /v1/documents/{doc_id}/requeue` to re-extract the statement.
  2. If the re-run proposes the same fingerprint, accept the new row and
     void the stranded twin (step 3) with reason `duplicate of <new-id>`.
- Row is junk (fake/test data, mis-extract) → void it:
  `POST /v1/review-queue/{txn_id}/reject` with
  `{"reason": "stranded: no source line (<why>)"}`.
  Proposed rows flip to `rejected` with no journals; posted rows get
  mirror-image reversals. History stays visible (Q2).

Do both from the UI if you prefer: Transactions → select row → Void;
Review → Reject / void. Same endpoints, same audit.

## 3. Verify books after

- `GET /v1/journal/trial-balance` → `balanced: true`.
- `GET /v1/journal/trial-balance?account_number=<each>` → each balanced.
- `GET /v1/journal/suspense` → parked R0 (or explain the remainder).
- `GET /v1/audit/human-changes?transaction_id=<id>` → void revision present.

## 4. Record

Append the tenant, txn ids, decision, and trial sha to STATE.md. If a
stranded row came from the extractor (not test data), file it against
the generic engine with the statement's bank + page count.
