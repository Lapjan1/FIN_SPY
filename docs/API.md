# FIN_SPY Books API - Day 4 endpoints

Auth: `X-User-Id: <id>` header (dev; session cookie in prod). All money in int
cents, never float. Errors: `422 Invalid parameters ...` on bad input,
`403 Cross-tenant access denied` across tenants, `401` without auth.
Every human write needs `reason` (kept forever in transaction_revisions +
hash-chained audit_log). Interactive schema at `/docs` when the API runs.

## Journal - apps/api/ledger.py

- `POST /v1/journal/post` `{transaction_id, category_id? | account_id?, nature?, business_pct?}` -> balanced entry `{id, lines, debits, credits, posted: 1}`. Outflow Dr expense / Cr bank, inflow Dr bank / Cr income, mixed 3-line split via 3300/7000/3210/3200. Unknown account -> 422.
- `GET /v1/journal/trial-balance?as_of=YYYY-MM-DD&entity_id=` -> `{lines[{code, debits, credits, net}], total_debits, total_credits, balanced, zero}`.
- `GET /v1/journal/entries?transaction_id=&limit=` -> full entries with lines + account code/name. Append-only history: originals, reversals, transfers, fresh posts.
- `GET /v1/journal/suspense` -> 9999 watchdog `{balance_minor, txn_count, oldest_age_days, unposted_confirmed_count/ids, thresholds {5%, 30d}, status ok|review, reasons}`. Counts only stuck money (per-txn 9999 net != 0).

## Classify - apps/api/classify.py + prompts/classify_private_business_v1.md

- `POST /v1/classifications/suggest` `{description, account_number, entity_kind?, amount_minor?, direction?}` -> `{nature, business_pct, category_id, rationale, source rule|ai|human, confidence}`. Rules-first merchant memory, AI-second acts rationale, human-last unknown -> 9999. Never finalizes.
- `POST /v1/classifications/decide` `{transaction_id, nature, business_pct, category_id, rationale?, reason*}` -> append-only classification `{id, supersedes_id, transfer_entry_id?}`. Auto-transfers the posted leg when the category changed (None when never posted); transfer failures record `transfer_error`, never block.

## Review queue - web at /review, thin client in apps/web/src/lib/api.ts

- `GET /v1/review-queue` -> `{transactions[{id, txn_date, description_raw, amount_minor, direction, status, fingerprint_sha256, account_number, original_filename, doc_sha256}], documents, count}`. Proposed/exception/needs_password only.
- `POST /v1/review-queue/{id}/accept` `{nature?, business_pct?, category_id?, rationale?, reason*}` -> `{status: confirmed, classification, journal_entry}`. Missing fields fill from suggestion; unknown parks in 9999.
- `POST /v1/review-queue/{id}/edit` `{description_raw?, txn_date?, amount_minor?, nature?, business_pct?, category_id?, rationale?, reason*}` -> `{revisions, updated_fields, classification, repost?, reverification?}`. Amount/date on posted txns reverse + repost atomically (rollback incl. fingerprint-collision 422); description-only and unposted edits post nothing. `reverification` re-runs opening/closing + running both directions over the affected chain.

## Audit + legal - apps/api/audit.py

- `GET /v1/audit/human-changes?from_utc=&to_utc=&actor_id=&transaction_id=&limit=` -> `{revisions[{field, old_value, new_value, reason, actor_email}], revision_count, journal_actions, journal_action_count}`. Newest first, bound params only.
- `GET /v1/audit/verify` -> `{audit_chain {checked, ok, bad_id, head}, vault_files {checked, ok, missing, mismatched}, intact}`. Recomputes SHA256(prev||payload) per row + rehashes vault files.

## Feedback - web at /contact, thin client in apps/web/src/lib/api.ts

- `POST /v1/feedback` `{category bug|bank-layout|question|other, subject 1..120, message 10..4000, document_id?, page_url?}` -> `{id, emailed}`. Authed, tenant-scoped; unknown document_id -> 404; 5 per user per hour -> 429. Persists first, then notifies ADMIN_EMAIL; reporter text never forwarded to any model.
