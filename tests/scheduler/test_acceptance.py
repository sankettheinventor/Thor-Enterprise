"""
The Scheduler — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 4). The Scheduler is pure deterministic logic (zero LLM); AC-1..AC-9/11/12 prove
in-process. AC-10 (restart without double-dispatch) verifies against a REAL Postgres-backed Manager
+ a real sealed room. Deferred (live); run: pytest -m deferred tests/scheduler.
"""
import pytest

from scheduler import cto_stub
from scheduler.core import Scheduler
from scheduler.graph import GraphError, Task

pytestmark = pytest.mark.deferred


def _tasks(spec):
    """spec: list of (fid, depends_on, task_type, est, ready)."""
    return [Task(feature_id=f, depends_on=tuple(d), task_type=tt, est_tokens=e, ready=r)
            for (f, d, tt, e, r) in spec]


def test_ac1_deterministic_byte_identical():
    spec = [("A", (), "build", 1000, True), ("B", ("A",), "build", 1000, True),
            ("C", (), "build", 1000, True)]
    a = Scheduler(_tasks(spec), capacity=2).plan().to_json()
    b = Scheduler(_tasks(spec), capacity=2).plan().to_json()
    assert a == b


def test_ac2_zero_llm_calls_during_scheduling():
    cto_stub.reset_counter()
    s = Scheduler(_tasks([("A", (), "build", 1000, True), ("B", (), "build", 1000, True)]), capacity=1)
    s.plan(); s.dry_run(); s.cost_estimate()
    assert cto_stub.PLAN_CALLS == 0   # scheduling triggers no planning call (only the CTO plans)


def test_ac3_unmet_dependency_never_dispatches_early():
    waves = Scheduler(_tasks([("A", (), "build", 1, True), ("B", ("A",), "build", 1, True)]),
                      capacity=5).plan().waves
    flat = [f for w in waves for f in w]
    assert flat.index("A") < flat.index("B")


def test_ac4_capacity_cap_queues_overflow():
    waves = Scheduler(_tasks([("A", (), "build", 1, True), ("B", (), "build", 1, True),
                              ("C", (), "build", 1, True)]), capacity=2).plan().waves
    assert len(waves[0]) == 2 and waves[1] == ["C"]


def test_ac5_dry_run_provisions_nothing():
    dr = Scheduler(_tasks([("A", (), "build", 1000, True)]), capacity=1).dry_run()
    assert dr["provisioned"] == 0 and dr["cost_estimate"] > 0


def test_ac6_budget_cap_halts_before_dispatch():
    calls = []
    res = Scheduler(_tasks([("A", (), "build", 5000, True), ("B", (), "build", 5000, True)]),
                    capacity=2, budget_cap=3000).run(lambda f, tt: calls.append(f))
    assert res["status"] == "halted_budget" and not calls


def test_ac7_same_order_different_capacity():
    spec = [("A", (), "build", 1, True), ("B", (), "build", 1, True), ("C", (), "build", 1, True)]
    assert Scheduler(_tasks(spec), capacity=3).plan().flatten() == \
        Scheduler(_tasks(spec), capacity=10).plan().flatten()


def test_ac8_rework_redispatch_without_rerunning_deps():
    s = Scheduler(_tasks([("A", (), "build", 1, True), ("B", ("A",), "build", 1, True)]), capacity=5)
    s.mark_done("A")
    s.mark_rework("B")
    waves = s.plan().waves
    assert "B" in [f for w in waves for f in w] and "A" not in [f for w in waves for f in w]


def test_ac9_genesis_first_no_build_until_plan_signed():
    s = Scheduler(_tasks([("A", (), "build", 1, True)]), capacity=2, plan_approved=False)
    assert s.plan().waves == []   # no build is schedulable before the plan is signed


def test_ac10_restart_rebuilds_without_double_dispatch(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    room = mgr.provision_room("A", task_type="build", network_mode="sealed")  # A is now 'working'
    try:
        s = Scheduler(_tasks([("A", (), "build", 1, True), ("B", (), "build", 1, True)]), capacity=5)
        s.rebuild_from_manager(mgr)                      # FR-17: learn A is already running
        flat = s.plan().flatten()
        assert "A" not in flat and "B" in flat          # A is not re-dispatched
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_ac11_cyclic_catalog_rejected():
    with pytest.raises(GraphError, match="cycle"):
        Scheduler(_tasks([("A", ("B",), "build", 1, True), ("B", ("A",), "build", 1, True)]), capacity=2)


def test_ac12_replay_reproduces_schedule():
    spec = [("A", (), "build", 1, True), ("B", ("A",), "build", 1, True), ("C", (), "build", 1, True)]
    recorded = Scheduler(_tasks(spec), capacity=2).plan().to_json()
    assert Scheduler(_tasks(spec), capacity=2).plan().to_json() == recorded
