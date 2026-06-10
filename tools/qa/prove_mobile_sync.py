"""
THOR Mobile proof — the PWA is served by the plane AND real-time sync works: when the ledger advances,
the SSE /stream pushes the new seq, so every connected head (laptop + phone) re-syncs instantly off the
ONE Manager truth. Boots the real DashboardAPI on a port, serves ui/dist, and drives a live stream.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_mobile_sync.py
"""
import json
import os
import threading
import time
import urllib.request

import docker
import uvicorn
from fastapi.staticfiles import StaticFiles

import dashboard.dashboard_api as api
from dashboard.service import DashboardService
from manager import db, pg
from manager.core import ThorManager

PORT = 7099
pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
with conn.cursor() as cur:
    cur.execute("TRUNCATE eventlog, rooms, cards, features")
conn.commit()
mgr = ThorManager(conn)
api.bind(DashboardService(mgr))
assert os.path.isdir("ui/dist"), "build the PWA first: cd ui && npm run build"
api.app.mount("/app", StaticFiles(directory="ui/dist", html=True), name="cockpit")

server = uvicorn.Server(uvicorn.Config(api.app, host="127.0.0.1", port=PORT, log_level="error"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(80):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/state/summary", timeout=1)
        break
    except Exception:
        time.sleep(0.1)

# 1) the plane serves the installable PWA (laptop + phone load the SAME cockpit)
for path in ("/app/", "/app/manifest.webmanifest", "/app/sw.js", "/app/icon.svg"):
    code = urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=3).status
    print(f"serve {path:28s} -> {code}")
    assert code == 200, path

# 2) REAL-TIME SYNC: open the stream, advance the ledger, see the new seq pushed
stream = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/stream", timeout=15)
seq_before = mgr.eventlog.count()


def advance():
    time.sleep(1.2)
    mgr._record("feature.added", {"feature_id": "MOB", "title": "from another device"}, feature_id="MOB")


threading.Thread(target=advance, daemon=True).start()

pushed = None
deadline = time.time() + 10
while time.time() < deadline and pushed is None:
    line = stream.readline().decode()
    if line.startswith("data:"):
        body = line[5:].strip()
        if body and body != "{}":
            d = json.loads(body)
            if d.get("seq", -1) > seq_before:
                pushed = d["seq"]

print(f"real-time push: seq {seq_before} -> {pushed}")
assert pushed is not None and pushed > seq_before, "the stream must push the new ledger seq in real time"
print("MOBILE_SYNC_OK")
