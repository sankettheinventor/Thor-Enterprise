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
import sys
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

HOST = "127.0.0.1"
PORTS = {"manager": 7100, "dashboard": 7080, "sentinel": 7140, "selfaudit": 7150}
COCKPIT = REPO / "dashboard" / "cockpit.html"


def _pg_reachable() -> bool:
    try:
        with psycopg.connect(pg.DSN, connect_timeout=2) as c:
            c.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001 - not up yet
        return False


def boot() -> list[tuple[object, int]]:
    # ---- 1) DB — the single ledger backend ----
    if _pg_reachable():
        print(f"[thor] DB        Postgres reachable at {pg.DSN}")
    else:
        print("[thor] DB        Postgres not reachable — bootstrapping thor-postgres ...")
        pg.start()
        print(f"[thor] DB        up at {pg.DSN}")
    conn = db.connect()
    db.init_schema(conn)

    # ---- 2) CTO — the brain (shared planner/escalation head) ----
    # Stateless planner faculty today (cto_stub). The per-room Leash rule-card comes online with each
    # room in the cook action path at T3; no decide-before loop is wired yet.
    assert hasattr(cto, "plan_task")
    print("[thor] CTO       brain ready — shared planner faculty (per-room Leash wired at T3)")

    # ---- 3) Room Mechanism — the Manager: the hands + the SOLE ledger writer (decides nothing) ----
    manager = ThorManager(conn)
    print("[thor] Manager   room mechanism up — sole EventLog writer (decides nothing)")

    # ---- 4) PM — the plan: the catalog lives in the ledger; the SDLC stage library is available ----
    print("[thor] PM        plan ready — feature catalog (in ledger) + SDLC stage library")

    # ---- 5) GovEngine — the verdict-from-reality (library; honest Coordinator wired at T5) ----
    print("[thor] GovEngine verdict engine ready — Verdict Coordinator wired at T5")

    # ---- 6) Sentinel — meta-governance / health (peer; real halt wired at T8) ----
    sentinel = Sentinel(manager)
    print("[thor] Sentinel  meta-governance up (real halt wired at T8)")

    # ---- 7) Self-Audit — the read-only correctness eyes (peer; real model wired at T9) ----
    sa_db.setup(conn)                      # create the read-only selfaudit role + tables (idempotent)
    selfaudit = SelfAudit(sa_db.connect_readonly(), sentinel=sentinel)
    print("[thor] SelfAudit correctness eyes up — read-only DB role (real model wired at T9)")

    # ---- 8) Operator surface — the Dashboard window over the one truth ----
    dashboard = DashboardService(manager)

    # ---- 9) Bind the served apps to the shared peers + mount the live cockpit (read-only at T0) ----
    manager_api._manager = manager         # the Manager API's lazy singleton = the shared mechanism
    dashboard_api.bind(dashboard)
    sentinel_api.bind(sentinel)
    selfaudit_api.bind(selfaudit)
    dashboard_api.app.add_api_route(       # serve the cockpit at :7080/ so live state is visible
        "/", lambda: FileResponse(str(COCKPIT)), include_in_schema=False)
    print("[thor] HTTP      surfaces bound; cockpit mounted at :7080/")

    return [
        (manager_api.app, PORTS["manager"]),
        (dashboard_api.app, PORTS["dashboard"]),
        (sentinel_api.app, PORTS["sentinel"]),
        (selfaudit_api.app, PORTS["selfaudit"]),
    ]


async def serve(apps: list[tuple[object, int]]) -> None:
    servers = []
    for app, port in apps:
        srv = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
        srv.install_signal_handlers = lambda: None   # one process hosts 4 servers — handle Ctrl-C at main
        servers.append(srv)
    print("\n" + "=" * 72)
    print(" THOR control plane UP")
    print(f"   Manager    http://{HOST}:{PORTS['manager']}")
    print(f"   Dashboard  http://{HOST}:{PORTS['dashboard']}/      <- open this to see THOR live")
    print(f"   Sentinel   http://{HOST}:{PORTS['sentinel']}")
    print(f"   Self-Audit http://{HOST}:{PORTS['selfaudit']}")
    print(" Ctrl-C to stop")
    print("=" * 72 + "\n", flush=True)
    await asyncio.gather(*(s.serve() for s in servers))


def main() -> int:
    try:
        asyncio.run(serve(boot()))
    except KeyboardInterrupt:
        print("\n[thor] shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
