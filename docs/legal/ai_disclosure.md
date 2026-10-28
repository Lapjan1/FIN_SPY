# AI Disclosure - FIN_SPY

This disclosure follows our method statement and product guardrails, and appears in summary form in every report.

## Models Used
- `muse-spark-1.3` standard edition (NOT contributor) - core reasoning: extraction fallback with line-ID grounding, private/business classification with rationale, KPI narratives, debt strategy narratives, chat over your books, and plain-language flag explanations written strictly from structured data
- `muse-wonder-1.0` - second opinion when Spark confidence is low, usage-capped by cost guards
- `muse-image-1.0` - financial health poster images
- `sam-3.1` - receipt image segmentation feeding OCR, from which Muse Spark extracts amounts and positions
- Development and fallback models: `muse-spark-1.1` via a local dev proxy, and local `llama3.2` via Ollama as the privacy fallback

## What AI Does NOT Do
- AI never finalizes anything - a human always decides. Uncertain items stay marked unknown.
- Extraction runs deterministic bank parsers first (FNB, Standard Bank, Absa, using SA number formats), then a text-model fallback with line-ID grounding, then vision as a last resort. Every run passes a balance-verification gate, and every row keeps its source coordinates.
- Anti-hallucination: answers must cite line IDs and pass a verbatim quote check (the quoted text must exist exactly in the page), plus a reconciliation check and two-pass agreement between a cheap and a strong model. Hidden-text defense: PDFs can contain invisible text meant to steer the model, so text outside the visible page area, near-zero font sizes, and background-matching colors are stripped or flagged. Page text is always treated as untrusted data, and extraction calls use no tools.
- The contributor tier (`muse-spark-1.3-contributor`) trains on prompts, so it is NEVER used for real bank documents - only for synthetic test data.

## Prompts Versioned
All prompts are versioned in git with a SHA256 header, and prompt text is never embedded in code. Files:
- `extract_sa_bank_v1.md`: extraction prompt with priority rules (never invent figures, amounts as decimal strings, every line accounted for or marked noise, quote check, reconciliation integrity), outputting exactly the extraction JSON schema, with no tool use
- `classify_private_business_v1.md`: classification prompt - saved rules first, AI suggestion second, human decision last
- `explain_flag_v1.md`: flag explanations written strictly from structured flag data, never inventing facts; flags are indicators, not findings of fault

## Capabilities & Effort Mapping
Current generation:
- Spark 1.1: 128k context, image support, parallel tools, structured output; effort low/medium/high
- Spark 1.3: 1M context, 131k output; effort low/medium/high/xhigh
- Glimmer: one tool call per turn (no parallel calls)


## Routing
Routing is local-first. If the local model is available and capable, it answers; if its answer is good enough, we stop there. Otherwise, and only if hosted use is allowed, we show you the exact text to be sent and ask approval before calling the hosted model, with backoff and retry on rate limits.

## Token Usage & Cost
An 8-page statement uses roughly 2k input tokens per page plus 5.5k output tokens, about $0.045 (R0.80); a $150 credit covers roughly 3000 statements. Cost is logged per document with per-account caps, a global daily budget alarm, and automatic fallback to No-AI mode.

## Verification
Every extraction run stores the model ID, prompt hash, parameters, code version, and raw-output hash for reproducibility.

## Human Accountability
Every change records the reviewer's identity, time, and reason, and AI suggestions are always labelled as such. A Method Validation page publishes accuracy results on the test set with known limitations, to support expert explanation.
