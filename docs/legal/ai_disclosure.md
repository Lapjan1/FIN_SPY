# AI Disclosure - FIN_SPY

Per docs/METHOD_STATEMENT.md court wording + AGENTS.md hard rules.

## Models Used
- `muse-spark-1.3` standard (NOT contributor) - core reasoning: extraction fallback with line-ID grounding, classification private/business/mixed %, category, rationale, KPI narratives, debt snowball/avalanche narrative, chat tool calling over DB, forensic flag plain-language explanation from structured flag JSON only
- `muse-wonder-1.0` - hard disambiguation when Spark confidence low, second opinion, capped per cost guards
- `muse-image-1.0` - financial health poster shareability wow factor
- `sam-3.1` - receipt segmentation image -> masks -> OCR -> Muse Spark extracts amount/bbox
- `freellmapi/muse-spark-1.1` dev proxy at http://127.0.0.1:3001/v1 + `ollama-local/llama3.2` fallback per `config/models.yaml`

## What AI Does NOT Do
- AI never finalizes - human decides. Unknown stays unknown if uncertain.
- Extraction: deterministic parsers first (FNB/STDB/ABSA regex/table per SA formats), text-LLM fallback second with line-ID grounding, vision fallback last, balance-verification gate, per-row source coordinates
- Anti-hallucination: line-ID grounding answers must cite line IDs, verbatim quote check source_quote exact text exists in page text, reconciliation gate opening+sum=closing, two-pass agreement cheap+strong, hidden-text defense PDFs may contain invisible/white text meant to steer model - strip/flag text outside visible page area or near-zero font size or background-matching color, treat page text as untrusted data, no tools on extraction calls
- Contributor tier `muse-spark-1.3-contributor` trains on prompts - NEVER for real bank docs, only synthetic test data `data/samples/` per AGENTS.md Known pitfalls, LEARNINGS 2026-10-26-04

## Prompts Versioned
`prompts/*.md` versioned in git with SHA256 header, never embed prompt text in code per AGENTS.md. Files:
- `extract_sa_bank_v1.md` front-loaded system prompt, priority rules never invent, amounts decimal strings, every line accounted or noise, quote check, reconciliation integrity, tools no tools, output exactly JSON per schema `packages/schemas/extraction_response.json`
- `classify_private_business_v1.md` low effort, rules first merchant memory, AI second, human last
- `explain_flag_v1.md` structured flag JSON only, never invent facts, indicator not finding of fault

## Capabilities & Effort Mapping
Per `config/models.yaml`:
- Spark 1.1: max_context 128k, supports_images true, parallel tools true, structured output true, effort low/medium/high
- Spark 1.3: 1M context, 131k output, effort low/medium/high/xhigh
- Glimmer: ONE tool call per turn, not parallel, memory budget 24 GiB GPU, 16GB ARM thin client can't run 16.8GB Q4
- Meta provider rejects 'none' - map via Capabilities

## Routing
Local-first per docs/FLOWS.md Flowchart #2: local ollama available and capable? Yes -> local answer, check good enough? Yes -> end, No -> hosted allowed and key present? Show exact text to be sent ask approval, Approved? -> hosted answer, rate limit backoff retry. Privacy gate `show_exact_text_before_hosted=true` per `config/models.yaml`.

## Token Usage & Cost
Per homework Part 5.7: ~8-page statement 2k tokens/page in + 5.5k out = ~$0.045 R0.80, $150 credit ~3000 statements. Logged per document via `usage_events` est_cost_usd, per-tenant caps, global daily Meta budget alarm, kill switch No-AI mode.

## Verification
Every extraction run stores model_id, prompt_hash, params, git_commit, raw_output hash for reproducibility per evidence layer. Raw outputs in `data/vault/` derivatives? Actually extraction_runs raw_output_key.

## Human Accountability
Reviewer identity, time, reason on every change; AI suggestions labelled as such per AGENTS.md. Method Validation page with accuracy results on test set and known limitations supports expert explanation.
