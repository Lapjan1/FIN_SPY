# Hackathon audit - 2026-11-01 (commit 3c95772)

Track: startup (indie creativity + production readiness).
Method: every claim below has a proof pointer (command, file, or live URL).
Verdict: **81 / 100**. P0 todo closes video + repo access for ~+12.

## Score

| Area | Max | Got |
| Demo live | 20 | 18 |
| Meta AI depth | 15 | 12 |
| Forensic proof | 15 | 14 |
| Books correct | 10 | 9 |
| Billing SaaS | 10 | 8 |
| Tests quality | 10 | 8 |
| Docs | 10 | 9 |
| Submit pack | 10 | 3 |
| Total | 100 | 81 |

## Evidence per area

- Demo live (18): API dep d22b06d6 + web dep ef7e6802 SUCCESS,
  `/health/ready` pg, `/` 200, web `/` + `/help` 200 (probed live).
  Minus 2: `web_ui` env points at API host; no seeded judge walkthrough.
- Meta AI depth (12): Spark 1.1 dev + 1.3 prod real calls, line-ID
  grounding (`prompts/*.md` versioned), 100 RPM limiter + per-tenant
  fairness, chat tool-calling. Minus 3: Wonder/Image endpoints exist
  but zero live calls; second-opinion hookup deferred (STATE).
- Forensic proof (14): SHA256 vault, hash-chain audit, bbox grounding,
  reconciliation both directions, evidence pack + `scripts/verify_pack.py`,
  TSA + PAdES. Minus 1: verifier demo never recorded.
- Books correct (9): post/trial/repost/suspense/9999, balanced enforced,
  Decimal-only money, 370 tests. Minus 1: no P&L/BS endpoints; Excel
  zero-cache mitigated with notes (3c95772) not values.
- Billing SaaS (8): test-mode proven end-to-end 2026-11-01 (both plans,
  Paystack-side verify, audit mapping). Minus 2: live KYC pending;
  X-User-Id dev auth (JWT is roadmap).
- Tests quality (8): 370 passed, golden 5, tsc 0. Minus 2: ruff 180
  pre-existing findings; `pyright>=1.15` spec bug breaks `uv run`.
- Docs (9): PLAN/MODULES/FLOWS/UI_SPEC/ADRs/day-recaps/78 learnings/
  legal set/method statement. Minus 1: README flow has no shot list.
- Submit pack (3): 87 commits in window, hero flow scripted. Minus 7:
  NO video file; GitHub frozen, 49 commits unpushed.

## Todo

P0 - submission blockers:

1. Record 2-3 min hero video per README flow (no file exists today).
2. Resolve GitHub frozen / push 49 commits (judges need code access).
   Fallback story: bundle + Railway + live URLs.
3. Judge click-through on a clean machine: register, upload synthetic
   statement, review, dashboard, Excel (F9), evidence pack, run
   `verify_pack.py` on the download.

P1 - cheap polish:

4. Excel pre-computed cached values + P&L/BS endpoints (kills F9).
5. Loud failure on unparseable PLAN_CODES_JSON (learning 76).
6. Fix `pyright>=1.15` to a real 1.1.x bound (one line, unblocks gates).
7. Point `web_ui`/APP_BASE_URL at the web domain.
8. Railway var cleanup: proper `PAYSTACK_PUBLIC_KEY`, drop the typo
   and duplicate secret vars.
9. Decide `tests/fakes/2025-05.pdf` + stray `None` file: commit or delete.

P2 - bonus (below).

## Bonus suggestions

- 60s `verify_pack.py` terminal clip inside the video (independent proof).
- Seeded demo tenant + one-page JUDGES.md click script with the exact
  synthetic file (zero-friction judging).
- Export one Mermaid diagram to PNG for the README.
- Visible "Built with Meta" model badge on the dashboard.
- Third-party evidence-pack verification (someone else runs the
  verifier) - strongest production-readiness signal.
- README stills/GIFs of the hero flow as video fallback.
- Quote the numbers in submission text: 87 commits, 370 tests,
  golden 5, both services live.

## Risks

- GitHub frozen is the top risk: 49 commits exist only locally.
  Mitigation today: `FIN_SPY-backup-*.bundle` files on disk.
- Railway free sleep: uptime ping Cron exists; confirm it still runs.
- No JWT: fine for hackathon (documented), blocks real customers.
