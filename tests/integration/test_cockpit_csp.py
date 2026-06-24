"""
Regression guard for the class of bug that left the CEO cockpit DEAD while 258 tests stayed green:
the security middleware's Content-Security-Policy blocked the cockpit's inline <script> + inline onclick
handlers (script-src 'self'), so NO cockpit JS ran in a real browser — and nothing caught it because no
test enforced CSP or rendered the page.

These tests are docker-free + browser-free (they run in the fast `make qa` / CI lane on EVERY push), and
they tie the served CSP to what cockpit.html ACTUALLY needs: if someone tightens script-src back to a value
that would block the cockpit's inline scripts/handlers or its esm.sh signing import, the suite goes red.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent.parent
COCKPIT = REPO / "dashboard" / "cockpit.html"


def _served_csp() -> str:
    """The CSP header the plane actually sends (set by dashboard_api._harden on every response)."""
    import dashboard.dashboard_api as dapi
    # _harden wraps EVERY response incl. errors, so even a 404 carries the security headers.
    r = TestClient(dapi.app).get("/__nonexistent_probe__")
    return r.headers.get("content-security-policy", "")


def _script_src(csp: str) -> str:
    m = re.search(r"script-src ([^;]+)", csp)
    return m.group(1).strip() if m else ""


def test_cockpit_actually_uses_inline_scripts_and_handlers():
    """Establish the requirement: the cockpit IS built from inline scripts + inline onclick + an esm.sh
    import. (If this ever stops being true, the CSP can be tightened — and these guards updated.)"""
    html = COCKPIT.read_text(encoding="utf-8")
    assert re.search(r"<script>\s*\n", html) or "<script>" in html, "cockpit has an inline <script> block"
    assert re.search(r'onclick="[a-zA-Z]', html), "cockpit wires buttons via inline onclick handlers"
    assert "esm.sh" in html, "cockpit imports the Ed25519 signing lib from esm.sh"


def test_csp_permits_the_cockpits_inline_scripts():
    """THE guard: script-src must allow inline execution (via 'unsafe-inline' or a nonce/hash), or the
    browser silently blocks the whole cockpit. 'self' alone (the bug) must FAIL this test."""
    src = _script_src(_served_csp())
    assert src, "no script-src directive in the served CSP"
    permits_inline = ("'unsafe-inline'" in src) or ("nonce-" in src) or re.search(r"'sha256-", src)
    assert permits_inline, (
        f"script-src ({src!r}) does NOT permit inline scripts — a browser will block every inline <script> "
        f"and onclick in the cockpit (dead nav, frozen 'connecting'). Use 'unsafe-inline' or per-request nonces.")


def test_csp_permits_the_signing_lib_origin():
    """The in-browser Ed25519 signing imports @noble from esm.sh; if script-src/connect-src don't allow it,
    the Sign button throws and merges can't be authorized from the cockpit."""
    csp = _served_csp()
    assert "esm.sh" in _script_src(csp), "script-src must allow https://esm.sh (the signing lib import)"


def test_csp_still_blocks_framing():
    """The clickjacking defence that actually mattered must stay strict even as script-src is relaxed."""
    csp = _served_csp()
    assert "frame-ancestors 'none'" in csp, "frame-ancestors 'none' (clickjacking) must remain"
