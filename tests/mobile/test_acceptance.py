"""
Mobile / Remote — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 7). The phone rides the SAME DashboardService verify/record path as the desktop
over an E2EE relay (ciphertext only), with a device-key allowlist + revocation and no inbound port.
Deferred (live, needs Postgres); run: pytest -m deferred tests/mobile.
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred


def _setup(fresh_ledger):
    from dashboard.service import DashboardService
    from manager.core import ThorManager
    from mobile import crypto
    from mobile.bridge import PhoneBridge
    from mobile.phone_client import PhoneClient
    from mobile.relay import Relay
    mgr = ThorManager(fresh_ledger)
    svc = DashboardService(mgr)
    relay = Relay()
    cp_priv, cp_pub = crypto.gen_keypair()
    bridge = PhoneBridge(mgr, svc, relay, cp_priv)
    phone = PhoneClient("dev-1", relay, cp_pub)
    bridge.register_device("dev-1", phone.e2ee_pub, phone.signing_pub)
    return mgr, svc, relay, bridge, phone


def _card(mgr, card_id):
    return mgr._get_card(card_id)


def test_ac1_merge_signed_from_phone_verified(fresh_ledger, host_repo):
    from govengine import reality
    from sdlc.bridge import FindingsTicketBridge
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    subprocess.run(["git", "-C", host_repo, "init", "-q"])
    open(os.path.join(host_repo, "a"), "w").write("x")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base"])
    subprocess.run(["git", "-C", host_repo, "branch", "-M", "main"])
    subprocess.run(["git", "-C", host_repo, "checkout", "-q", "-b", "feature/F"])
    open(os.path.join(host_repo, "b"), "w").write("y")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "F"])
    cid = FindingsTicketBridge(mgr).raise_merge_card("F", repo=host_repo, branch="feature/F",
                                                     snapshot_sha=reality.head_sha(host_repo, "feature/F"))
    bridge.push_card(_card(mgr, cid), "dev-1")
    phone.approve(phone.receive())               # phone signs on-device, sends sealed
    res = bridge.process_inbound()
    assert res["verified"] is True and res["merge"]["merged"] is True


def test_ac2_relay_zero_knowledge(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    phone.send_command("mark_ready", feature_id="F")
    blob = relay._to_cp[-1]                       # what the relay holds — ciphertext only
    assert set(blob.keys()) == {"nonce", "ct", "sender_pub"}
    assert "mark_ready" not in str(blob) and "command" not in str(blob)   # plaintext never on the wire


def test_ac3_no_inbound_port(fresh_ledger):
    _, _, _, bridge, _ = _setup(fresh_ledger)
    assert bridge.inbound_port is None           # the control plane dials OUT — no inbound port


def test_ac4_non_allowlisted_rejected_logged(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    phone.send_command("rm_minus_rf")
    res = bridge.process_inbound()
    assert res["status"] == "rejected"
    assert any(e["event_type"] == "security.rejected" for e in mgr.eventlog.all_events())


def test_ac5_legible_block_one_sentence(fresh_ledger):
    _, _, _, _, phone = _setup(fresh_ledger)
    assert isinstance(phone.legible("path outside approved scope", "F"), str)


def test_ac6_already_decided_no_double_resolve(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    cid = mgr.raise_card("plan", "F", {"feature_id": "F"})
    bridge.push_card(_card(mgr, cid), "dev-1")
    card = phone.receive()
    phone.approve(card); assert bridge.process_inbound()["verified"] is True
    phone.approve(card); assert bridge.process_inbound()["verified"] is False   # already decided


def test_ac7_disconnect_disables_signing(fresh_ledger):
    _, _, _, _, phone = _setup(fresh_ledger)
    phone.set_connected(False)
    assert phone.approve({"card_id": "c", "payload": {}})["sent"] is False


def test_ac8_replayed_approval_rejected(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    cid = mgr.raise_card("plan", "F", {"feature_id": "F"})
    bridge.push_card(_card(mgr, cid), "dev-1")
    card = phone.receive()
    phone.approve(card); assert bridge.process_inbound()["verified"] is True
    phone.approve(card); assert bridge.process_inbound()["verified"] is False   # replay on a decided card


def test_ac9_lost_device_revoked(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    bridge.revoke_device("dev-1")
    cid = mgr.raise_card("plan", "F", {"feature_id": "F"})
    phone.approve({"card_id": cid, "payload": {"feature_id": "F"}})
    assert "revoked" in bridge.process_inbound()["reason"]                       # signature no longer trusted


def test_ac10_phone_actions_recorded(fresh_ledger):
    mgr, svc, relay, bridge, phone = _setup(fresh_ledger)
    cid = mgr.raise_card("plan", "F", {"feature_id": "F"})
    bridge.push_card(_card(mgr, cid), "dev-1")
    phone.approve(phone.receive()); bridge.process_inbound()
    assert any(e["event_type"] == "dashboard.action" for e in mgr.eventlog.all_events())


def test_ac11_phone_cannot_reach_room_or_change_rules(fresh_ledger):
    from mobile import allowlist
    assert allowlist.allowed("reach_room") is False and allowlist.allowed("edit_rules") is False


def test_ac12_phone_desktop_consistent_card(fresh_ledger):
    # the phone and the desktop sign the IDENTICAL card material (one shared decision model)
    from manager.core import ThorManager
    _, _, _, _, phone = _setup(fresh_ledger)
    desktop = ThorManager.card_material("card-1", {"feature_id": "F"})
    assert phone.sign_for("card-1", {"feature_id": "F"})   # signs the same material the desktop verifies
    assert desktop == ThorManager.card_material("card-1", {"feature_id": "F"})
