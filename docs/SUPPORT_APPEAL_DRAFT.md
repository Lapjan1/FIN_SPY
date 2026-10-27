# GitHub Support Appeal Draft - Lapjan1/FIN_SPY

**Subject:** Request for review - Account suspended after Actions storage alert (Lapjan1)

Hello GitHub Support,

My account `Lapjan1` was suspended shortly after I received the automated email "You have used 100% of the Actions storage included for the Lapjan1 account (0.5 GB)".

**Context:**
- Project: `Lapjan1/FIN_SPY` - private hackathon project for Meta Global AI Dev Hackathon (Oct 26 - Nov 4). All commits `771812d` through `8cca543` (25+ commits, `git log --oneline --since="2026-10-26"`) were made in that window; evidence is verifiable locally via `pytest -q` 89 passed, `railway` deploy `finspy-production.up.railway.app` `{"ready":true,"backend":"pg"}`.
- Storage cause: I had a `uptime.yml` workflow with `cron: '*/5 * * * *'` (~288 runs/day) to keep a Railway free-tier service awake (`/health/ready`). I also run a local diagnostic tool `ClearFlag` that monitors workflows - it may have polled frequently. This explains the 90% -> 100% in 3 days. No artifacts are uploaded; it's run logs filling the free 0.5 GB.
- No intentional abuse: No spam, no secret leakage, no FINSPIB/FNBP code reuse beyond READ for design per `AGENTS.md`. Branch protection and presubmit checks are in place.

**Actions already taken locally (not yet pushed due to 403):**
- Disabled the cron in `.github/workflows/uptime.yml` (now `workflow_dispatch` only).
- Plan to delete old workflow runs with `gh run delete` / `gh cache delete` once access is restored, and replace the ping with external UptimeRobot (zero Actions storage).
- Set a $0 budget consideration and retention review to prevent refill.

I have preserved the full local `.git` history and can provide `git bundle` or `git log --graph` if needed.

Could you please advise the specific reason for the suspension and whether clearing runs / disabling the workflow would allow restoration? I will keep the repo private and limit Actions usage until the quota resets on Nov 1.

Thank you,
Jan (Lapjan1, dshannesjvr@gmail.com)
FIN_SPY - C:\Users\dshan\Downloads\Projects\FIN_SPY
