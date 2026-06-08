"""
Seam S2 (Integration PRD) — Scheduler → CTO → Manager dispatch + the PM admission gate (M2/M3).

Proves the live wire against reality: a deterministic ready-wave dispatches through the real
dispatcher (CTO plan → Manager provision), creating real sealed rooms; and a no-spec feature is
REFUSED by PM before any room is provisioned. Deferred (live).
"""
import pytest

pytestmark = pytest.mark.deferred


def _mgr(fresh_ledger):
    from manager.core import ThorManager
    return ThorManager(fresh_ledger)


def test_seam_S2_deterministic_dispatch_provisions_rooms(fresh_ledger):
    from scheduler.core import Scheduler
    from scheduler.dispatch import make_dispatcher
    from scheduler.graph import Task

    mgr = _mgr(fresh_ledger)
    catalog = {
        "F1": {"feature_id": "F1", "acceptance_criteria": ["a"], "scope_files": ["src/"]},
        "F2": {"feature_id": "F2", "acceptance_criteria": ["a"], "scope_files": ["src/"]},
    }
    # deterministic plan (same catalog → byte-identical waves)
    assert Scheduler([Task("F1"), Task("F2")], capacity=5).plan().to_json() == \
        Scheduler([Task("F1"), Task("F2")], capacity=5).plan().to_json()

    sched = Scheduler([Task("F1"), Task("F2")], capacity=5)
    dispatch = make_dispatcher(mgr, catalog)
    res = sched.run(dispatch)
    try:
        assert res["status"] == "dispatched" and set(res["dispatched"]) == {"F1", "F2"}
        assert all(d["dispatched"] for d in dispatch.log)
        rooms = mgr.state_summary()["rooms"]                     # real rooms exist for both
        assert len([r for r in rooms.values() if r["feature_id"] in ("F1", "F2")]) == 2
    finally:
        for d in dispatch.log:
            if d.get("room_id"):
                mgr.destroy_room(d["room_id"], d["_room"].get("_mount_plan"))


def test_seam_S2_pm_refuses_no_spec_feature(fresh_ledger):
    from scheduler.dispatch import make_dispatcher

    mgr = _mgr(fresh_ledger)
    catalog = {"FNOSPEC": {"feature_id": "FNOSPEC"}}   # no acceptance criteria, no scope
    dispatch = make_dispatcher(mgr, catalog)
    rec = dispatch("FNOSPEC", "build")
    assert rec["refused"] is True and rec["dispatched"] is False
    assert "no acceptance criteria" in rec["reason"] or "no declared scope" in rec["reason"]
    assert mgr.state_summary()["rooms"] == {}, "PM must refuse a no-spec feature — no room provisioned"
