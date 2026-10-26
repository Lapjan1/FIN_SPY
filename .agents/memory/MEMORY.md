# Memory Index - Facts Only, No Secrets, No Imperative AI Instructions

- [Learnings](../../LEARNINGS.md) - mistakes and fixes; read before debugging - includes clearmind weak SHA256, paystack timing, session secret bug, trial pages vs sessions
- [State](../../STATE.md) - where we are now (Working v0.2.0 DB+auth+paystack 12 passed, In progress privacy templates frontend auth extraction line-ID, Blocked META_API_KEY pending)
- [Plan](../../docs/PLAN.md) - purpose, I/O, 7 user tasks, constraints, done means -> /goal acceptance checks
- [Modules](../../docs/MODULES.md) - 12 module cards + dependency Mermaid, high cohesion low coupling
- [Flows](../../docs/FLOWS.md) - flowcharts Mermaid: intake->extract->reconcile->classify->post + agent loop + router + verification independent verifier
- [UI Spec](../../docs/UI_SPEC.md) - 6 screens, wireframes, control->function map, states, heuristics, /taste anti-slop
- [Troubleshooting](../../docs/TROUBLESHOOTING.md) - symptom->cause->fix lookup includes bcrypt, paystack timing, session secret, trial metering, SA amount parsing, cross-tenant isolation
- [Method Statement](../../docs/METHOD_STATEMENT.md) - court wording what we guarantee vs not, AI disclosure, retention, POPIA
- [Decision 0001](../../docs/decisions/0001-stack-fresh.md) - fresh build lean MVP DB-first, no FINSPIB import, dynamic COA per tenant
- [Decision 0002](../../docs/decisions/0002-clearmind-adapter.md) - clearmind pattern adapted: dual DB _translate, require_login FastAPI Depends, bcrypt not SHA256, trial pages 20/200/1000 vs 5 sessions, paystack timing-safe HMAC SHA512 raw body + idempotent webhook_events, fail-closed SESSION_SECRET, hash-chain audit
- [Auth Paystack Doc](../../docs/AUTH_PAYSTACK.md) - DB adapter dual, auth bcrypt upgrade, paystack initialize/verify/webhook timing-safe, plans, trial pages, privacy/legal TODO, deployment railway.json pattern, tests
- [AGENTS](../../AGENTS.md) - hard rules front-loaded, commands exact copy-pasteable, read first list, FINSPIB ban, DB-first, Decimal, line-ID grounding, lethal trifecta split, guardrails
- [Models](../../config/models.yaml) - capabilities spark 1.1/1.3 wonder image sam, routing local_first_hosted_on_approval privacy_gate show_exact_text_before_hosted true, cost guards per-tenant pages
- [Prompts](../../prompts/) - versioned with hash header: extract_sa_bank_v1, classify_private_business_v1, explain_flag_v1
- [Schemas](../../packages/schemas/) - extraction_response.json Appendix B line-ID grounding + manifest.json Appendix C evidence pack
- [Tests](../../tests/test_db_auth_paystack.py) - hash-chain, bcrypt $2b$, isolation, timing-safe, trial pages 20->15->None
- [Scripts](../../scripts/verify_pack.py) - independent verifier SHA256+TSA per Appendix D, generate_sa_statements.py synthetic SA banks FNB/STDB/ABSA
- [Clearmind Reference](../../../../clearmind-ai/) - reference project READ for design, never copied: database.py:6-87 dual, 103-205 tables, 308 SHA256 weak, 335-364 reset token, 566-573 trial, app.py:152-172 decorators, 63-360 paystack, templates/privacy.html POPIA - all patterns adapted with security upgrades
