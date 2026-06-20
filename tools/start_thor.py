"""
THOR control-plane supervisor — the run target (wiring Task 0; closes register gap C2).

Brings the whole control plane up as ONE process that constructs the THOR roles as DISTINCT PEERS
sharing one Postgres ledger, in the manual's boot order, then serves the four real HTTP boundaries.

ROLES (the Manager is NOT "the brain" — it is the room mechanism + the sole ledger writer):
    CTO         the brain — shared planner/escalation head (per-room Leash rule-card wired at T3)
    Manager     the room mechanism + the SINGLE EventLog writer (decides nothing)
    PM          the plan — the feature catalog (in the ledger) + the SDLC stage library
    GovEngine   the verdict-from-reality (honest Verdict Coordinator wired at T5)
    Sentinel    meta-governance / health (real halt wired at T8)
    Self-Audit  the read-only correctness eyes (real local model wired at T9)

Task 0 wires NO decision flow — it only stands the roles up and serves their surfaces:
    Manager :7100    Dashboard :7080 (+ live cockpit)    Sentinel :7140    Self-Audit :7150

Start THOR (host mode, one command):

    python tools/start_thor.py

Postgres is brought up automatically if it isn't already reachable (the same `thor-postgres`
container that `docker-compose.yml` declares), so this single command cold-starts the control plane.
Open the dashboard URL printed in the banner to see live state. Ctrl-C stops it.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import psycopg
import uvicorn
from fastapi.responses import FileResponse

import dashboard.dashboard_api as dashboard_api
import manager.api as manager_api
import scheduler.cto_stub as cto          # the CTO planner faculty (shared brain; stub today)
import selfaudit.api as selfaudit_api
import sentinel.api as sentinel_api
from dashboard.service import DashboardService
from manager import db, pg
from manager.core import ThorManager
from selfaudit import db as sa_db
from selfaudit.core import SelfAudit
from sentinel.core import Sentinel

# Bind host: 127.0.0.1 by default (safe for local dev). In a container/k8s the surfaces must bind
# 0.0.0.0 to be reachable through published ports / Services — set THOR_BIND_HOST=0.0.0.0.
HOST = os.environ.get("THOR_BIND_HOST", "127.0.0.1")
PORTS = {"manager": 7100, "dashboard": 7080, "sentinel": 7140, "selfaudit": 7150}
COCKPIT = REPO / "dashboard" / "cockpit.html"
DASH_CSS = REPO / "dashboard" / "dashboard.css"   # the original watchdog's design system, verbatim


class _LockedConn:
    """
    Thread-safe wrapper around ONE psycopg connection (run-target plumbing — NOT a module change).

    The control plane shares one ledger connection, but uvicorn serves the sync HTTP endpoints in a
    worker-thread pool and the cockpit fires several requests in parallel — concurrent use of a single
    psycopg connection raises. This serializes every `with conn.cursor()` block behind one re-entrant
    lock, so concurrent HTTP-served access is safe. Modules are untouched: they still call
    `conn.cursor()` / `conn.commit()`. (Relates to register M4; the proper fix is a pool, later.)
    """

    def __init__(self, conn) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    def cursor(self, *a, **k):
        return _LockedCursor(self._conn, self._lock, a, k)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def __getattr__(self, name):           # pass through everything else (execute, close, info, ...)
        return getattr(self._conn, name)


class _LockedCursor:
    """A cursor context manager that holds the connection lock for the whole `with` block."""

    def __init__(self, conn, lock, a, k) -> None:
        self._conn, self._lock, self._a, self._k, self._cur = conn, lock, a, k, None

    def __enter__(self):
        self._lock.acquire()
        try:
            self._cur = self._conn.cursor(*self._a, **self._k)
            return self._cur.__enter__()
        except Exception:
            self._lock.release()
            raise

    def __exit__(self, *exc):
        try:
            return self._cur.__exit__(*exc)
        finally:
            self._lock.release()


def _pg_reachable() -> bool:
    try:
        with psycopg.connect(pg.DSN, connect_timeout=2) as c:
            c.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - not up yet
        return False


def _auth_guard() -> None:
    """Refuse to boot a NETWORK-EXPOSED plane with NO authentication. Auth is OPEN when neither
    THOR_API_TOKEN nor THOR_USERS (RBAC) is set — fine for a localhost dev box (HOST=127.0.0.1), but a
    plane bound to 0.0.0.0 (the compose / k8s posture) would then expose its mutating surface to the network
    with no credential. Fail fast with the fix. `THOR_ALLOW_OPEN=1` is a loud, explicit escape hatch."""
    import rbac
    host = os.environ.get("THOR_BIND_HOST", "127.0.0.1")
    exposed = host not in ("127.0.0.1", "localhost", "::1")
    has_auth = bool(os.environ.get("THOR_API_TOKEN")) or rbac.rbac_enabled()
    if exposed and not has_auth and os.environ.get("THOR_ALLOW_OPEN") != "1":
        sys.exit(
            f"[thor] REFUSING TO BOOT: bound to {HOST} (network-exposed) with NO authentication.\n"
            "        Set THOR_API_TOKEN=<strong secret>  OR  THOR_USERS=<RBAC roster JSON>.\n"
            "        (Localhost dev is exempt; THOR_ALLOW_OPEN=1 overrides this — do NOT in production.)")


def boot() -> list[tuple[object, int]]:
    _auth_guard()   # security: never start an open plane on a network-reachable bind
    # ---- 1) DB — the single ledger backend ----
    if _pg_reachable():
        print(f"[thor] DB        Postgres reachable at {pg.DSN}")
    else:
        print("[thor] DB        Postgres not reachable — bootstrapping thor-postgres ...")
        pg.start()
        print(f"[thor] DB        up at {pg.DSN}")
    conn = _LockedConn(db.connect())       # thread-safe: the control plane serves HTTP off one conn
    db.init_schema(conn)

    # ---- 2) CTO — the brain (shared planner/escalation head) ----
    # Stateless planner faculty today (cto_stub). The per-room Leash rule-card comes online with each
    # room in the cook action path at T3; no decide-before loop is wired yet.
    assert hasattr(cto, "plan_task")
    print("[thor] CTO       brain ready — shared planner faculty (per-room Leash wired at T3)")

    # ---- 3) Room Mechanism — the Manager: the hands + the SOLE ledger writer (decides nothing) ----
    manager = ThorManager(conn)
    # Operator signing keys come from out-of-band boot config (THOR_OPERATOR_PUBKEYS, comma-separated
    # Ed25519 b64 keys) — NOT from a token-unlocked HTTP endpoint. With keys configured, only they may
    # sign; a new key afterwards needs an existing operator's co-signature (AUD-register-authority).
    for _pub in (p.strip() for p in os.environ.get("THOR_OPERATOR_PUBKEYS", "").split(",") if p.strip()):
        manager.register_operator(_pub)
    # RBAC: bind each configured user's Ed25519 key to its role (THOR_USERS). Only commander keys gain merge
    # authority; operator/viewer keys are known identities with NO signing power (their TOKEN drives the flow,
    # role-gated at the HTTP edge). authN ≠ authZ: a token can never mint a merge — that needs a commander key.
    import rbac
    _users = rbac.load_users()
    for _u in _users:
        manager.register_user(_u["id"], _u["role"], _u.get("pubkey", ""))
    if manager.authorized_signers:
        print(f"[thor] Identity  {len(manager.authorized_signers)} commander key(s) registered from boot config")
    if _users:
        from collections import Counter
        _by = Counter(u["role"] for u in _users)
        print(f"[thor] RBAC      {len(_users)} user(s): " + ", ".join(f"{n} {r}" for r, n in sorted(_by.items())))
    # Supply-chain nudge: a mutable image tag can be swapped at the registry — pin by digest in production.
    from wall import config as _img_cfg
    if "@sha256:" not in _img_cfg.ROOM_IMAGE:
        print(f"[thor] WARN     room image '{_img_cfg.ROOM_IMAGE}' is a MUTABLE tag — pin by digest "
              f"(THOR_ROOM_IMAGE=name@sha256:…) in production to prevent a swapped image")
    # M1: crash-replay has a REAL caller now. On every boot the Manager rebuilds its projections
    # (rooms/cards/features) purely by replaying the durable signed EventLog — so a crash that lost
    # the projection tables (but kept the ledger) recovers to exact state. (FR-13 / AC-3.)
    manager.rebuild_from_log()
    print(f"[thor] Manager   room mechanism up — sole EventLog writer (decides nothing); "
          f"replayed {manager.eventlog.count()} events on boot")
    # AC-8 crash-resume: after the projection is rebuilt, re-queue any build interrupted by the crash (the
    # plane just started, so a mid-flight feature is orphaned). The verdict re-judges from reality on the
    # re-dispatch, so recovery can never resurrect a false `done`.
    _rec = manager.recover_in_flight()
    if _rec["recovered"]:
        print(f"[thor] Recovery  {len(_rec['recovered'])} interrupted build(s) re-queued to ready: "
              + ", ".join(r["feature_id"] for r in _rec["recovered"]))

    # ---- 4) PM — the plan: the catalog lives in the ledger; the SDLC stage library is available ----
    print("[thor] PM        plan ready — feature catalog (in ledger) + SDLC stage library")

    # ---- 5) GovEngine — the verdict-from-reality (library; honest Coordinator wired at T5) ----
    print("[thor] GovEngine verdict engine ready — Verdict Coordinator wired at T5")

    # ---- 6) Sentinel — meta-governance / health (peer; REAL halt wired at T8) ----
    sentinel = Sentinel(manager)
    manager.attach_sentinel(sentinel)   # T5: a caught lie escalates to meta-governance

    def _http_health(url):
        def fn():
            import json
            import urllib.request
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    body = json.loads(r.read() or "{}") if r.status == 200 else {}
                    return {"alive": True, "responsive": bool(body.get("responsive", r.status == 200))}
            except Exception:  # unreachable / hung → not responsive (the probe fails closed)
                return {"alive": False, "responsive": False}
        return fn

    # T8: the Sentinel watches the LIVE surfaces; a critical one going unresponsive → halt (after re-probe).
    sentinel.register("manager", critical=True, health_fn=_http_health(f"http://{HOST}:{PORTS['manager']}/health"))
    sentinel.register("selfaudit", critical=True, health_fn=_http_health(f"http://{HOST}:{PORTS['selfaudit']}/health"))
    sentinel.register("dashboard", critical=False, health_fn=_http_health(f"http://{HOST}:{PORTS['dashboard']}/"))
    print("[thor] Sentinel  meta-governance up — REAL halt: kills rooms + blocks work; watches 3 live surfaces")

    # ---- 7) Self-Audit — the read-only correctness eyes (peer; real model wired at T9) ----
    sa_db.setup(conn)                      # create the read-only selfaudit role + tables (idempotent)
    from selfaudit import model_host as sa_model
    sa_inspector = sa_model.select_model()   # T9: a real local Ollama/Qwen if present, else deterministic v1
    selfaudit = SelfAudit(_LockedConn(sa_db.connect_readonly()), sentinel=sentinel, model=sa_inspector)
    print(f"[thor] SelfAudit correctness eyes up — read-only DB role; model={sa_inspector.name} "
          f"(zero frontier calls)")

    # ---- 8) Operator surface — the Dashboard window over the one truth ----
    dashboard = DashboardService(manager, selfaudit=selfaudit)   # surfaces governance + Self-Audit live

    # ---- 9) Bind the served apps to the shared peers + mount the live cockpit (read-only at T0) ----
    manager_api._manager = manager         # the Manager API's lazy singleton = the shared mechanism
    dashboard_api.bind(dashboard)
    sentinel_api.bind(sentinel)
    selfaudit_api.bind(selfaudit)
    # native push: a card that needs a human → a THOR notification on every subscribed phone (best-effort)
    from dashboard import push as _push
    manager.on_card_raised = lambda cid, t, fid, st: _push.send(
        "THOR — signature needed", f"{t} · {fid} is awaiting your signature", "/app/")
    dashboard_api.app.add_api_route(       # serve the static cockpit + shared theme at :7080/
        "/", lambda: FileResponse(str(COCKPIT)), include_in_schema=False)
    dashboard_api.app.add_api_route(
        "/dashboard.css", lambda: FileResponse(str(DASH_CSS)), include_in_schema=False)
    # THOR Mobile: the React cockpit (laptop + phone, installable PWA) at :7080/app/ — same Manager truth,
    # real-time via /stream. Served only if built (`cd ui && npm ci && npm run build`).
    ui_dist = REPO / "ui" / "dist"
    if ui_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        dashboard_api.app.mount("/app", StaticFiles(directory=str(ui_dist), html=True), name="cockpit")
        print(f"[thor] HTTP      surfaces bound; cockpit at :7080/  +  React PWA at :7080/app/")
    else:
        print("[thor] HTTP      surfaces bound; cockpit at :7080/  (build ui/ for the React PWA at /app/)")

    return [
        (manager_api.app, PORTS["manager"]),
        (dashboard_api.app, PORTS["dashboard"]),
        (sentinel_api.app, PORTS["sentinel"]),
        (selfaudit_api.app, PORTS["selfaudit"]),
    ]


def _run_server(app: object, port: int) -> None:
    # Each uvicorn server gets its OWN thread + event loop. Running several servers in one shared
    # asyncio loop (asyncio.gather) breaks the sync-endpoint threadpool; one-loop-per-server is clean.
    asyncio.set_event_loop(asyncio.new_event_loop())
    srv = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    asyncio.get_event_loop().run_until_complete(srv.serve())


def serve(apps: list[tuple[object, int]]) -> None:
    for app, port in apps:
        threading.Thread(target=_run_server, args=(app, port), daemon=True).start()
    print("\n" + "=" * 72)
    print(" THOR control plane UP")
    print(f"   Manager    http://{HOST}:{PORTS['manager']}")
    print(f"   Dashboard  http://{HOST}:{PORTS['dashboard']}/      <- open this to see THOR live")
    print(f"   Sentinel   http://{HOST}:{PORTS['sentinel']}")
    print(f"   Self-Audit http://{HOST}:{PORTS['selfaudit']}")
    print(" Ctrl-C to stop")
    print("=" * 72 + "\n", flush=True)
    while True:
        time.sleep(3600)


def main() -> int:
    try:
        serve(boot())
    except KeyboardInterrupt:
        print("\n[thor] shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
