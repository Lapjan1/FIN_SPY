# Menu restructure: lighter flat top, links live on the bottom - task record

User asked (2026-11-02): the top bar is overpopulated (12 flat links);
implement the submenu structure that was proposed-but-deferred during the
feedback-channel work, and move the static links to a persistent bottom
footer on every page. Flow: document -> red test -> green implement.

PIVOT (same day, user call for the competition): dropdowns felt
excessive (everything two clicks away). Shipped the lighter version
instead - flat workflow links on top, static links only in the footer.

## Plan

Top bar (12 flat links -> 10 flat links + badge + Account):

- Dashboard, Transactions, Upload, Inbox, Chat, Review, Books, Debt,
  Reports, Help (flat, unchanged order)
- SessionNav badge + Account (direct, unchanged)
- Privacy/Terms/Refund moved OFF the top bar into the footer

Bottom footer, rendered by `layout.tsx` on EVERY page:

- About, Contact, Privacy, Terms, Refund

Per-page footers (about, contact, privacy, terms, refund) are removed so
the footer has a single source of truth and no page shows it twice. No
route is removed and no URL changes; legal pages keep their light-theme
body classes, only their footer moves to the shared dark footer.

## Steps

1. [x] Document: this file (plan above).
2. [x] Red: `tests/test_menu_structure.py` 6 failed / 1 passed on the
   old nav (no TopNav/SiteFooter, 12 flat links, 5 per-page footers;
   only the route-existence guard passed).
3. [x] Green: `TopNav.tsx` (client dropdowns) + `SiteFooter.tsx` +
   `layout.tsx` wiring + per-page footer removal (about/contact LF via
   edit, privacy/terms/refund CRLF via regex splice per Learning 43).
4. [x] Verify: 7/7 menu tests green, `tsc --noEmit` exit 0. Full API
   suite NOT runnable locally: `uv sync` unsatisfiable (pyright pin)
   and no fastapi in any interpreter - pre-existing env breakage, and
   this change touches no Python runtime code. Ruff binary absent.

## Evidence

- `uv run --no-sync pytest tests/test_menu_structure.py -q`: 7 passed
  (dropdown version), then retargeted to the flat contract: 2 red on
  the dropdown code, 6/6 green after flattening.
- `pnpm --dir apps/web exec tsc --noEmit`: exit 0 (both versions).
- Top bar now: 10 flat workflow links + SessionNav badge + Account.
  Footer on every page: About Contact Privacy Terms Refund. No URL
  changed, no route removed.
- LIVE 2026-11-02 (`railway up --service web`): /about nav has the 10
  flat links, no /privacy in nav, SiteFooter marker present;
  /contact /help /privacy all carry the footer. API redeployed same
  day at user request (`railway up --service FIN_SPY`, fresh boot
  confirmed): /health/ready 200 pg, /v1/feedback no-auth 401.
