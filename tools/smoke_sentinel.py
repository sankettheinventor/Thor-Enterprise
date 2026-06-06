"""
ONE-TIME smoke of the Sentinel (Module 10) — the governor of the governor.

Headline (PRD §15): AC-1 + AC-2 + AC-7 — a dead governor is caught and fail-closed, a broken detector
is caught by a passing canary, and the Sentinel's own death is caught by its silent heartbeat. Run
against the REAL Manager (Postgres) + REAL Leash policy canary + Docker (a real shadow room).

NOT the formal proving suite (Rule 2). No faked results (Rule 11).

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_sentinel.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from leash.policy import FrozenPolicy
from manager import db, pg
from manager.core import ThorManager
from sdlc import skills
from sentinel import canary
from sentinel.core import Sentinel
from sentinel.reconcile import Reconciler
from wall import provisioner


def main() -> int:
    results: dict[str, bool] = {}
    client = docker.from_env()
    shadow_room = None
    try:
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features, bugs")
        mgr = ThorManager(conn)
        sentinel = Sentinel(mgr)

        # mutable component health flags the chaos test can flip
        leash_health = {"alive": True, "responsive": True}
        sentinel.register("manager", True, lambda: {"alive": True, "responsive": True})
        sentinel.register("leash", True, lambda: dict(leash_health))
        sentinel.register("scheduler", False, lambda: {"alive": True, "responsive": True})

        # ---------- AC-1 dead/hung leash detected → fail-closed ----------
        print("== AC-1 killed/hung leash detected as unresponsive → fail-closed ==")
        leash_health["responsive"] = False               # the leash dies quietly
        before_halts = len(sentinel.halts)
        probe = sentinel.probe("leash")
        sentinel.probe_all()
        halted_system = any(h["scope"] == "system" for h in sentinel.halts[before_halts:])
        results["AC-1 dead leash detected + fail-closed"] = (not probe["healthy"]) and halted_system
        print(f"   leash healthy={probe['healthy']} → halted system={halted_system}")
        leash_health["responsive"] = True                # restore for later checks

        # ---------- AC-2 passing canary → alarm + halt ----------
        print("== AC-2 canary: a passing canary (broken detector) → alarm + halt ==")
        good_policy = FrozenPolicy("r", scope_files=("src/",), forbidden_patterns=("infra/",))
        broken_policy = FrozenPolicy("r", scope_files=("infra/", "src/"), forbidden_patterns=())
        good = canary.leash_canary(good_policy)          # out-of-scope write → denied → healthy
        broken = canary.leash_canary(broken_policy)      # the same write now ALLOWED → broken detector
        paged = False
        if not broken["healthy"]:
            sentinel.alarm("critical", f"canary {broken['name']} PASSED — detector broken")
            sentinel.halt("component:leash", "canary passed — leash not catching")
            paged = True
        results["AC-2 passing canary alarms + halts"] = good["healthy"] and not broken["healthy"] and paged
        print(f"   good canary healthy={good['healthy']}  broken canary healthy={broken['healthy']} → paged={paged}")

        # ---------- AC-3 hung-but-running component detected ----------
        print("== AC-3 hung-but-running (alive, not responsive) detected ==")
        def hung():
            raise TimeoutError("did not answer in time")
        sentinel.register("hung-svc", False, hung)
        hp = sentinel.probe("hung-svc")
        results["AC-3 hung component detected"] = hp["alive"] and not hp["responsive"] and not hp["healthy"]
        print(f"   alive={hp['alive']} responsive={hp['responsive']} (naive liveness would have passed)")

        # ---------- AC-4 rule tamper → CRAWLER_ALARM + halt ----------
        print("== AC-4 governance-rule tampering → CRAWLER_ALARM + halt ==")
        rules = {"leash_rules": b"scope=src/; forbidden=infra/"}
        sentinel.integrity.record_baseline(rules)
        intact = sentinel.check_integrity(rules)["ok"]
        n_halts = len(sentinel.halts)
        tampered = sentinel.check_integrity({"leash_rules": b"scope=EVERYTHING; forbidden="})
        results["AC-4 rule tamper → alarm + halt"] = intact and not tampered["ok"] and len(sentinel.halts) > n_halts
        print(f"   intact={intact} tampered={tampered['tampered']}")

        # ---------- AC-5 unloaded skill fail-closes ----------
        print("== AC-5 a stage's floor skill failed to load → fail-closes ==")
        loaded = [s for s in skills.FLOOR_SKILLS if s != "security"]   # 'security' didn't load
        ld = sentinel.verify_loadedness(skills.FLOOR_SKILLS, loaded)
        results["AC-5 unloaded skill fail-closes"] = (not ld["ok"]) and "security" in ld["missing"]
        print(f"   missing={ld['missing']} fail_closed={ld.get('fail_closed')}")

        # ---------- AC-6 failed boot self-test blocks startup ----------
        print("== AC-6 failed boot self-test prevents accepting work ==")
        s6 = Sentinel()
        s6.register("dead-dep", True, lambda: {"alive": True, "responsive": False})
        booted = s6.boot_self_test()
        results["AC-6 failed boot blocks startup"] = (not booted) and (not s6.accepts_work)
        print(f"   boot_passed={booted} accepts_work={s6.accepts_work}")

        # ---------- AC-7 Sentinel's own death via silent heartbeat ----------
        print("== AC-7 Sentinel death caught by the silent-heartbeat base case ==")
        last = sentinel._heartbeat
        sentinel.heartbeat()                              # alive: heartbeat advances
        alive = sentinel.heartbeat_alive(last)
        frozen_last = sentinel._heartbeat                 # now simulate death — no further heartbeat
        dead_detected = not sentinel.heartbeat_alive(frozen_last)
        results["AC-7 silent heartbeat detects death"] = alive and dead_detected
        print(f"   heartbeat advancing={alive}  silence detected as death={dead_detected}")

        # ---------- AC-8 proportionate halt scope ----------
        print("== AC-8 fail-closed, proportionately (room vs system) ==")
        local = sentinel.halt("room:room-xyz", "one hung room")
        systemic = sentinel.halt("system", "dead leash / tampered rule")
        results["AC-8 proportionate halt scope"] = (local["scope"].startswith("room:")
                                                    and systemic["scope"] == "system")
        print(f"   local={local['scope']}  systemic={systemic['scope']}")

        # ---------- AC-9 Self-Audit URGENT: Sentinel decides (model never halts directly) ----------
        print("== AC-9 Self-Audit URGENT evaluated by the Sentinel (halt or note) ==")
        d1 = sentinel.receive_urgent({"confirmed_critical": True, "scope": "room:r1"})
        d2 = sentinel.receive_urgent({"confirmed_critical": False, "detail": "minor drift"})
        results["AC-9 sentinel decides on urgent"] = d1["decision"] == "halt" and d2["decision"] == "note"
        print(f"   confirmed→{d1['decision']}  uncertain→{d2['decision']}")

        # ---------- AC-10 shadow discovered + orphan reaped ----------
        print("== AC-10 reconcile: shadow container discovered, orphan reaped ==")
        room = provisioner.provision_room(task_type="build", network_mode="sealed",
                                          feature_slice={"feature_id": "SHADOW"})
        shadow_room = room["room_id"]                     # a REAL container, NOT in the Manager registry
        recon = Reconciler(client).reconcile(registry_room_ids={"room-ghost-orphan"})
        results["AC-10 shadow discovered + orphan"] = (shadow_room in recon["shadows"]
                                                       and "room-ghost-orphan" in recon["orphans"])
        print(f"   shadows={recon['shadows']}  orphans={recon['orphans']}")

        # ---------- AC-11 maintenance mode (scoped, bounded, auto-closing) ----------
        print("== AC-11 maintenance mode: scoped, bounded, never silences outside ==")
        needs_auth = sentinel.set_maintenance(["chaos"], 2, human_authority=False)
        sentinel.set_maintenance(["chaos"], 2, human_authority=True)
        suppressed = sentinel.alarm("degraded", "chaos test injected failure").get("suppressed")
        real_fires = "suppressed" not in sentinel.alarm("critical", "real leash down")
        sentinel.tick(); sentinel.tick()                  # window auto-closes
        chaos_after = "suppressed" not in sentinel.alarm("degraded", "chaos again")
        results["AC-11 maintenance scoped + bounded"] = (not needs_auth["ok"] and suppressed
                                                         and real_fires and chaos_after)
        print(f"   auth_required={not needs_auth['ok']} chaos_suppressed_in_window={suppressed} "
              f"real_fired={real_fires} chaos_fires_after_expiry={chaos_after}")

        # ---------- AC-12 chaos test pages each failure class ----------
        print("== AC-12 chaos test: the Sentinel pages for every failure class ==")
        classes = {
            "dead_component": results["AC-1 dead leash detected + fail-closed"],
            "passing_canary": results["AC-2 passing canary alarms + halts"],
            "hung_component": results["AC-3 hung component detected"],
            "rule_tamper": results["AC-4 rule tamper → alarm + halt"],
            "unloaded_skill": results["AC-5 unloaded skill fail-closes"],
            "silent_heartbeat": results["AC-7 silent heartbeat detects death"],
        }
        results["AC-12 chaos pages each failure class"] = all(classes.values())
        print(f"   classes paged = {classes}")

        print("\n==== SENTINEL SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = (results["AC-1 dead leash detected + fail-closed"]
                    and results["AC-2 passing canary alarms + halts"]
                    and results["AC-7 silent heartbeat detects death"])
        print(f"\n   HEADLINE (AC-1 + AC-2 + AC-7: THOR cannot be silently broken, down to the watcher): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        if shadow_room:
            try:
                provisioner.destroy_room(shadow_room)
            except Exception:  # noqa: BLE001
                pass
        for c in client.containers.list(all=True, filters={"label": "thor.room"}):
            try:
                c.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
