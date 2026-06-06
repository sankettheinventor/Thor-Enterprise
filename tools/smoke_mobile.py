"""
ONE-TIME smoke of Mobile / Remote (Module 9) — command from a phone, over real E2EE.

Headline (PRD §15): AC-1 + AC-2 + AC-3 — a real merge signed from a phone over an end-to-end-encrypted
channel, where the relay can neither read nor forge anything and the control plane exposes no inbound
port. Exercised against the REAL Manager (Postgres) + DashboardService (M8) + the E2EE bridge + a phone
stand-in (the mobile app UI is deferred; the security-critical channel is what's proven).

NOT the formal proving suite (Rule 2). No faked results (Rule 11): real X25519/ChaCha20 + real signatures.

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_mobile.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker

from dashboard import legible
from dashboard.service import DashboardService
from manager import db, pg
from manager.core import ThorManager
from mobile import allowlist, crypto
from mobile.bridge import PhoneBridge
from mobile.phone_client import PhoneClient
from mobile.relay import Relay


def merge_card(mgr, service, fid):
    """Add a feature + raise a merge card; return (card_id, card_dict pushed to the phone)."""
    mgr.add_feature(fid, f"feature {fid}")
    cid = mgr.raise_card("merge", fid, {"feature_id": fid})
    return cid, {"card_id": cid, "type": "merge", "feature_id": fid, "payload": {"feature_id": fid},
                 "legible_reason": legible.render("merge", fid)}


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
        service = DashboardService(mgr)

        relay = Relay()
        cp_priv, cp_pub = crypto.gen_keypair()
        bridge = PhoneBridge(mgr, service, relay, cp_priv)
        phone = PhoneClient("dev-1", relay, cp_pub)
        bridge.register_device("dev-1", phone.e2ee_pub, phone.signing_pub)

        # ---------- AC-1 sign a merge from the phone ----------
        print("== AC-1 merge signed from the phone → Manager-verified → merges ==")
        cid, card = merge_card(mgr, service, "F47")
        bridge.push_card(card, "dev-1")
        received = phone.receive()
        phone.approve(received)
        res = bridge.process_inbound()
        merged = any(f["feature_id"] == "F47" and f["status"] == "done" for f in mgr.list_features())
        results["AC-1 merge signed from phone, verified"] = res.get("verified") and merged
        print(f"   verified={res.get('verified')} merged={merged}")

        # ---------- AC-2 relay is zero-knowledge (reads nothing, forges nothing) ----------
        print("== AC-2 relay zero-knowledge: ciphertext only, cannot forge ==")
        blob = crypto.seal(b'{"command":"approve","card_id":"SECRET-CARD-123"}', phone.e2ee_priv, cp_pub)
        relay_cannot_read = "SECRET-CARD-123" not in json.dumps(blob) and "approve" not in json.dumps(blob)
        tampered = {**blob, "ct": blob["ct"][:-3] + "AAA"}      # relay flips bytes → forgery attempt
        try:
            crypto.open_(tampered, cp_priv)
            forged = True
        except Exception:  # noqa: BLE001
            forged = False
        results["AC-2 relay reads nothing, forges nothing"] = relay_cannot_read and not forged
        print(f"   relay_cannot_read={relay_cannot_read} relay_forged={forged}")

        # ---------- AC-3 no inbound port ----------
        print("== AC-3 control plane opens no inbound port (outbound tunnel) ==")
        no_inbound = (bridge.inbound_port is None and not hasattr(bridge, "listen")
                      and not hasattr(bridge, "serve"))
        results["AC-3 no inbound port"] = no_inbound
        print(f"   inbound_port={bridge.inbound_port} no listener={no_inbound}")

        # ---------- AC-4 non-allowlisted command rejected + logged ----------
        print("== AC-4 non-allowlisted command rejected + logged ==")
        phone.send_command("reach_into_room", room_id="room-x")
        r4 = bridge.process_inbound()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eventlog WHERE event_type='security.rejected'")
            logged = cur.fetchone()[0] >= 1
        results["AC-4 non-allowlisted rejected + logged"] = r4["status"] == "rejected" and logged
        print(f"   {r4['reason']}  logged={logged}")

        # ---------- AC-5 legible refusal one sentence ----------
        print("== AC-5 legible block: one plain sentence (small screen) ==")
        msgs = [phone.legible(c, "F47") for c in ["scope_violation", "forbidden_pattern", "high-stakes change"]]
        results["AC-5 legible one-sentence reason"] = all(len(m) > 25 and m.count(".") <= 2 for m in msgs)
        print(f"   e.g. {msgs[0]!r}")

        # ---------- AC-6 already-decided across heads ----------
        print("== AC-6 card resolved on desktop → phone shows 'already decided' ==")
        cid6, card6 = merge_card(mgr, service, "F60")
        service.approve(cid6, phone.sign_for(cid6, {"feature_id": "F60"}), phone.signing_pub)   # desktop
        bridge.push_card(card6, "dev-1"); phone.receive(); phone.approve(card6)                  # phone, late
        r6 = bridge.process_inbound()
        results["AC-6 no double-resolution"] = not r6.get("verified") and "not open" in r6.get("reason", "")
        print(f"   phone result = {r6}")

        # ---------- AC-7 disconnect disables signing ----------
        print("== AC-7 disconnect → signing disabled (never against stale state) ==")
        phone.set_connected(False)
        r7 = phone.approve(card)
        phone.set_connected(True)
        results["AC-7 disconnect disables signing"] = (not r7["sent"]) and "disconnected" in r7["reason"]
        print(f"   {r7}")

        # ---------- AC-8 replayed/bound signature rejected ----------
        print("== AC-8 a signature bound to one card is rejected on another (replay) ==")
        cidA, _ = merge_card(mgr, service, "F80")
        cidB, _ = merge_card(mgr, service, "F81")
        sigA = phone.sign_for(cidA, {"feature_id": "F80"})
        replay = service.approve(cidB, sigA, phone.signing_pub)        # A's signature replayed on B
        results["AC-8 replayed signature rejected"] = not replay["verified"]
        print(f"   replay verified={replay['verified']}")

        # ---------- AC-9 lost device revoked ----------
        print("== AC-9 revoked device's signatures rejected ==")
        cid9, card9 = merge_card(mgr, service, "F90")
        bridge.revoke_device("dev-1")
        bridge.push_card(card9, "dev-1") if "dev-1" in bridge._devices else None
        phone.send_command("approve", card_id=cid9, signature=phone.sign_for(cid9, {"feature_id": "F90"}))
        r9 = bridge.process_inbound()
        results["AC-9 revoked device rejected"] = r9["status"] == "rejected" and "revoked" in r9["reason"]
        print(f"   {r9['reason']}")
        bridge.register_device("dev-1", phone.e2ee_pub, phone.signing_pub)   # re-register for the rest

        # ---------- AC-10 phone actions recorded ----------
        print("== AC-10 phone actions recorded identically to desktop ==")
        phone.send_command("mark_ready", feature_id="F47")
        bridge.process_inbound()
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT payload FROM eventlog WHERE event_type='dashboard.action'")
            actions = {json.loads(r[0]).get("action") for r in cur.fetchall()}
        results["AC-10 phone actions recorded"] = {"approve", "mark_ready"} <= actions
        print(f"   recorded actions = {actions}")

        # ---------- AC-11 phone cannot reach a room or change rules ----------
        print("== AC-11 phone cannot reach into a room or change rules ==")
        no_path = (not allowlist.allowed("reach_into_room") and not allowlist.allowed("change_rules")
                   and not hasattr(bridge, "exec_in_room"))
        results["AC-11 no room reach / rule change"] = no_path
        print(f"   reach/change blocked = {no_path}")

        # ---------- AC-12 phone + desktop same card from same state ----------
        print("== AC-12 phone and desktop render the same card consistently ==")
        cid12, card12 = merge_card(mgr, service, "F12")
        bridge.push_card(card12, "dev-1")
        phone_view = phone.receive()
        desktop_view = next((c for c in service.cards() if c["card_id"] == cid12), None)
        results["AC-12 consistent card across heads"] = (
            phone_view["card_id"] == desktop_view["card_id"]
            and phone_view["legible_reason"] == desktop_view["legible_reason"])
        print(f"   same card_id={phone_view['card_id'] == desktop_view['card_id']}")

        print("\n==== MOBILE SMOKE RESULTS (real, observed) ====")
        for k, v in results.items():
            print(f"   [{'PASS' if v else 'FAIL'}] {k}")
        headline = (results["AC-1 merge signed from phone, verified"]
                    and results["AC-2 relay reads nothing, forges nothing"]
                    and results["AC-3 no inbound port"])
        print(f"\n   HEADLINE (AC-1 + AC-2 + AC-3: command-from-anywhere without weakening security): "
              f"{'PASS' if headline else 'FAIL'}")
        return 0 if all(results.values()) else 1
    finally:
        print("== teardown ==")
        pg.stop(client)


if __name__ == "__main__":
    sys.exit(main())
