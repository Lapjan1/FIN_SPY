"""Menu restructure (lighter): flat workflow top nav + persistent footer.

Top bar holds the 10 workflow links flat (no dropdowns); About, Contact,
Privacy, Terms, Refund live in one footer on every page.
"""
from pathlib import Path

WEB = Path("apps/web/src")
APP = WEB / "app"
TOPNAV = WEB / "components/TopNav.tsx"
FOOTER = WEB / "components/SiteFooter.tsx"
LAYOUT = APP / "layout.tsx"

TOP_LINKS = [
    "/dashboard", "/transactions", "/upload", "/inbox", "/chat",
    "/review", "/books", "/debt", "/reports", "/help", "/account",
]
NOT_ON_TOP = ["/about", "/contact", "/privacy", "/terms", "/refund"]
FOOTER_LINKS = ["/about", "/contact", "/privacy", "/terms", "/refund"]


def test_topnav_lists_workflow_links_flat():
    src = TOPNAV.read_text()
    for href in TOP_LINKS:
        assert f'href="{href}"' in src, f"{href} missing from TopNav"


def test_topnav_has_no_dropdowns_or_static_links():
    src = TOPNAV.read_text()
    assert "useState" not in src  # flat links, no dropdown state
    assert "'use client'" not in src  # server component suffices
    for href in NOT_ON_TOP:
        assert href not in src, f"{href} should live in the footer, not TopNav"


def test_footer_holds_static_links():
    src = FOOTER.read_text()
    assert "<footer" in src
    for href in FOOTER_LINKS:
        assert f'href="{href}"' in src, f"{href} missing from footer"


def test_layout_renders_nav_and_footer():
    src = LAYOUT.read_text()
    assert "TopNav" in src and "SiteFooter" in src
    assert 'href="/dashboard"' not in src  # links live in TopNav, not layout


def test_no_per_page_footers():
    dupes = sorted(str(p) for p in APP.glob("*/page.tsx")
                   if "<footer" in p.read_text())
    assert dupes == [], f"per-page footers remain: {dupes}"


def test_every_nav_href_has_a_route():
    hrefs = TOP_LINKS + FOOTER_LINKS
    missing = [h for h in hrefs if not (APP / h.strip("/") / "page.tsx").exists()]
    assert missing == [], f"nav links without routes: {missing}"
