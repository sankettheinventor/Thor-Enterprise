"""
FLOW A tail (Integration PRD) — a `done` verdict → merge card → human Signature 3 → real git merge →
room destroyed. Gaps H9 + R9. Proves: no merge before a VERIFIED Signature 3; a forged signature
leaves the card open; a STALE verdict is refused (R9); the authorized path performs a real merge and
records feature.merged. Driven by a live verdict from the Coordinator. Deferred (live).
"""
import os
import subprocess

import pytest

pytestmark = pytest.mark.deferred

LOGIN = "def check(pw):\n    return len(pw) >= 8\n"
REAL_TEST = ("import sys; sys.path.insert(0,'src')\nfrom login import check\n"
             "assert check('abcdefgh') is True\nassert check('x') is False\nprint('ok')\n")
REGRESS = "print('ok')\n"


def _git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)


def _V(decision):
    return type("V", (), {"decision": decision, "reason": "x", "classification": "non_critical"})()


def _operator():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub, _b64


def _done(conn, repo, fid="FA"):
    """Build green trusted state and return (mgr, branch, result) with a `done` verdict."""
    from contract.seam import Seam
    from contract.slice_builder import build_slice
    from contract.transport import InProcessTransport
    from manager.core import ThorManager

    mgr = ThorManager(conn)
    open(os.path.join(repo, "README"), "w").write("base\n")
    _git(repo, "add", "-A"); _git(repo, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q", "-m", "base")
    _git(repo, "branch", "-M", "main")
    branch = f"feature/{fid}"
    _git(repo, "checkout", "-q", "-b", branch)
    files = {"src/login.py": LOGIN, "src/test_login.py": REAL_TEST, "src/test_regress.py": REGRESS}
    for rel, c in files.items():
        p = os.path.join(repo, rel); os.makedirs(os.path.dirname(p) or repo, exist_ok=True); open(p, "w").write(c)
    _git(repo, "add", "-A"); _git(repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", f"implement {fid}")

    room = mgr.provision_room(fid, branch=branch, worktree_host_path=repo, network_mode="sealed")
    feature = {"feature_id": fid, "task_type": "build", "acceptance_criteria": ["works"],
               "scope_files": ["src/login.py"], "planned_test": "src/test_login.py",
               "regression_file": "src/test_regress.py"}
    seam = Seam(InProcessTransport(), manager=mgr)
    seam.manager_send("assign_task", {"room_id": room["room_id"],
                                      "feature_slice": build_slice(feature, {"scope_files": ["src/login.py"]}).model_dump()})
    for f in files:
        mgr.record_decision(_V("allow"), {"room_id": room["room_id"], "type": "tool_call",
                                          "name": "write_file", "target": f})
    seam.room_send("claim_done", {"room_id": room["room_id"], "feature_id": fid, "message_id": "k1"})
    return mgr, branch, mgr.run_verdict(fid, branch, repo)


def _ctx(repo, branch, fid):
    from govengine.engine import VerdictContext
    return VerdictContext(fid, branch, repo, contract={})


def test_flow_a_done_to_signed_merge(fresh_ledger, host_repo):
    from govengine.engine import GovernanceEngine
    from manager.core import ThorManager
    from sdlc.merge_driver import MergeDriver

    mgr, branch, result = _done(fresh_ledger, host_repo, "FA")
    assert result["verdict"] == "done", result["blockers"]
    driver = MergeDriver(mgr, engine=GovernanceEngine(mgr))
    ctx = _ctx(host_repo, branch, "FA")

    card = driver.on_verdict(result)
    assert card, "a done verdict must raise a merge card"

    # 1) no merge before a verified Signature 3
    r0 = driver.merge_if_authorized(card, host_repo, branch, result, ctx)
    assert r0["merged"] is False and "Signature 3" in r0["reason"]

    # 2) a forged signature is rejected — the card stays open (valid nonce, wrong material → bad sig)
    priv, pub, _b64 = _operator()
    nonce = mgr.issue_challenge(card)                       # BUG-3: the nonce is now mandatory
    forged = mgr.approve(card, _b64(priv.sign(b"wrong material")), pub, nonce=nonce)
    assert forged["verified"] is False and mgr.is_card_approved(card) is False

    # 3) a valid Signature 3 → real merge → feature.merged + room destroyed
    material = ThorManager.card_material(card, mgr._get_card(card)["payload"], nonce)
    assert mgr.approve(card, _b64(priv.sign(material.encode())), pub, nonce=nonce)["verified"] is True
    r = driver.merge_if_authorized(card, host_repo, branch, result, ctx)
    assert r["merged"] is True, r
    assert any(e["event_type"] == "feature.merged" for e in mgr.eventlog.all_events())
    rooms = mgr.state_summary()["rooms"]
    assert rooms.get(result["room_id"], {}).get("status") in ("destroyed", None)


def test_flow_a_stale_verdict_refused(fresh_ledger, host_repo):
    """R9 — if the branch HEAD moves after the verdict, the merge is refused even with a valid Sig 3."""
    from govengine.engine import GovernanceEngine
    from manager.core import ThorManager
    from sdlc.merge_driver import MergeDriver

    mgr, branch, result = _done(fresh_ledger, host_repo, "FS")
    assert result["verdict"] == "done"
    driver = MergeDriver(mgr, engine=GovernanceEngine(mgr))
    card = driver.on_verdict(result)
    priv, pub, _b64 = _operator()
    nonce = mgr.issue_challenge(card)                       # BUG-3: the nonce is now mandatory
    material = ThorManager.card_material(card, mgr._get_card(card)["payload"], nonce)
    mgr.approve(card, _b64(priv.sign(material.encode())), pub, nonce=nonce)   # valid Signature 3

    open(os.path.join(host_repo, "src/login.py"), "a").write("# moved\n")  # branch HEAD moves
    _git(host_repo, "add", "-A"); _git(host_repo, "-c", "user.email=c@t", "-c", "user.name=c", "commit", "-q", "-m", "move")

    r = driver.merge_if_authorized(card, host_repo, branch, result, _ctx(host_repo, branch, "FS"))
    assert r["merged"] is False and "stale" in r["reason"]
    try:
        mgr.destroy_room(result["room_id"])
    except Exception:  # noqa: BLE001
        pass
