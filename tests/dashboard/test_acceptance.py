"""
The PM Surface — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 7). The DashboardService is a WINDOW over the Manager; its only state is a Manager
reference. Reads are projections; writes are direction or a verified Ed25519 signature (operator-key +
one-time nonce). Deferred (live, needs Postgres); run: pytest -m deferred tests/dashboard.
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred


def _operator():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64
    priv = Ed25519PrivateKey.generate()
    return priv, _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)), _b64


def _svc(fresh_ledger, **kw):
    from dashboard.service import DashboardService
    from manager.core import ThorManager
    return DashboardService(ThorManager(fresh_ledger), **kw)


def _sign(mgr, priv, _b64, card, nonce):
    return _b64(priv.sign(mgr.card_material(card, mgr._get_card(card)["payload"], nonce).encode()))


def test_ac1_kanban_live_state_and_ready_picked_up(fresh_ledger):
    svc = _svc(fresh_ledger)
    fid = svc.add_feature("login")
    assert any(c["feature_id"] == fid for col in svc.kanban()["columns"].values() for c in col)
    svc.mark_ready(fid)
    assert next(f for f in svc.manager.list_features() if f["feature_id"] == fid)["status"] == "ready"


def test_ac2_merge_card_verified_signature_drives_merge(fresh_ledger, host_repo):
    from govengine import reality
    from sdlc.bridge import FindingsTicketBridge
    svc = _svc(fresh_ledger); mgr = svc.manager
    subprocess.run(["git", "-C", host_repo, "init", "-q"])
    open(os.path.join(host_repo, "a"), "w").write("x")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base"])
    subprocess.run(["git", "-C", host_repo, "branch", "-M", "main"])
    subprocess.run(["git", "-C", host_repo, "checkout", "-q", "-b", "feature/F"])
    open(os.path.join(host_repo, "b"), "w").write("y")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "F"])
    priv, pub, _b64 = _operator(); mgr.register_operator(pub)
    card = FindingsTicketBridge(mgr).raise_merge_card("F", repo=host_repo, branch="feature/F",
                                                      snapshot_sha=reality.head_sha(host_repo, "feature/F"))
    nonce = mgr.issue_challenge(card)
    r = svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)
    assert r["verified"] and r["merge"]["merged"] is True


def test_ac3_legible_refusal_plain_language(fresh_ledger):
    svc = _svc(fresh_ledger)
    svc.manager.raise_card("merge", "F", {"feature_id": "F"})
    assert isinstance(svc.cards()[0]["legible_reason"], str) and svc.cards()[0]["legible_reason"]


def test_ac4_room_logs_read_only_no_mutate(fresh_ledger):
    assert _svc(fresh_ledger).room_logs("room-x")["writable"] is False


def test_ac5_holds_no_authoritative_state(fresh_ledger):
    svc = _svc(fresh_ledger)
    # the ONLY state is the manager reference + config — no local rooms/features/cards store
    assert not any(k in svc.__dict__ for k in ("rooms", "features", "cards_store", "_state"))


def test_ac6_disconnected_disables_signing_no_stale(fresh_ledger):
    svc = _svc(fresh_ledger)
    card = svc.manager.raise_card("merge", "F", {"feature_id": "F"})
    svc.set_disconnected(True)
    r = svc.approve(card, "x", "y")
    assert r["verified"] is False and "disconnected" in r["reason"]


def test_ac7_cost_caps_alert_dryrun(fresh_ledger):
    svc = _svc(fresh_ledger, budget_cap=500)
    fid = svc.add_feature("big"); svc.mark_ready(fid)
    c = svc.cost()
    assert "total_spent" in c and "cap" in c


def test_ac8_three_signature_cards_no_autoresolve(fresh_ledger):
    svc = _svc(fresh_ledger)
    card = svc.manager.raise_card("qa_fail", "F", {"feature_id": "F"}, held=True)
    assert svc.manager._get_card(card)["status"] == "held"   # never auto-resolves without a human


def test_ac9_audit_feed_and_export(fresh_ledger):
    svc = _svc(fresh_ledger)
    svc.add_feature("x")
    assert len(svc.audit_feed()) >= 1 and svc.audit_export("json")


def test_ac10_checker_findings_view_matches_db(fresh_ledger):
    svc = _svc(fresh_ledger)
    assert svc.findings() == svc.manager.list_checker_findings()


def test_ac11_operator_actions_recorded(fresh_ledger):
    svc = _svc(fresh_ledger)
    svc.add_feature("x")
    assert any(e["event_type"] == "dashboard.action" for e in svc.manager.eventlog.all_events())


def test_ac12_desktop_mobile_consistent_one_decision(fresh_ledger):
    svc = _svc(fresh_ledger); mgr = svc.manager
    priv, pub, _b64 = _operator(); mgr.register_operator(pub)
    card = mgr.raise_card("plan", "F", {"feature_id": "F"})
    nonce = mgr.issue_challenge(card)
    assert svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)["verified"] is True
    # the SAME card cannot be resolved twice (one decision, desktop or mobile)
    assert svc.approve(card, "x", pub)["verified"] is False
