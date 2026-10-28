# TROUBLESHOOTING.md - Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| `unknown model architecture: 'muse-glimmer'` in llama.cpp | Build too old b10353+ required | Upgrade llama.cpp release, check meta-models org, see LEARNINGS |
| Every sandboxed shell command fails in CI | bubblewrap missing + non-musl build needed on Linux, fail-closed correct | Fix runner image, apt install bubblewrap, use glibc image |
| `malformed settings file` at Muse Code startup | settings.json missing schema_version 1 | Add `"schema_version":1` |
| Hooks not firing startup warning | malformed .claude/hooks.json | Fix JSON, start NEW session |
| Whole run aborts required MCP server failed | MCP mode required fails whole run | Fix server or set optional, check inventory /mcp |
| Row accuracy <99% golden | Hidden text white/0pt or scanned page no OCR | Enable hidden-text detector, route to OCRmyPDF, check line-ID quote validation |
| Reconciliation fail opening+sum != closing | Sign reversed Cr/Dr suffix, space thousands, comma decimal SA formats | Check money parsing SA: R prefix, space thousands, 1 234,56 comma, (450) negative, Cr/Dr; fix parsers |
| Cross-tenant read succeeded | RLS not enforced, app uses service key | Test uses restricted role per-tenant + set tenant per tx, REVOKE UPDATE/DELETE from app role on append-only, run isolation test |
| Meta rate limit 429 100 RPM | No global limiter, queue burst | Add token bucket global limiter + per-tenant fairness + retries exponential backoff, cap worker concurrency |
| Secret committed git log -p shows META_API_KEY | Key in .env committed or log printed | REVOKE key NOW, rotate, git filter-repo or BFG not enough (assume compromised), add gitleaks pre-commit block |
| Contributor tier used for bank PDF | Cheap but trains on prompts | Switch to standard tier muse-spark-1.3, contributor only synthetic test data, check model id |
| Supabase free project paused | Free pauses after 1 week idle | Add uptime ping Cron or upgrade Pro $25/mo |
| Paystack webhook signature_ok false | x-paystack-signature verify raw body HMAC SHA512 with secret, not JSON parsed body | Use raw body bytes, constant time compare, idempotent processed_at guard |
| PDF highlight bbox wrong | Page width/height mismatch, rotation | Normalize bbox to page width/height * scale, consider page rotation from PyMuPDF |
| `pytest` fails only from non-repo dir | canonical.py not packaged, repo root not on sys.path (FINSPIB anti-pattern) | This repo keeps all modules packaged in apps/api|worker, no repo-root import, add tests/test_import_is_packaged |
| Muse Code ignores AGENTS.md | Workspace not trusted | Trust workspace after reading AGENTS.md/CLAUDE.md/.claude/hooks.json/.agents/skills/.agents/memory |
| Agent summary says done but diff empty | Agent invented tool result | Evidence before synthesis rule - require file read + test output, use FakeModelClient for tests |
| WARN dedup unique-index migration failed | Duplicate (tenant, account, fingerprint) rows predate enforcement | Find via GROUP BY tenant_id, account_number, fingerprint_sha256 HAVING COUNT(*)>1, merge manually, re-run init_db |
| Edit succeeds but trial unchanged | Edit touched description only, or txn unposted (repost only fires on amount/date of posted txns) | Check response.repost; description-only edits post nothing by design |
