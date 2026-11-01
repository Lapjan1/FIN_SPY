# VIDEO_SCRIPT.md - 2:30 submission cut (director's notes included)

Research consensus (Devpost, AngelHack, ETHGlobal patterns): judges watch
dozens of videos, often sound-off first. Structure: hook 10s, problem 15s,
live demo 60-90s, tech 30s, close 20s. Never narrate what they can see -
one sentence per screen state. MP4, 720p minimum, captions on.

Target: 2:30, ~370 spoken words. Record at 1080p30, export 1080p MP4.

## Shot list (S = screen, V = voice, T = on-screen text)

### 0:00-0:10 HOOK (T works sound-off)

- S: dashboard with real totals + leak score, already loaded.
- T: "Every rand traced to the exact line. - FIN_SPY"
- V: "Bank statements go in. Every number comes out with proof."

### 0:10-0:25 PROBLEM

- S: messy folder of PDFs -> cut to a dense 3-page statement.
- V: "Small businesses drown in statements. Accountants don't trust
  AI numbers, because no AI can show where a number came from."

### 0:25-0:55 UPLOAD + PROOF (the core demo)

- S: Upload page. Drag `FNB_synthetic_1.csv`. Receipt appears.
- V: "Watch. The file is hashed into an immutable vault - same file
  twice is detected, never duplicated."
- S: Inbox row flips queued -> proposed. Open the extraction view.
- V: "Extraction carries line IDs. Opening plus rows must equal
  closing, checked both directions, or it never passes."

### 0:55-1:20 BOOKS THAT BUILD THEMSELVES

- S: Review queue. Accept two suggestions (private, business).
- V: "Private or business, with a rationale and a confidence. Accept,
  and a balanced journal posts. Unsure money parks in suspense."
- S: Books page trial balance. Debits equal credits.
- V: "Trial balance, per bank account. Debits equal credits."

### 1:20-1:50 THE MONEY SHOT (slow down here)

- S: Dashboard. Click a chart number -> transaction grid -> click a row
  -> PDF with the source line highlighted.
- V: "And here is the whole product. Any number, back to the exact
  highlighted line it came from. That is what court-ready means."

### 1:50-2:10 SPY + EXPORTS

- S: Spy flags (duplicate/subscription), leak score R/mo. Then Reports:
  download Excel, open Trial_Balance (Enable Editing, F9).
- V: "The spy finds duplicates and subscriptions. Exports carry live
  formulas - and an evidence pack any auditor can verify offline."
- S (5s): terminal running `python scripts/verify_pack.py`, hashes OK.
  (Pre-record this clip; paste it in.)

### 2:10-2:30 TECH + CLOSE

- S: `/docs` API page scrolling, then landing page. Freeze on logo.
- T: "Built with Meta Muse Spark - 370 tests - live today"
- V: "Built with Meta Muse Spark, with a hundred-request limiter and
  audited fallbacks. Three hundred seventy tests, live in production
  today. FIN_SPY: every rand, with proof."

## Recording guide (Windows, free)

1. Tool: OBS Studio (free) or Xbox Game Bar (Win+G, built in).
   Capture: one Chrome window at 1920x1080, 30fps. Close notifications
   (Focus Assist on), hide bookmarks bar, zoom pages to 110%.
2. Audio: any headset mic in a quiet room beats a laptop mic across
   the room. Record 5s of silence first (noise profile / room tone).
3. Takes: record each block above as its own take; mistakes cost
   seconds, not the whole video. Clap once before each take (sync mark).
4. Data: use a FRESH demo account (`demo-judge@fin-spy.example`) so the
   video shows a clean first-run story. Rehearse the clicks once
   unrecorded (cold start can take ~60s - wake the site first).
5. Edit: DaVinci Resolve (free) or Clipchamp (built in). Cut pauses,
   add the T overlays above as text cards, hard-code captions
   (YouTube auto-captions + 10 min of fixes, then burn in).
6. Export: MP4 H.264 1080p30, under 500MB. Filename:
   `FIN_SPY-demo-2m30s.mp4`. Keep the project file for re-cuts.
7. Fallbacks: if the live site sleeps mid-take, keep recording, say
   "waking the free tier", cut the wait in edit. If upload stalls,
   cut to the already-loaded Inbox (record B-roll of every page first).

## Pre-flight checklist (night before)

- Live site awake: load `/` and `/health/ready` on the API.
- Demo account registered; trial quota untouched (20 uploads).
- Sample files on desktop: `FNB_synthetic_1.csv`, one PDF.
- Script printed; water; room quiet; phone on silent.
- Disk space for recording (~2GB); charger plugged in.
