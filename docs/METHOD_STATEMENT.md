# METHOD STATEMENT - Court Wording

**Product:** FIN_SPY Financial Surveillance & Peak Insights  
**Version:** See git commit SHA in report footer + manifest.json  
**Date:** Generated at UTC per report, display Africa/Johannesburg

## What We Guarantee
- Original documents preserved byte-for-byte, SHA256 computed server-side on receipt, content-addressed key = SHA256, never overwritten, immutable storage, derivatives separate with derived_from link.
- Chain-of-custody: authenticated user, UTC time, IP, user agent, filename, size, MIME recorded in append-only audit_log with prev_hash/row_hash SHA256(prev||canonical_json).
- Traceability: every transaction row cites >=1 source_spans with page_no, line_id, bbox x0y0x1y1, text, text_hash. Transaction -> spans -> page -> document SHA256.
- Reproducibility: every extraction run stores pipeline_version, git_commit, method deterministic|llm|vision, model_id muse-spark-1.3, prompt_id+sha256, params, raw_output_key+sha256, start/finish UTC, reconciliation pass|fail|na, opening/closing minor.
- Validation: schema validation, line ID exists, amount Decimal parse exact, dates valid monotonic, reconciliation opening+sum=closing, running balance monotonic, page coverage every line accounted or noise, duplicate fingerprint SHA256(date|amount|desc_norm), hidden-text detection, quote verbatim check source_quote exists in page text.
- Human in the loop: AI proposes, human confirms. Each edit = new revision with reason, actor_id, at_utc, old->new, never overwrite. Court-report inclusion requires status confirmed or exception noted.
- Audit: append-only, RLS deny update/delete from app role, triggers reject, periodic export to off-platform, daily anchor hash chain head -> RFC3161 TSA (FreeTSA/DigiCert, free no SLA, prod qualified TSA roadmap), tokens .tsr stored.
- Reports: Excel live SUMIFS, not tamper proof - integrity anchor is signed PDF + manifest SHA256 printed in PDF footer + QR verification page that shows expected SHA256.

## What We Do NOT Guarantee (AI Disclosure + Limitations)
- "Court-ready" means built to support admissibility and expert testimony under ECTA s15, NOT guaranteed admissible. Admissibility decided by court, needs witness who can explain method.
- AI use disclosure: extraction fallback uses Meta Muse Spark 1.3 structured output with line-ID grounding, low effort default, temp 0.2, schema enforced, refusal/unknown allowed ("unreadable" valid). Classification suggestions also AI second opinion. All AI outputs labelled source=ai, confidence, rationale. AI never finalizes.
- Limitations: OCR error rate on scanned/skewed, handwritten not supported, mixed language, multi-account PDF may need manual split, round-number heuristic is indicator not finding of fault, Benford requires sample size warning, debt strategies are calculation aids not financial advice (SARS deductibility need practitioner), private/business split needs professional review.
- Retention: tenant chooses per record type, commonly 5 years tax, 7 years company per SA anchors [VERIFY with accountant/attorney]. POPIA minimal collection, deletion + legal hold flag blocks deletion, deletion certificate hash list, non-personal audit skeleton may remain as law allows.
- Data residency: dev Railway EU approx, Supabase free region may not be SA [VERIFY]. POPIA cross-border s72 disclosure in privacy notice, roadmap AWS af-south-1 Cape Town.
- Cross-tenant isolation: tested via DB-level RLS, but tenant must enforce strong passwords + MFA.
- This document is engineering guidance, not legal/tax advice. Have attorney + registered accountant review report wording, retention, privacy notice, terms before charging real customers.
