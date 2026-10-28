# Day 9 Video Script - 2-3 min hero flow (README + submit)

Target: problem -> upload -> extraction proof -> books -> dashboard drill ->
forensics -> debt -> exports -> billing. Record at 1080p, narrate live.

## Shots (approx timings for a 2:30 cut)

0:00-0:15 Problem - pile of PDFs, no proof
- Show 3 SA bank PDFs (FNB/STDB/ABSA synthetic from data/samples/).
- Line: "Statements arrive as PDFs. Numbers with no proof, no books, no answers."

0:15-0:40 Upload - hash + timestamp
- /upload: drop 3 statements. Show SHA256 vault keys + queued status in /inbox.
- Line: "Every file is hashed into an immutable vault before anything else."

0:40-1:05 Extraction - line-ID grounding + reconcile gate
- /transactions + SourceViewer: click a row, bbox highlight on the PDF.
- Show one reconcile warning resolving (opening + sum = closing both directions).
- Line: "Every number traces to an exact box on the original. The gate checks
  both directions - and fails loudly instead of guessing."

1:05-1:25 Books - private vs business
- /review: accept one AI suggestion with rationale, edit one with reason.
- Trial balance + 9999 suspense near-zero.
- Line: "Rules first, AI second, human last. Humans decide; the audit log
  remembers every change with its reason."

1:25-1:45 Dashboard drill + forensics
- /dashboard: click a bar -> grid -> PDF highlight. Show duplicate/subscription
  flag + Leak Score R/mo.
- Line: "Click any number to its source. The spy finds duplicates, creeping
  subscriptions, and fee leaks."

1:45-2:05 KPI peek + debt
- Runway/burn/savings cards. Debt snowball vs avalanche on the fixture.
- Line: "Runway, burn, and a payoff plan - snowball or avalanche, your call."

2:05-2:25 Exports + billing + close
- Download Excel-12, signed PDF, Evidence Pack; run scripts/verify_pack.py green.
- Paystack test-mode checkout. Close on: "Built with Meta Muse
  Spark/Wonder/Image/SAM 3.1."

## Pre-flight checklist (before pressing record)
- [ ] Railway deploy green, /health/ready true, demo tenant seeded
- [ ] data/samples synthetic PDFs only (never real customer docs on camera)
- [ ] MODEL=muse-spark-1.3 (standard, NOT contributor) or freellmapi dev
- [ ] Reset demo tenant so inbox/flags tell a clean story
- [ ] verify_pack.py runs green on a fresh pack
