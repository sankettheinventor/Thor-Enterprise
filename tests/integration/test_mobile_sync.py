"""
THOR Mobile: the plane serves the installable PWA at /app/ and the SSE /stream pushes ledger advances in
real time, so the phone and the laptop sync off the ONE Manager truth (Module 9: the phone is a REMOTE
HEAD, not a second system). Deferred; auto-skips if the UI isn't built (never fakes green).
"""
import json
import os
import threading
import time
import urllib.request

import pytest

pytestmark = pytest.mark.deferred


@pytest.mark.skipif(not os.path.isdir("ui/dist"), reason="UI not built (cd ui && npm run build)")
def test_pwa_served_and_realtime_stream(fresh_ledger):
    import uvicorn
    from fastapi.staticfiles import StaticFiles

    import dashboard.dashboard_api as api
    from dashboard.service import DashboardService
    from manager.core import ThorManager

    mgr = ThorManager(fresh_ledger)
    api.bind(DashboardService(mgr))
    if not any(getattr(r, "path", None) == "/app" for r in api.app.routes):
        api.app.mount("/app", StaticFiles(directory="ui/dist", html=True), name="cockpit")

    port = 7098
    server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/state/summary", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    try:
        # the installable PWA is served (laptop + phone load the SAME cockpit)
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/app/", timeout=3).status == 200
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}/app/manifest.webmanifest", timeout=3).status == 200

        # real-time sync: open the stream, advance the ledger from "another device", see it pushed
        stream = urllib.request.urlopen(f"http://127.0.0.1:{port}/stream", timeout=15)
        before = mgr.eventlog.count()
        threading.Thread(target=lambda: (time.sleep(1.2),
                         mgr._record("feature.added", {"feature_id": "MOB", "title": "x"}, feature_id="MOB")),
                         daemon=True).start()

        pushed = None
        deadline = time.time() + 10
        while time.time() < deadline and pushed is None:
            line = stream.readline().decode()
            if line.startswith("data:"):
                body = line[5:].strip()
                if body and body != "{}" and json.loads(body).get("seq", -1) > before:
                    pushed = json.loads(body)["seq"]
        assert pushed is not None and pushed > before, "the stream must push the new ledger seq in real time"
    finally:
        server.should_exit = True
