"""
The Scheduler — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_scheduler.py (AC-10 against the real Manager; the rest are pure logic).
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_deterministic_byte_identical():
    """AC-1: same catalog+readiness+capacity twice → byte-identical schedules."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_zero_llm_calls_during_scheduling():
    """AC-2: the Scheduler makes zero LLM/planning calls while scheduling (only the CTO does)."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_unmet_dependency_never_dispatches_early():
    """AC-3: a task with an unmet dependency never appears before its prerequisite."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_capacity_cap_queues_overflow():
    """AC-4: within a level, run up to capacity; the (cap+1)-th queues to the next wave."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_dry_run_provisions_nothing():
    """AC-5: dry-run yields a full plan + cost estimate and provisions nothing."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_budget_cap_halts_before_dispatch():
    """AC-6: a wave exceeding the budget cap is halted before any dispatch."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_same_order_different_capacity():
    """AC-7: identical task order at capacity=3 and capacity=10; only concurrency differs."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_rework_redispatch_without_rerunning_deps():
    """AC-8: a QA re-work re-dispatches the failed feature without re-running its done deps."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_genesis_first_no_build_until_plan_signed():
    """AC-9: no build task is schedulable before the plan is signed."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_restart_rebuilds_without_double_dispatch():
    """AC-10: restart rebuilds task state from Manager events; no double-dispatch. [real Manager]"""


@pytest.mark.skip(reason=DEFER)
def test_ac11_cyclic_catalog_rejected():
    """AC-11: a cyclic catalog is rejected at load with the cycle identified."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_replay_reproduces_schedule():
    """AC-12: a replayed recorded plan reproduces the exact schedule."""
