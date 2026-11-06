# FIN_SPY - hackathon submission pack (2026-11-03)

Startup track. Theme: Build for Your World.

## Start here (2 min)

1. Watch the demo: https://youtu.be/7RpuGlK77rc
   (offline copy: FIN_SPY-demo-2m30s.mp4 in this pack)
2. Click the live app: https://web-production-74f81.up.railway.app
   (free tier sleeps - first load can take ~60s, then fast)
3. Judge click guide: JUDGES.md (3-min express path included)

## Contents

- JUDGES.md - 7-minute click-through (register, upload the sample
  below, dashboard, drill-to-proof, Excel, evidence pack + verify)
- FNB_synthetic_1.csv - the sample statement from the click guide
- FIN_SPY-code.bundle - complete verified git history (93 commits,
  head 37082ee). GitHub account was suspended mid-event, so code
  ships this way: `git clone FIN_SPY-code.bundle finspy && cd finspy`
  (`git bundle verify` passes; see GIT_HISTORY.md in the repo)
- FIN_SPY-demo-2m30s.mp4 - the demo video file (same as YouTube)
- README.md - project readme (also in the bundle)
- verify_pack.py - offline evidence-pack verifier from the video:
  download an evidence pack from the live app, then
  `python verify_pack.py ./evidence-pack.zip`
- VIDEO.txt - demo video link again for copy-paste

## The numbers

92 commits, 400 tests, 68/68 chain recall, evidence pack verifies
offline (PASS: court-ready chain OK, proven on live 2026-11-03).
Built with Meta Muse Spark 1.3 (standard tier) + Muse Code.
