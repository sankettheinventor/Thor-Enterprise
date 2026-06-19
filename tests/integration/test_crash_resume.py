"""
Crash-resume (AC-8) — a build interrupted by a control-plane crash is re-queued on the next boot, and its
orphaned room is freed, so work continues from a clean point. The verdict still judges from reality on the
re-dispatch, so recovery can never resurrect a false `done`.

Deferred (live): needs the real ledger (Postgres projections).
"""
import pytest

pytestmark = pytest.mark.deferred


def _mgr(fresh_ledger):
    from manager.core import ThorManager
    return ThorManager(fresh_ledger)


def test_inflight_build_is_requeued_and_room_freed(fresh_ledger):
    mgr = _mgr(fresh_ledger)
    mgr.add_feature("FCR1", "interrupted build")
    mgr.set_feature_status("FCR1", "building")
    # a room was 'working' on this branch when the crash hit (record the projection directly — no docker)
    mgr._record("room.provisioned",
                {"room_id": "room-crash1", "container": "c", "task_type": "build", "feature_id": "FCR1",
                 "branch": "feature/FCR1", "status": "working"}, room_id="room-crash1", feature_id="FCR1")

    out = mgr.recover_in_flight()

    assert out["recovered"] == [{"feature_id": "FCR1", "from": "building"}]
    status = next(f for f in mgr.list_features() if f["feature_id"] == "FCR1")["status"]
    assert status == "ready", "the interrupted build must be re-queued for re-dispatch"
    # the branch is free again (one-branch-one-room): a fresh room can be provisioned for it
    assert mgr._working_room_ids("FCR1") == [], "the orphaned working room must be freed"
    # the recovery is on the audit trail
    types = [e["event_type"] for e in mgr.eventlog.all_events() if e.get("feature_id") == "FCR1"]
    assert "feature.recovered" in types


def test_done_and_awaiting_signature_are_not_touched(fresh_ledger):
    mgr = _mgr(fresh_ledger)
    mgr.add_feature("FCR2", "finished")
    mgr.set_feature_status("FCR2", "awaiting_signature")
    mgr.add_feature("FCR3", "shipped")
    mgr.set_feature_status("FCR3", "done")

    out = mgr.recover_in_flight()

    assert out["recovered"] == [], "recovery must not disturb completed / human-pending work"
    by = {f["feature_id"]: f["status"] for f in mgr.list_features()}
    assert by["FCR2"] == "awaiting_signature" and by["FCR3"] == "done"


def test_recovery_is_idempotent(fresh_ledger):
    mgr = _mgr(fresh_ledger)
    mgr.add_feature("FCR4", "x")
    mgr.set_feature_status("FCR4", "in_qa")
    assert mgr.recover_in_flight()["recovered"] == [{"feature_id": "FCR4", "from": "in_qa"}]
    # second boot: already 'ready' → nothing to recover
    assert mgr.recover_in_flight()["recovered"] == []
