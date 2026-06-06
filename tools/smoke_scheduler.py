"""
ONE-TIME smoke demonstration of the Scheduler (Module 4).

Headline (PRD §15): AC-1 + AC-2 — a deterministic schedule produced with zero LLM calls in the
loop, reproducible on replay. Part A is pure logic (AC-1/2/3/4/5/6/7/8/9/11/12); Part B drives the
REAL Manager (Postgres + Wall) for AC-10 (restart without double-dispatch) + the real handoff.

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real schedules, real rooms.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_scheduler.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from scheduler import cto_stub
from scheduler.core import Scheduler
from scheduler.graph import GraphError, Task


def T(fid, deps=(), task_type="build", est=1000, status="pending", ready=True):
    return Task(fid, tuple(deps), task_type, est, status, ready)


def deps_respected(schedule, graph) -> bool:
    seen: set[str] = set()
    for wave in schedule.waves:
        for fid in wave:
            if not all(d in seen for d in graph.tasks[fid].depends_on):
                return False
        seen.update(wave)
    return True


def part_a() -> dict:
    results: dict[str, bool] = {}

    # A multi-level DAG (PRD Figure 1): F12/F13/F14 -> F20,F21 -> F30
    dag = [T("F12"), T("F13"), T("F14"), T("F20", ["F12"]), T("F21", ["F13", "F14"]),
           T("F30", ["F20", "F21"])]

    print("== AC-1 — determinism: same inputs twice → byte-identical ==")
    s1 = Scheduler([T(*[t.feature_id], deps=t.depends_on) for t in dag], capacity=3).plan().to_json()
    s2 = Scheduler([T(t.feature_id, t.depends_on) for t in dag], capacity=3).plan().to_json()
    results["AC-1 deterministic byte-identical"] = (s1 == s2)
    print(f"   schedule == schedule(rerun): {s1 == s2}")
    print(f"   waves: {s1}")

    print("== AC-2 — zero LLM/planning calls during scheduling ==")
    cto_stub.reset_counter()
    sch = Scheduler([T(t.feature_id, t.depends_on) for t in dag], capacity=3)
    sch.plan()
    sch.dry_run()
    results["AC-2 zero planning calls while scheduling"] = (cto_stub.PLAN_CALLS == 0)
    print(f"   cto planning calls after plan()+dry_run(): {cto_stub.PLAN_CALLS}")

    print("== AC-3 — unmet dependency never dispatches early ==")
    sched = Scheduler([T(t.feature_id, t.depends_on) for t in dag], capacity=3)
    results["AC-3 deps respected across levels"] = deps_respected(sched.plan(), sched.graph)

    print("== AC-4 — capacity cap queues the overflow ==")
    three = [T("A"), T("B"), T("C")]                       # 3 independent level-0
    waves = Scheduler(three, capacity=2).plan().waves
    results["AC-4 cap queues overflow"] = (len(waves[0]) == 2 and "C" in waves[1])
    print(f"   cap=2 waves: {waves}")

    print("== AC-5 — dry-run provisions nothing ==")
    dr = Scheduler([T(t.feature_id, t.depends_on) for t in dag], capacity=3).dry_run()
    results["AC-5 dry-run zero provisioning"] = (dr["provisioned"] == 0 and dr["cost_estimate"] > 0)
    print(f"   dry_run provisioned={dr['provisioned']} cost_estimate={dr['cost_estimate']}")

    print("== AC-6 — budget cap halts before any dispatch ==")
    dispatched_calls = []
    big = [T("X", est=5000), T("Y", est=5000)]
    res = Scheduler(big, capacity=2, budget_cap=3000).run(lambda f, tt: dispatched_calls.append(f))
    results["AC-6 budget halts dispatch"] = (res["status"] == "halted_budget" and not dispatched_calls)
    print(f"   run status={res['status']} wave_cost={res.get('wave_cost')} dispatched={dispatched_calls}")

    print("== AC-7 — same order at capacity 3 vs 10 (only concurrency differs) ==")
    # 5 level-0 + 2 level-1 that depend on ALL level-0 (clean levels, no interleaving)
    l0 = [T(f"L{i}") for i in range(5)]
    l1 = [T("M0", [t.feature_id for t in l0]), T("M1", [t.feature_id for t in l0])]
    cat = l0 + l1
    flat3 = Scheduler([T(t.feature_id, t.depends_on) for t in cat], capacity=3).plan().flatten()
    flat10 = Scheduler([T(t.feature_id, t.depends_on) for t in cat], capacity=10).plan().flatten()
    results["AC-7 same order, different capacity"] = (flat3 == flat10)
    print(f"   cap3 == cap10 order: {flat3 == flat10}  ({flat3})")

    print("== AC-8 — re-work re-dispatches without re-running done deps ==")
    rw = [T("D20", status="done"), T("D30", ["D20"], status="done")]
    sched = Scheduler(rw, capacity=3)
    sched.mark_rework("D30")
    flat = sched.plan().flatten()
    results["AC-8 rework no dep re-run"] = ("D30" in flat and "D20" not in flat)
    print(f"   after re-work of D30, schedule: {flat}")

    print("== AC-9 — Genesis-first: no build until the plan is signed ==")
    b = [T("B1"), T("B2")]
    unsigned = Scheduler([T(t.feature_id) for t in b], capacity=3, plan_approved=False).plan().waves
    signed = Scheduler([T(t.feature_id) for t in b], capacity=3, plan_approved=True).plan().waves
    results["AC-9 genesis-first gate"] = (unsigned == [] and signed != [])
    print(f"   unsigned waves={unsigned}  signed waves={signed}")

    print("== AC-11 — cyclic catalog rejected at load ==")
    try:
        Scheduler([T("P", ["Q"]), T("Q", ["P"])], capacity=2)
        results["AC-11 cycle rejected"] = False
    except GraphError as e:
        results["AC-11 cycle rejected"] = "cycle" in str(e).lower()
        print(f"   rejected: {e}")

    print("== AC-12 — replay reproduces the exact schedule ==")
    original = Scheduler([T(t.feature_id, t.depends_on) for t in dag], capacity=3).plan().to_json()
    record = [(t.feature_id, t.depends_on) for t in dag]                # the 'recorded plan' inputs
    replayed = Scheduler([T(fid, deps) for fid, deps in record], capacity=3).plan().to_json()
    results["AC-12 replay reproduces schedule"] = (original == replayed)
    print(f"   replay == original: {original == replayed}")

    return results


def part_b() -> dict:
    """AC-10 + the real handoff: dispatch real rooms via the Manager, then restart without dup."""
    from manager import db, pg
    from manager.core import ThorManager
    from wall import provisioner

    results: dict[str, bool] = {}
    client = docker.from_env()
    rooms: list[str] = []
    try:
        print("== Part B: real Manager (Postgres + Wall) ==")
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features")
        mgr = ThorManager(conn)

        catalog = [Task("F100"), Task("F200")]
        sched = Scheduler([Task(t.feature_id) for t in catalog], capacity=2)

        cto_stub.reset_counter()

        def dispatch(fid, task_type):
            cto_stub.plan_task(fid, task_type)                  # the ONE planning call (CTO, not Scheduler)
            room = mgr.provision_room(fid, task_type="build", network_mode="sealed")
            rooms.append(room["room_id"])

        run1 = sched.run(dispatch)
        print(f"   run1 dispatched={run1['dispatched']}  cto planning calls={cto_stub.PLAN_CALLS}")

        # the Scheduler itself made zero LLM calls; the CTO made one per dispatched task
        results["AC-2 (real) scheduler zero LLM; CTO planned each"] = (cto_stub.PLAN_CALLS == 2)

        print("== AC-10 — 'restart' the Scheduler; rebuild from Manager events; no double-dispatch ==")
        sched2 = Scheduler([Task(t.feature_id) for t in catalog], capacity=2)
        sched2.rebuild_from_manager(mgr)                        # sees F100/F200 already running
        run2 = sched2.run(dispatch)
        results["AC-10 restart, no double-dispatch"] = (run2["dispatched"] == [])
        print(f"   after restart, run2 dispatched={run2['dispatched']} (expected [])  state={sched2.state()}")

        return results
    finally:
        for rid in rooms:
            try:
                provisioner.destroy_room(rid)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


def main() -> int:
    results = {}
    print("########## PART A — pure deterministic logic ##########")
    results.update(part_a())
    print("\n########## PART B — real Manager integration ##########")
    try:
        results.update(part_b())
    except Exception as e:  # noqa: BLE001 - report honestly, don't fake
        print(f"   PART B ERROR: {e}")
        results["PART B integration"] = False

    print("\n==== SCHEDULER SMOKE RESULTS (real, observed) ====")
    for k, v in results.items():
        print(f"   [{'PASS' if v else 'FAIL'}] {k}")
    headline = results.get("AC-1 deterministic byte-identical") and \
        results.get("AC-2 zero planning calls while scheduling")
    print(f"\n   HEADLINE (AC-1 + AC-2: deterministic + zero-LLM): {'PASS' if headline else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
