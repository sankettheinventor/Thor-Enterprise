"""
ONE-TIME smoke of the PM Surface (Module 8) — the human cockpit, against the real Manager.

Headline (PRD §15): AC-2 + AC-3 + AC-6 — a verified Ed25519 signature drives a real merge, governance
blocks are explained in plain language, and the cockpit never lets the operator sign against a stale
picture. Exercised via the DashboardService + cockpit logic against the REAL Manager (Postgres) +
Scheduler (M4) + a real Project Checker room (M7).

NOT the formal proving suite (Rule 2). No faked results (Rule 11). The React UI is deferred; the
DashboardAPI + logic (the substance) is what's proven here.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_pmsurface.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from dashboard import legible
from dashboard.service import DashboardService
from manager import db, pg
from manager.core import ThorManager
from scheduler.core import Scheduler
from scheduler.graph import Task
from sdlc.stages import CheckerStage
from wall.identity_stamper import _b64


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


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

        def make_sched(ready):
            return Scheduler([Task(f["feature_id"], (), "build", f.get("est_tokens", 1000)) for f in ready],
                             capacity=3)

        service = DashboardService(mgr, budget_cap=2000, scheduler_factory=make_sched)
        priv = Ed25519PrivateKey.generate()
        pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

        def sign(card_id, payload):
            return _b64(priv.sign(ThorManager.card_material(card_id, payload).encode()))

        # ---------- AC-1 kanban + mark-ready picked up by the Scheduler ----------
        print("== AC-1 kanban reflects state; mark-ready → Scheduler picks it up ==")
        fid = service.add_feature("Login form", "users log in", priority=1, est_tokens=2000)
        in_backlog = fid in [c["feature_id"] for c in service.kanban()["columns"]["backlog"]]
        service.mark_ready(fid)
        in_ready = fid in [c["feature_id"] for c in service.kanban()["columns"]["ready"]]
        dr = service.dry_run()
        picked = fid in [f for w in dr["waves"] for f in w]
        results["AC-1 kanban live + scheduler picks up ready"] = in_backlog and in_ready and picked
        print(f"   backlog→ready={in_backlog}/{in_ready}  scheduler picked up={picked}")

        # ---------- AC-2 verified signature drives a real merge; forged rejected ----------
        print("== AC-2 merge card: verified signature drives the merge; forged rejected ==")
        mc = mgr.raise_card("merge", fid, {"feature_id": fid})
        forged = service.approve(mc, sign(mc, {"wrong": True}), pub)        # forged material
        merged_after_forge = any(f["feature_id"] == fid and f["status"] == "done"
                                 for f in mgr.list_features())
        ok = service.approve(mc, sign(mc, {"feature_id": fid}), pub)        # valid signature
        merged = any(f["feature_id"] == fid and f["status"] == "done" for f in mgr.list_features())
        results["AC-2 verified sig drives merge, forged rejected"] = (
            not forged["verified"] and not merged_after_forge and ok["verified"] and merged)
        print(f"   forged_verified={forged['verified']} merged_after_forge={merged_after_forge} "
              f"valid_verified={ok['verified']} merged={merged}")

        # ---------- AC-3 legible refusal in plain language ----------
        print("== AC-3 legible refusal: plain language across reason codes ==")
        codes = ["scope_violation E0042", "governor_unavailable", "forbidden_pattern infra/secrets",
                 "dependency-manifest change", "high-stakes change", "claim-vs-reality divergence"]
        rendered = [legible.render(c, "F47") for c in codes]
        plain = all(len(r) > 25 and "E0042" not in r and "_violation" not in r for r in rendered)
        results["AC-3 legible refusal plain language"] = plain
        print(f"   e.g. {rendered[0]!r}")

        # ---------- AC-4 read-only logs, no room-mutation path ----------
        print("== AC-4 room logs read-only; no path to modify a room ==")
        logs = service.room_logs("room-x")
        no_mutate = (not logs["writable"]) and not any(
            hasattr(service, m) for m in ("exec_in_room", "modify_room", "write_room", "inject"))
        results["AC-4 read-only, no room mutation"] = no_mutate
        print(f"   logs.writable={logs['writable']}  no mutation methods={no_mutate}")

        # ---------- AC-5 holds no authoritative state ----------
        print("== AC-5 no authoritative state; reopen → same truth from the Manager ==")
        service2 = DashboardService(mgr, budget_cap=2000, scheduler_factory=make_sched)
        same = service2.kanban() == service.kanban() and service2.cost()["total_est"] == service.cost()["total_est"]
        only_refs = set(vars(service)) <= {"manager", "budget_cap", "scheduler_factory", "_disconnected"}
        results["AC-5 no authoritative state"] = same and only_refs
        print(f"   reopened view identical={same}  holds only references={only_refs}")

        # ---------- AC-6 disconnected disables signing, no stale-as-live ----------
        print("== AC-6 disconnected → signing disabled, never stale-as-live ==")
        mc2 = mgr.raise_card("merge", fid, {"feature_id": fid})
        service.set_disconnected(True)
        disc = service.state_summary()
        refused = service.approve(mc2, sign(mc2, {"feature_id": fid}), pub)
        service.set_disconnected(False)
        results["AC-6 disconnected disables signing"] = (
            disc["connected"] is False and not refused["verified"] and "disconnected" in refused["reason"])
        print(f"   connected={disc['connected']} sign_refused={not refused['verified']}")

        # ---------- AC-7 cost, caps, alert, dry-run ----------
        print("== AC-7 cost + caps + alert + dry-run (zero provisioning) ==")
        mgr.set_feature_status(fid, "building")           # spend accrues for a building feature
        costr = service.cost()
        dr2 = service.dry_run()
        results["AC-7 cost/caps/alert/dry-run"] = (
            costr["total_spent"] > 0 and costr["cap"] == 2000 and costr["alert"] and dr2["provisioned"] == 0)
        print(f"   spent={costr['total_spent']} cap={costr['cap']} alert={costr['alert']} dry_run_provisioned={dr2['provisioned']}")

        # ---------- AC-8 three signature cards, none auto-resolves ----------
        print("== AC-8 the three signature points appear as cards; none auto-resolves ==")
        mgr.raise_card("plan", fid, {"feature_id": fid})
        mgr.raise_card("qa_fail", fid, {"bugs": ["x"]}, held=True)
        mgr.raise_card("merge", "F99", {"feature_id": "F99"})
        types = {c["type"] for c in service.cards()}
        results["AC-8 three signature cards held"] = {"plan", "qa_fail", "merge"} <= types
        print(f"   card types pending = {types}")

        # ---------- AC-9 audit feed + export ----------
        print("== AC-9 audit feed + CSV/JSON export ==")
        feed = service.audit_feed()
        js = service.audit_export("json")
        csvexp = service.audit_export("csv")
        results["AC-9 audit feed + export"] = (
            len(feed) > 5 and len(json.loads(js)) == len(feed) and csvexp.startswith("seq,ts,actor"))
        print(f"   feed_events={len(feed)} csv_header_ok={csvexp.startswith('seq,ts,actor')}")

        # ---------- AC-10 Project Checker findings view matches DB ----------
        print("== AC-10 Project Checker findings render and match the DB ==")
        rchk = REPO / ".smoke" / "pm-legacy"
        if rchk.exists():
            shutil.rmtree(rchk)
        rchk.mkdir(parents=True)
        git(str(rchk), "init", "-q", "-b", "main")
        open(rchk / "bad.py", "w").write("y = eval('2+2')  # TODO clean up\n")
        git(str(rchk), "add", "-A"); git(str(rchk), "-c", "user.email=h@t", "-c", "user.name=h", "commit", "-q", "-m", "legacy")
        CheckerStage().execute(repo=str(rchk), manager=mgr)
        view = service.findings()
        results["AC-10 checker findings view matches DB"] = (
            len(view) >= 1 and view == mgr.list_checker_findings())
        print(f"   findings rendered={len(view)}")

        # ---------- AC-11 operator actions recorded ----------
        print("== AC-11 every operator action recorded as an event ==")
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT payload FROM eventlog WHERE event_type='dashboard.action'")
            actions = {json.loads(r[0]).get("action") for r in cur.fetchall()}
        results["AC-11 operator actions recorded"] = {"add_feature", "mark_ready", "approve"} <= actions
        print(f"   recorded operator actions = {actions}")

        # ---------- AC-12 desktop+mobile consistent (idempotent one decision) ----------
        print("== AC-12 same card resolved once across heads (desktop+mobile consistency) ==")
        fid2 = service.add_feature("Profile", "edit profile", priority=2)
        mc3 = mgr.raise_card("merge", fid2, {"feature_id": fid2})
        first = service.approve(mc3, sign(mc3, {"feature_id": fid2}), pub)   # "desktop"
        second = service.approve(mc3, sign(mc3, {"feature_id": fid2}), pub)  # "mobile" — same card
        results["AC-12 one decision across heads"] = first["verified"] and not second["verified"]
        print(f"   first_verified={first['verified']} second={second}")

        print("\n==== PM-SURFACE SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = (results["AC-2 verified sig drives merge, forged rejected"]
                    and results["AC-3 legible refusal plain language"]
                    and results["AC-6 disconnected disables signing"])
        print(f"\n   HEADLINE (AC-2 + AC-3 + AC-6: real, legible, safe human command): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        for c in client.containers.list(all=True, filters={"label": "thor.room"}):
            try:
                c.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
