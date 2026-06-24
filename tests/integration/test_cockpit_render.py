"""
Browser-level render + nav smoke for the CEO cockpit — the test that was MISSING when a dead cockpit
passed 258 green tests. It loads cockpit.html in a real headless browser THAT ENFORCES CSP (the thing
Node/curl/TestClient can't do), and asserts:
  - the inline IIFE actually executes under the served CSP  (window.go is defined)
  - the banner leaves the 'connecting…' placeholder        (refreshAll ran)
  - clicking a nav tab switches panels                      (the user's exact complaint)

Self-contained: serves cockpit.html behind the REAL dashboard CSP/security headers + stub data endpoints,
so it needs no Postgres. Skips honestly when Playwright or a browser isn't installed (e.g. local WSL),
so it never false-greens; it RUNS in CI's browser-smoke job (Linux + `playwright install chromium`).
"""
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.deferred

REPO = Path(__file__).resolve().parent.parent.parent
COCKPIT = REPO / "dashboard" / "cockpit.html"

_STUB = {"connected": True, "health": {"sentinel": {"alive": True, "alarms": 0}, "self_audit": {"model": "v1", "frontier_calls": 0}, "self_audit_meta_trust": 0.97},
         "columns": {"backlog": [], "ready": [], "building": [], "in_qa": [], "awaiting_signature": [], "done": []},
         "cards": [], "events": [], "active": [], "checker_findings": [], "total": 0, "by_container": {}, "recent": [],
         "per_feature": [], "total_spent": 0, "threats": []}


def _make_app():
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, JSONResponse
    import dashboard.dashboard_api as dapi

    app = FastAPI()

    @app.middleware("http")
    async def _sec(request, call_next):       # the REAL security headers / CSP the plane serves
        return dapi._harden(await call_next(request))

    @app.get("/")
    def _root():
        return FileResponse(str(COCKPIT))

    @app.get("/vendor/{name}")
    def _vendor(name: str):
        f = REPO / "dashboard" / "vendor" / name
        return FileResponse(str(f), media_type="text/javascript")

    for path in ["/state/summary", "/kanban", "/rooms/live", "/cards", "/audit/feed", "/cost",
                 "/findings", "/lies", "/health/system", "/threats", "/progress", "/bugs"]:
        app.add_api_route(path, lambda: JSONResponse(_STUB), include_in_schema=False)
    return app


def _serve(app, port):
    import uvicorn
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(50):
        if srv.started:
            return srv
        time.sleep(0.1)
    return srv


def test_cockpit_renders_and_nav_switches_panels():
    pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    port = 7399
    srv = _serve(_make_app(), port)
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--no-sandbox"])
            except Exception as e:  # noqa: BLE001 — no browser binary (e.g. local WSL): skip, never fake-pass
                pytest.skip(f"no chromium browser available: {e}")
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(3500)

            state = page.evaluate("() => ({go: typeof window.go, trust: document.getElementById('trust-text')?.textContent})")
            assert state["go"] == "function", "the inline IIFE did not execute under CSP — window.go missing (cockpit dead)"
            assert "connecting" not in (state["trust"] or "").lower(), f"banner stuck on placeholder: {state['trust']!r}"

            # click Decide and assert the panel actually switches
            page.evaluate("() => [...document.querySelectorAll('.np')].find(b => b.textContent.toLowerCase().includes('decide')).click()")
            page.wait_for_timeout(300)
            vis = page.evaluate("() => ['home','decide'].filter(p => getComputedStyle(document.getElementById('panel-'+p)).display !== 'none')")
            assert vis == ["decide"], f"nav did not switch: visible panels = {vis}"
            assert not errors, f"page errors: {errors}"
            browser.close()
    finally:
        srv.should_exit = True
