# RECAP Day 6 Finish - Dashboard + Drill + Chat + Settings - 2026-10-28

Per docs/TIMELINE.md Day6: Next.js screens per UI_SPEC (KPI cards, waterfall, treemap, heatmap, subscription radar, ECharts cross-filter, drill transaction -> grid -> pdf.js bbox highlight via /v1/transactions/{id}/sources, Spark tool-calling chat over DB) + Settings UI for Meta models (done pre-Day6: settings page + docs/SETTINGS.md).

## What We Have Done (Oct28 - Day 6, three parts)

### Part 1 - Drill backend (the outage)
- FOUND + FIXED outage (LEARNINGS 31): worker read stale gate keys `gate["opening_closing"]`/`gate["running_balance"]` while reconcile returns `*_top_bottom`/`*_bottom_top` - every upload since Day 2 ended (exception, None) and persisted NOTHING. E2E masked it with `if result:`. Worker now reads the four real keys; drill tests assert non-None unconditionally.
- Real grounding persisted: `extract_document` attaches pages; `persist_to_db` writes one span per cited line with true bbox + page_width/page_height (new cols + `_ensure_span_dims` migration for old DBs, sqlite/pg tolerant). Dedup check moved before span writes (no more orphan spans on dupes).
- GET /v1/transactions/{id}/sources: now returns dims + doc identity + honest `unlinked` state; mock L012 fallback removed; 404 on unknown txn (was silent 200).
- GET /v1/documents/{doc_id}/file (new): tenant-guarded vault PDF bytes for the viewer (404/403 covered).
- PRAGMA busy_timeout=5000 against threaded TestClient lock flakes.

### Part 2 - Chat real + pages
- apps/worker/spy/chat.py (new): 6 DB tools (totals, top_vendors, search, subscriptions, duplicates, fees), deterministic intent router with per-intent handlers, citations on every answer. Local model (freellmapi then ollama) may only rephrase supplied facts; mock responses detected and never surface; 1s TCP pre-check so dead models fail fast (16s -> ~1s per probe). Zero hosted calls, zero credit.
- POST /v1/chat: mock string replaced; tenant mismatch 403, empty user message 422.
- Pages /upload (file + optional password -> vault receipt), /inbox (docs + statuses), /chat (connect, cited answers with `via` model label). api.ts: fetchMe, postChat, uploadDocument, fetchDocuments, documentFileOptions, runSpy, fetchDashboard, fetchTxnSources, fetchFlags.

### Part 3 - Dashboard + drill UI + charts
- /dashboard (new): live KPIs (net, leak accent, burn/runway, savings), monthly ECharts bars, flow waterfall (in/out/net), vendor treemap (top 12), monthly heatmap (in/out/net intensity), subscription radar from SUB flags (top 6 R/mo), spy flags list + Run spy. All real data + empty states.
- /transactions (new): ledger list -> sources -> SourceViewer with real react-pdf render (authed httpHeaders) + bbox overlay normalized by stored page dims; unlinked + load-failure states.
- SourceViewer rewritten from placeholder; nav extended; home demo updated to new props.

### Tests + gates
- tests/test_drill_day6.py (4): real spans/dims/bbox persisted, sources shape + 404, unlinked + 403, file bytes + 403/404.
- tests/test_chat_day6.py (4): real R totals, subs + spend, 403/422 guards, empty tenant, tool edges.
- Suite 149 passed 0 failed; tsc 0; next build green (/dashboard 340kB, /transactions, /upload, /inbox, /chat); ruff clean on all new files.

## What We Learned
- LEARNINGS 31 (gate keys): catch-all + `if result:` e2e = silent total outage. E2E must assert the happy path ran.
- LEARNINGS 32 (tenant sweep): 15 endpoints collapsed all sqlite tenants into default-tenant via `isinstance(row, dict) else "default-tenant"`; one `_tenant_of` helper, repo-wide sweep with asserted counts, zero stragglers.
- LEARNINGS 33 (chat grounding): tools-first + mock detection + no-credit rule = chat that works offline and can never hallucinate numbers; fast TCP pre-check beats SDK retry waits.
- CRLF/LF mixed files break exact-match edits: regions never touched are CRLF; scripted replacement with asserted counts is the reliable path.
- react-pdf v9 works on React 18 (peer range includes it); authed PDF loads via `file={{url, httpHeaders}}`.

## Checklist vs plan (Day 6 honest)
- [x] KPI cards live [x] waterfall [x] treemap [x] heatmap [x] subscription radar [x] drill txn->grid->pdf bbox [x] chat over DB [x] settings (pre-existing) [x] upload/inbox pages (bonus, unblocks demo)
- [ ] ECharts cross-filter click-to-drill (charts display-only) - single remainder, stretch.
