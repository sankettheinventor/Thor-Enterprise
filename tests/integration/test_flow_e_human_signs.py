"""
FLOW E (Integration PRD) — the human signs from the dashboard (HCD made real). Gaps M5/M6 + T7.

A genuine Ed25519 signature (a REGISTERED operator key + a one-time card nonce) → verified → the
gated action proceeds; a forged signature, a replayed nonce, or an unregistered key → rejected, card
stays open. A verified merge-card signature drives the REAL merge (T6) only if the verdict is fresh
(R9). Proves the same backend the cockpit Sign button calls. Deferred (live, needs Postgres).
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
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub, _b64


def _svc(fresh_ledger):
    from dashboard.service import DashboardService
    from manager.core import ThorManager
    return DashboardService(ThorManager(fresh_ledger))


def _sign(mgr, priv, _b64, card, nonce=None):
    material = mgr.card_material(card, mgr._get_card(card)["payload"], nonce)
    return _b64(priv.sign(material.encode()))


def test_flow_e_human_signs(fresh_ledger):
    """A registered operator key + the card's nonce → verified → card.approved."""
    svc = _svc(fresh_ledger); mgr = svc.manager
    priv, pub, _b64 = _operator()
    mgr.register_operator(pub)
    card = mgr.raise_card("plan", "FE", {"feature_id": "FE"})
    nonce = mgr.issue_challenge(card)
    r = svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)
    assert r["verified"] is True and mgr.is_card_approved(card) is True


def test_flow_e_forged_signature_rejected(fresh_ledger):
    svc = _svc(fresh_ledger); mgr = svc.manager
    priv, pub, _b64 = _operator(); mgr.register_operator(pub)
    card = mgr.raise_card("plan", "FE", {"feature_id": "FE"})
    nonce = mgr.issue_challenge(card)
    r = svc.approve(card, _b64(priv.sign(b"not the card material")), pub, nonce=nonce)
    assert r["verified"] is False and mgr.is_card_approved(card) is False   # card stays open


def test_flow_e_replayed_nonce_rejected(fresh_ledger):
    svc = _svc(fresh_ledger); mgr = svc.manager
    priv, pub, _b64 = _operator(); mgr.register_operator(pub)
    card = mgr.raise_card("plan", "FE", {"feature_id": "FE"})
    nonce = mgr.issue_challenge(card)
    assert svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)["verified"] is True
    # replay: the same (signature, nonce) again — the nonce is consumed AND the card is no longer open
    r = svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)
    assert r["verified"] is False
    # and a signature carrying a never-issued nonce is rejected outright
    card2 = mgr.raise_card("plan", "FE2", {"feature_id": "FE2"})
    mgr.issue_challenge(card2)
    bad = svc.approve(card2, _sign(mgr, priv, _b64, card2, "never-issued"), pub, nonce="never-issued")
    assert bad["verified"] is False and "challenge" in bad["reason"]


def test_flow_e_unregistered_key_rejected(fresh_ledger):
    svc = _svc(fresh_ledger); mgr = svc.manager
    priv_a, pub_a, _b64 = _operator(); mgr.register_operator(pub_a)   # only A is authorized
    priv_b, pub_b, _ = _operator()                                    # B is a stranger
    card = mgr.raise_card("plan", "FE", {"feature_id": "FE"})
    nonce = mgr.issue_challenge(card)
    r = svc.approve(card, _sign(mgr, priv_b, _b64, card, nonce), pub_b, nonce=nonce)
    assert r["verified"] is False and "unauthorized" in r["reason"]


def test_flow_e_merge_sign_drives_real_merge(fresh_ledger, host_repo):
    """A verified Signature 3 on a merge card → the real git merge runs (fresh verdict, R9)."""
    svc = _svc(fresh_ledger); mgr = svc.manager
    from govengine import reality
    from sdlc.bridge import FindingsTicketBridge

    # a real repo: main + a feature branch
    open(os.path.join(host_repo, "f.txt"), "w").write("base\n")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base"])
    subprocess.run(["git", "-C", host_repo, "branch", "-M", "main"])
    subprocess.run(["git", "-C", host_repo, "checkout", "-q", "-b", "feature/FM"])
    open(os.path.join(host_repo, "g.txt"), "w").write("feature\n")
    subprocess.run(["git", "-C", host_repo, "add", "-A"]); subprocess.run(
        ["git", "-C", host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "FM"])
    snap = reality.head_sha(host_repo, "feature/FM")

    priv, pub, _b64 = _operator(); mgr.register_operator(pub)
    card = FindingsTicketBridge(mgr).raise_merge_card("FM", repo=host_repo, branch="feature/FM", snapshot_sha=snap)
    nonce = mgr.issue_challenge(card)
    r = svc.approve(card, _sign(mgr, priv, _b64, card, nonce), pub, nonce=nonce)
    assert r["verified"] is True
    assert r["merge"]["merged"] is True                              # the REAL git merge ran
    assert any(e["event_type"] == "feature.merged" for e in mgr.eventlog.all_events())
