"""
FLOW D (Integration PRD) — a governor dies → fail-closed halt. Gaps C3 + R6.

The Sentinel doesn't just detect — it ENFORCES: a confirmed critical failure physically destroys the
affected rooms and blocks new work; a broken detector (a passing canary) triggers a real halt; a
transient flap does NOT thrash a halt; a local fault halts only its room. Verified against reality
(real rooms killed via Docker, the Manager refusing new provisions). Deferred (live).
"""
import pytest

pytestmark = pytest.mark.deferred


def _mgr_sentinel(fresh_ledger):
    from manager.core import ThorManager
    from sentinel.core import Sentinel
    mgr = ThorManager(fresh_ledger)
    sentinel = Sentinel(mgr)
    mgr.attach_sentinel(sentinel)
    return mgr, sentinel


def test_flow_D_governor_dies_halts(fresh_ledger, host_repo):
    """A dead critical governor → the room is physically destroyed + new work is blocked."""
    mgr, sentinel = _mgr_sentinel(fresh_ledger)
    room = mgr.provision_room("FD", branch="feature/FD", worktree_host_path=host_repo, network_mode="sealed")
    # the leash governor is dead: alive but never responsive (a systemic, critical component)
    sentinel.register("leash", critical=True, health_fn=lambda: {"alive": True, "responsive": False})
    sentinel.probe_all()

    assert sentinel.halted is True
    assert mgr.state_summary()["rooms"][room["room_id"]]["status"] == "destroyed"   # room physically killed
    with pytest.raises(RuntimeError, match="HALTED"):                                # new work blocked
        mgr.provision_room("FD2", branch="feature/FD2")


def test_flow_D_flap_does_not_thrash_halt(fresh_ledger):
    """R6 — a transient blip (unhealthy then healthy on the re-probe) must NOT trigger a halt."""
    mgr, sentinel = _mgr_sentinel(fresh_ledger)
    n = {"i": 0}

    def flapping():
        n["i"] += 1
        return {"alive": True, "responsive": n["i"] % 2 == 0}   # 1st probe bad, re-probe good

    sentinel.register("manager", critical=True, health_fn=flapping)
    sentinel.probe_all()
    assert sentinel.halted is False and sentinel.halts == []     # recovered on re-probe → no halt


def test_flow_D_proportionate_local_halt(fresh_ledger, host_repo):
    """AC-8 — a local (room) fault halts only that room; other work keeps running, no global block."""
    mgr, sentinel = _mgr_sentinel(fresh_ledger)
    a = mgr.provision_room("FA", branch="feature/FA", worktree_host_path=host_repo, network_mode="sealed")
    b = mgr.provision_room("FB", branch="feature/FB", network_mode="sealed")
    try:
        sentinel.halt("room:" + a["room_id"], "local fault")
        rooms = mgr.state_summary()["rooms"]
        assert rooms[a["room_id"]]["status"] == "destroyed"     # only A killed
        assert rooms[b["room_id"]]["status"] == "working"       # B untouched
        assert sentinel.halted is False                         # a local halt does NOT block all work
    finally:
        mgr.destroy_room(b["room_id"])


def test_flow_D_broken_canary_halts(fresh_ledger):
    """AC-2 — a canary that PASSES means the detector is blind → alarm + real halt."""
    from leash.policy import FrozenPolicy
    from sentinel import canary
    mgr, sentinel = _mgr_sentinel(fresh_ledger)
    # a BROKEN policy: scope matches everything → the planted out-of-scope write is wrongly ALLOWED
    broken = FrozenPolicy(room_id="canary", scope_files=("**",), forbidden_patterns=(), frozen_at=0.0)
    c = canary.leash_canary(broken)
    assert c["healthy"] is False                                # the detector let the planted write through
    rep = sentinel.evaluate_canaries([c])
    assert rep["all_healthy"] is False and sentinel.halted is True
