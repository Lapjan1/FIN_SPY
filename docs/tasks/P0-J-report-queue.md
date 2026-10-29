# P0-J: Kill Report Queue — Task Document

## Goal
D8: delete the dead report-job path. `POST /v1/reports` returned
`{"status": "queued"}` for every kind except powerbi, and nothing ever
consumed the queue — reports vanished silently.

## Red
New `tests/test_report_queue_killed.py` (2 tests): excel/auditor-csv/
evidence-pack/powerbi must return `ready` with file_key+sha256; unknown
kinds must 422, never `queued`. Both failed on the old code.

## Implement
- `apps/api/main.py` — `create_report` rewritten: known kinds
  (powerbi, excel, auditor-csv, evidence-pack, signed-pdf) generate
  synchronously via the same builders the GET download endpoints use,
  persist file_key/sha256 on the `reports` row, and return `ready`;
  `ValueError` (bad window, signing unconfigured) → 422; unexpected
  errors keep the old `failed` + error shape; unknown kind → 422 naming
  the valid kinds. Spliced via `.fin_spy_tmp/splice_queue*.py` (CRLF).
- Verified no web caller POSTs `/v1/reports`; remaining `queued`
  references are the live document-extraction queue (worker-consumed).

## Green
- `tests/test_report_queue_killed.py`: 2 passed.
- Full suite: 254 passed. (Mid-task the suite caught real pollution —
  the P0-H test leaked `trial_pages=50` into the global settings table
  and broke pinned `test_trial_pages`; fixed by save/restore in the
  P0-H test's finally block, then re-verified green.)
