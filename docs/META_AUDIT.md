# META Audit - Is everything that needs to be META meta?

Per competition rules: Build with Muse Spark series, Wonder, Image, SAM 3.1 via Meta Model API, open-weights via Baseten/Modal, Muse Code. Startup track judged on technical execution + production readiness + effective Meta use.

## What Should Be META (per README + AGENTS.md + config/models.yaml)

- Extraction fallback: Muse Spark 1.3 standard with line-ID grounding, structured output, refusal/unknown allowed
- Classification: private/business/mixed + category + rationale
- KPI narratives + debt snowball/avalanche narrative
- Chat tool calling over DB: search_transactions, explain_flag, debt_plan
- Forensic flag plain-language explanation from structured flag only
- Image generation: financial health poster for shareability
- SAM 3.1: receipt segmentation image -> masks -> OCR
- Muse Code: build accelerator (we use OpenCode with muse-spark-1.1)

## Current Status (2026-10-27) - Evidence

**META Ready:**
- `config/models.yaml` capabilities spark 1.1 max_context 128k supports_images parallel_tools structured_output effort low/medium/high, spark 1.3 1M context 131k output effort low/medium/high/xhigh, wonder, image, sam, llama3.2 fallback, routing local_first_hosted_on_approval privacy_gate show_exact_text_before_hosted true per docs/FLOWS.md Flowchart #2, cost guards per_document_token_ceiling 15000
- `apps/worker/llm/client.py` MetaClient complete(messages,tools,schema,effort) -> ModelResult content reasoning tool_calls usage, Capabilities, local_first_router() privacy gate show exact text before hosted, prompt_hash() SHA256 for forensic evidence_run, provider freellmapi http://127.0.0.1:3001/v1 dev muse-spark-1.1 + ollama http://127.0.0.1:11434/v1 fallback + meta_official https://api.llama.com/compat/v1 muse-spark-1.3 standard NOT contributor contributor trains on prompts NEVER
- `prompts/` versioned with SHA256 header never embedded in code per AGENTS.md: `extract_sa_bank_v1.md` front-loaded system prompt priority rules never invent amounts decimal strings every line accounted or noise quote check reconciliation integrity no tools output exactly JSON per schema, `classify_private_business_v1.md` low effort rules first merchant memory AI second human last, `explain_flag_v1.md` structured flag JSON only never invent facts indicator not finding of fault
- `packages/schemas/extraction_response.json` Appendix B line-ID grounding + `manifest.json` Appendix C evidence pack
- `apps/web/src/components/settings/MetaModelSelector.tsx` pure Meta models list spark 1.1 freellmapi spark 1.3 meta_official wonder image sam 3.1 llama3.2 ollama-local, capabilities max_context, cost est $0.045 per 8p $150 credit ~3000 statements, contributor warning, badges freellmapi active green + meta pending warning yellow per STATE.md Blocked

**META Mock / Not Yet Real:**
- `apps/worker/parsers/extractor.py:115` `llm_fallback()` builds numbered lines Lxxx Page bbox text + prompt file but returns mock rows `ExtractedRow line_ids L001 date 2026-10-26 description LLM Fallback Mock amount 10000` with warning `LLM fallback mock - implement real Meta call` - not yet calling `client.complete(messages, response_schema, effort="medium")` + validate schema + quote exists
- `apps/worker/parsers/fnb.py` deterministic only FNB, STDB/ABSA parsers per 25+ adaptors reference not yet
- `apps/api/main.py` `/v1/chat` returns mock answer `Mock: Your Woolworths spend R1200...` not real tool calling, `/v1/debt/plan` only mock ordering not interest saved calc
- Image generation + SAM 3.1 not yet wired - stretch per timeline Day8, cut rule if slip core forensic loop untouchable

**META Usage Proof for Submission (currently):**
- README Meta model matrix table Spark 1.3/Wonder/Image/SAM3.1 + adapter path `apps/worker/llm/client.py` + `config/models.yaml` routing local-first
- Prompts versioned with hash header
- Git commits during Oct26-Nov4 window evidence of Meta build: 11 commits `git log --oneline` 771812d initial, 1770fe8 scaffold, 2a49ac6 DB+auth+paystack, 98b069d docs hackathon grade, 28bc951 privacy templates POPIA, fce4747 Settings UI Meta pure, 98a21e0 red tests, 1f99344 intake capabilities, 03d0279 web JSX escaping, ab663a6 public not found, a513a6c Day2 extraction line-ID grounding, 3f2a8e6 encrypted PDFs, 1f99344 intake, 8e259f2 web Dockerfile, 66445dd email service, 1f99344 intake tamper, a513a6c Day2 extraction, 3f2a8e6 encrypted, plus `ab663a6..1f99344` etc - all during window
- Tests 62 passed including 25 red that ensure fails for right reasons per AGENTS.md evidence before synthesis
- .env.example names only no secrets, .gitignore data/vault/ data/*.db .env, banned imports no FINSPIB/FNBP via CI
- But actual Meta API calls not yet in production path - need to wire real calls before final video Day9

**Gap to be fully META meta:**
- Wire real `client.complete()` in `llm_fallback()` with structured output validation + quote check + reconciliation gate + token logging `usage_events` est_cost_usd per Part 5.7 ~$0.045
- Implement `classify_private_business_v1.md` via `client.complete()` when merchant memory misses, with rationale source=ai confidence
- Implement chat tool calling: `search_transactions`, `explain_flag`, `debt_plan` via Spark parallel tool calls
- Implement Wonder second-opinion path on low-confidence extractions (capped)
- Implement Image poster generation via `muse-image-1.0` for shareable financial health report
- Implement SAM 3.1 receipt segmentation for DocumentSpy stretch

**Plan to make fully META meta before submit Nov4 12:00 SAST buffer:**
- Day3 extraction quality: wire real Meta call + schema validation + golden tests `pytest tests/golden -v` 99% accuracy + 100% reconcile
- Day4 books: add classification AI suggestion via Spark low effort
- Day6 dashboard + chat: replace mock chat with real tool calling
- Day8 Meta depth + wow timeboxed: Wonder + Image + SAM 3.1

**Evidence of learnings with date:**
- LEARNINGS.md 14 entries 2026-10-26-01 to 14 with Symptom/Cause/Fix/Applies when, e.g., 09 Web build JSX escaping -> and {{{{ fixed → and {'{{'}} {{'}}'}, 10 Railway deploy uvicorn not found + email-validator missing fixed requirements.txt + python -m uvicorn, 11 Railway sleep uptime ping Cron, 12 Encrypted PDF handling, 13 Intake classifier duplicate tamper, 14 Extraction line-ID grounding reconciliation gate review queue
- STATE.md updated to v0.6.0-intake-tamper-extraction with Working 6 commits, In progress privacy frontend extraction, Blocked META_API_KEY pending, Next 3 steps
- CHANGELOG.md v0.6.0 with date and evidence per commit

**Conclusion:** Foundation is documented with date and evidence (git log, file:line, SHA256, test counts), learnings documented, but not yet fully META meta - extraction fallback still mock, need real Meta calls for hackathon grade Startup track. Next slice should wire real Spark 1.3 call.
