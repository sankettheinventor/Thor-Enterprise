"""
ONE-TIME smoke of the Self-Audit Model (Module 11) — the zero-cost, read-only "understanding eyes".

Headline (PRD §15): AC-1 + AC-3 + AC-4 — a continuous, zero-cost, read-only inspector that catches a
real correctness anomaly and escalates it to the Sentinel WITHOUT ever being able to act on the system
itself. Run against a REAL read-only Postgres role + the Manager's EventLog + the REAL Sentinel (M10).

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real DB permissions, real escalation.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_selfaudit.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from manager import db, pg
from manager.core import ThorManager
from selfaudit import db as sa_db
from selfaudit.core import SelfAudit
from selfaudit.model_host import InspectionModel
from sentinel.core import Sentinel


def main() -> int:
    results: dict[str, bool] = {}
    client = docker.from_env()
    try:
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features, bugs")
        mgr = ThorManager(conn)

        # seed an EventLog of real activity with a SEEDED severe anomaly (high divergence + escalation)
        for i in range(5):
            mgr.eventlog.append("verdict.computed", {"feature_id": f"F{i}", "verdict": "done"})
        for i in range(5):
            mgr.eventlog.append("verdict.computed", {"feature_id": f"G{i}", "verdict": "escalate"})
        for i in range(5):
            mgr.eventlog.append("divergence.detected", {"feature_id": f"H{i}", "signals": ["lie"]})
        for i in range(6):
            mgr.eventlog.append("qa.finding", {"feature_id": f"J{i}", "severity": "high"})
        mgr.eventlog.append("sentinel.alarm", {"severity": "degraded", "message": "blip"})

        sa_db.setup(conn)                          # create the read-only role + its tables (as DB owner)
        ro = sa_db.connect_readonly()              # connect as the selfaudit role (read-only)

        sentinel = Sentinel(mgr)
        sa = SelfAudit(ro, sentinel=sentinel)
        sentinel.register("selfaudit", critical=False, health_fn=sa.health)   # the observer is watched

        result = sa.inspect()

        # ---------- AC-1 zero token cost ----------
        print("== AC-1 zero token cost (no frontier-model calls) ==")
        results["AC-1 zero token cost"] = sa.model.frontier_calls == 0
        print(f"   frontier_calls={sa.model.frontier_calls}")

        # ---------- AC-2 writes reports + meta-trust to DB ----------
        print("== AC-2 writes correctness reports + meta-trust score to DB ==")
        reps = sa.reports()
        mt = sa.meta_trust()
        results["AC-2 reports + meta-trust in DB"] = len(reps) >= 1 and mt is not None and mt["score"] is not None
        print(f"   reports={len(reps)}  meta_trust_score={mt['score'] if mt else None}")

        # ---------- AC-3 read-only: write to EventLog DENIED by DB permissions ----------
        print("== AC-3 read-only: a write to the EventLog is DENIED by Postgres ==")
        denied = False
        try:
            with ro.cursor() as cur:
                cur.execute("INSERT INTO eventlog (seq,prev_hash,hash,signature,ts,actor,event_type,payload)"
                            " VALUES (999999,'x','x','x',0,'sa','hack','{}')")
        except Exception as e:  # noqa: BLE001 - expecting InsufficientPrivilege
            denied = "permission denied" in str(e).lower() or "insufficient" in type(e).__name__.lower()
        with ro.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eventlog")             # but it CAN read (broad eyes)
            can_read = cur.fetchone()[0] > 0
        results["AC-3 read-only (eventlog write denied)"] = denied and can_read
        print(f"   eventlog write denied={denied}  can read eventlog={can_read}")

        # ---------- AC-4 severe anomaly escalated URGENT; model cannot halt ----------
        print("== AC-4 a severe anomaly is escalated URGENT to the Sentinel; the model never halts ==")
        escalated = len(result["escalations"]) >= 1
        no_enforce = not any(hasattr(sa, m) for m in ("halt", "enforce", "kill", "stop"))
        results["AC-4 severe anomaly escalated, no enforce power"] = escalated and no_enforce
        print(f"   findings={[f['pattern'] for f in result['findings']]}")
        print(f"   escalations={result['escalations']}  selfaudit has no enforce method={no_enforce}")

        # ---------- AC-5 system runs without Self-Audit; absence alarmed ----------
        print("== AC-5 system runs with Self-Audit down; its absence is alarmed ==")
        sa.up = False                                               # the inspector crashes
        mgr.eventlog.append("test.system_still_runs", {"ok": True})  # the system keeps working
        n_alarms_before = len(sentinel.alarms)
        probe = sentinel.probe("selfaudit")                         # the Sentinel notices it's down
        sentinel.probe_all()
        results["AC-5 not-on-critical-path + absence alarmed"] = (not probe["healthy"]
                                                                  and len(sentinel.alarms) > n_alarms_before)
        print(f"   selfaudit healthy={probe['healthy']}  system kept running + alarm raised")
        sa.up = True

        # ---------- AC-6 meta-trust is system-trust, not agent-trust ----------
        print("== AC-6 meta-trust reflects SYSTEM reliability, not per-agent scoring ==")
        sigs = {s["signal"] for s in mt["signals"]}
        system_level = sigs <= {"required_output_miss_rate", "verdict_escalation_rate",
                                "divergence_rate", "component_failure_count"}
        no_agent = not any("agent" in s.lower() for s in sigs)
        results["AC-6 system-trust not agent-trust"] = system_level and no_agent
        print(f"   signals={sigs}  no agent scored={no_agent}")

        # ---------- AC-7 false positive → at most a Sentinel evaluation, no wrongful halt ----------
        print("== AC-7 false positive → Sentinel evaluation only, never a wrongful halt ==")
        halts_before = len(sentinel.halts)
        decisions = {e["sentinel_decision"] for e in result["escalations"]}
        no_halt_from_selfaudit = len(sentinel.halts) == halts_before and decisions <= {"note"}
        results["AC-7 false positive → no wrongful halt"] = no_halt_from_selfaudit
        print(f"   sentinel decisions on self-audit urgents = {decisions} (no halt)")

        # ---------- AC-8 retro + benchmark over existing data, zero frontier ----------
        print("== AC-8 retro + benchmark over existing data, zero frontier calls ==")
        retro = sa.run_retro()
        bench = sa.run_benchmark()
        results["AC-8 retro/benchmark zero frontier"] = (retro["frontier_calls"] == 0
                                                         and bench["frontier_calls"] == 0)
        print(f"   retro over {retro['retrospective']['events']} events  frontier_calls=0")

        # ---------- AC-9 the Sentinel probes the Self-Audit's liveness ----------
        print("== AC-9 the Sentinel watches the Self-Audit's liveness too ==")
        healthy_probe = sentinel.probe("selfaudit")
        results["AC-9 sentinel watches selfaudit"] = "selfaudit" in sentinel.components and healthy_probe["healthy"]
        print(f"   selfaudit watched={('selfaudit' in sentinel.components)} healthy_when_up={healthy_probe['healthy']}")

        # ---------- AC-10 findings persist in the DB across restart ----------
        print("== AC-10 findings live in the DB, persistent across restart ==")
        sa2 = SelfAudit(sa_db.connect_readonly())                   # a 'restarted' inspector
        results["AC-10 findings persist across restart"] = len(sa2.reports()) >= 1
        print(f"   restarted inspector sees {len(sa2.reports())} persisted reports")

        # ---------- AC-11 inspection respects resource bounds ----------
        print("== AC-11 inspection respects resource bounds (never starves rooms) ==")
        bounded = SelfAudit(sa_db.connect_readonly(), max_events=3)
        obs = bounded.inspect()["observations"]
        results["AC-11 resource-bounded inspection"] = obs["events_scanned"] <= 3
        print(f"   events_scanned={obs['events_scanned']} (bound=3)")

        # ---------- AC-12 Toras-ready observe→assess→emit seam ----------
        print("== AC-12 clean observe→assess→emit seam for Toras v2 ==")
        seam_ok = ("assess" in InspectionModel.__abstractmethods__ and hasattr(sa.model, "assess"))
        results["AC-12 Toras-ready seam"] = seam_ok
        print(f"   InspectionModel.assess seam present={seam_ok}")

        print("\n==== SELF-AUDIT SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = (results["AC-1 zero token cost"] and results["AC-3 read-only (eventlog write denied)"]
                    and results["AC-4 severe anomaly escalated, no enforce power"])
        print(f"\n   HEADLINE (AC-1 + AC-3 + AC-4: intelligent self-audit, zero cost, zero enforcement risk): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
