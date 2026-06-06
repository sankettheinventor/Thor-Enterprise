"""
ONE-TIME smoke demonstration of the THOR Manager (Module 3) against REAL Postgres + REAL rooms.

Headline (PRD §15): AC-2 + AC-3 — a tamper-evident signed EventLog that the Manager replays to
rebuild exact state after a crash. Also demonstrates AC-1/4/5/7/8/9/10/11/12.

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real Postgres rows, real
containers, real Ed25519 signatures. AC-6 (claim_done→QA→verdict) needs Module 6 and is deferred.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_manager.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from adapters import agt_adapter
from leash.policy import FrozenPolicy
from leash.proxy import InRoomProxy
from manager import db, pg
from manager.core import FailClosed, ThorManager
from wall.identity_stamper import _b64

CLIENT = docker.from_env()


def operator_keys():
    priv = Ed25519PrivateKey.generate()
    pub_b64 = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub_b64


def main() -> int:
    results: dict[str, bool] = {}
    rooms: list[str] = []
    try:
        print("== 0. start Postgres + schema ==")
        pg.start(CLIENT)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features")
        conn.commit()
        mgr = ThorManager(conn)
        print("   postgres up, schema ready")

        print("== 1. provision two REAL governed rooms (Manager drives the Wall) ==")
        room_a = mgr.provision_room("F100", task_type="build", network_mode="sealed")
        room_b = mgr.provision_room("F200", task_type="build", network_mode="sealed")
        rooms = [room_a["room_id"], room_b["room_id"]]
        print(f"   registered: {room_a['room_id']} (F100), {room_b['room_id']} (F200)")

        print("== AC-9 — second provision on an already-owned branch is refused ==")
        try:
            mgr.provision_room("F100", task_type="build")
            ac9 = False
        except ValueError as e:
            ac9 = "one-branch-one-room" in str(e)
        results["AC-9 one-branch-one-room"] = ac9

        print("== AC-8 — identity verification (good token trusted, bad token refused) ==")
        good = mgr.verify_room_identity(room_a["room_id"], room_a["identity_token"])
        bad = mgr.verify_room_identity(room_a["room_id"], "forged.token")
        results["AC-8 bad identity refused"] = good and not bad

        print("== AC-1 — the Leash records THROUGH the Manager (single writer) ==")
        policy = FrozenPolicy(room_id=room_a["room_id"], scope_files=("src/",),
                              forbidden_patterns=("infra/",), frozen_at=0.0)
        agt_adapter.load_policy(policy)
        wt = REPO / ".smoke" / "mgr-work"
        if wt.exists():
            shutil.rmtree(wt)
        (wt / "src").mkdir(parents=True)
        proxy = InRoomProxy(agt_adapter, mgr, str(wt))   # the Manager IS the recorder
        proxy.handle_tool_call({"name": "write_file", "room_id": room_a["room_id"],
                                "args": {"path": "src/ok.js", "content": "// ok"}})
        proxy.handle_tool_call({"name": "write_file", "room_id": room_a["room_id"],
                                "args": {"path": "infra/secrets.tf", "content": "leak"}})
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eventlog WHERE event_type='action.decided' AND actor='leash'")
            decided = cur.fetchone()[0]
        results["AC-1 Leash records via Manager"] = decided == 2
        print(f"   action.decided events written by the Manager (actor=leash): {decided}")

        print("== AC-4/AC-5 — signature gates + forged signature rejected ==")
        priv, pub_b64 = operator_keys()
        card_plan = mgr.raise_card("plan", "F300", {"summary": "build plan for F300"})
        before = mgr.is_card_approved(card_plan)               # AC-4: not approved yet
        forged = mgr.approve(card_plan, _b64(priv.sign(b"wrong material")), pub_b64)
        stays_open = not mgr.is_card_approved(card_plan)        # AC-5: forged → still open
        material = ThorManager.card_material(card_plan, {"summary": "build plan for F300"})
        good_sig = _b64(priv.sign(material.encode()))
        ok = mgr.approve(card_plan, good_sig, pub_b64)
        after = mgr.is_card_approved(card_plan)                 # AC-4: now approved
        results["AC-4 signature gates the plan"] = (not before) and after
        results["AC-5 forged signature rejected, card stays open"] = (not forged["verified"]) and stays_open
        print(f"   plan: approved_before={before} forged_verified={forged['verified']} "
              f"stayed_open={stays_open} approved_after={after}")

        print("== AC-11 — an escalated (held) card is never auto-resolved ==")
        card_crit = mgr.raise_card("critical", "F400", {"what": "dependency add"}, held=True)
        still_held = mgr._get_card(card_crit)["status"] == "held"
        results["AC-11 held card not auto-resolved"] = still_held

        print("== AC-12 — duplicate event append (retry) is idempotent ==")
        n0 = mgr.eventlog.count()
        mgr.eventlog.append("test.retry", {"x": 1}, client_id="DUP-1")
        n1 = mgr.eventlog.count()
        dup = mgr.eventlog.append("test.retry", {"x": 1}, client_id="DUP-1")
        n2 = mgr.eventlog.count()
        results["AC-12 idempotent append"] = (n1 == n0 + 1) and (n2 == n1) and dup.get("idempotent")

        print("== AC-3 (HEADLINE) — capture state, then crash+restart replays to EXACT state ==")
        s1 = mgr.state_summary()
        conn2 = db.connect()
        mgr2 = ThorManager(conn2, stamper=mgr.stamper)   # a 'restarted' Manager on the same DB
        mgr2.rebuild_from_log()                          # projections lost → rebuilt purely by replay
        s2 = mgr2.state_summary()
        results["AC-3 replay rebuilds exact state"] = (s1 == s2)
        print(f"   state rooms={len(s1['rooms'])} cards={len(s1['cards'])}  rebuilt_matches={s1 == s2}")

        print("== AC-10 — Sentinel reads the Manager's true health ==")
        h = mgr.health()
        results["AC-10 truthful health"] = h["alive"] and h["eventlog_writable"] and h["deps"]["postgres"]
        print(f"   health={h}")

        print("== AC-7 — EventLog unwritable => Manager refuses governed actions (fail-closed) ==")
        n_before = mgr.eventlog.count()
        mgr.set_eventlog_writable(False)
        refused = False
        try:
            mgr.record_decision(type("V", (), {"decision": "allow", "reason": "x",
                                                "classification": "non_critical"})(),
                                {"room_id": room_a["room_id"], "type": "tool_call",
                                 "name": "write_file", "target": "src/x.js"})
        except FailClosed:
            refused = True
        n_after = mgr.eventlog.count()
        mgr.set_eventlog_writable(True)
        results["AC-7 fail-closed (no unaudited actions)"] = refused and (n_after == n_before)

        print("== AC-2 (HEADLINE) — signed hash chain is tamper-evident ==")
        chain_before = mgr.eventlog.verify_chain()
        with conn.cursor() as cur:                       # tamper a past event's payload
            cur.execute("UPDATE eventlog SET payload=%s WHERE seq=0", ('{"tampered":true}',))
        conn.commit()
        chain_after = mgr.eventlog.verify_chain()
        results["AC-2 tamper-evident signed chain"] = chain_before and not chain_after
        print(f"   verify_chain before_tamper={chain_before}  after_tamper={chain_after}")

        print("\n==== MANAGER SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = results["AC-2 tamper-evident signed chain"] and results["AC-3 replay rebuilds exact state"]
        print(f"\n   HEADLINE (AC-2 + AC-3: authoritative + crash-safe): {'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        for rid in rooms:
            try:
                from wall import provisioner
                provisioner.destroy_room(rid)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(CLIENT)


if __name__ == "__main__":
    sys.exit(main())
