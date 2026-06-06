"""
The SDLC Stages — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated end-to-end by tools/smoke_sdlc.py against the real Manager + Engine + Wall.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_order_enforced_no_skip_qa():
    """AC-1: a feature flows through stages in order; reaching the verdict without QA is refused."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_qa_independent_of_build():
    """AC-2: the QA agent is a fresh, different instance from the Build agent for the same feature."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_qa_writes_new_test_catches_edge_case():
    """AC-3: QA reads the actual code and produces a NEW test catching an implementation edge case."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_qa_findings_in_db_not_memory():
    """AC-4: QA findings appear as structured bugs in the DB, not agent memory."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_no_build_before_plan_signed():
    """AC-5: no Build stage runs before the plan is signed (Signature 1)."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_qa_fail_loops_only_after_signature2():
    """AC-6: a QA failure does not loop back to Build until the operator authorizes a ticket (Sig 2)."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_checker_readonly_yet_findings():
    """AC-7: the Project Checker changes nothing yet produces findings to the DB."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_floor_skills_always_present():
    """AC-8: floor skills are present in every Build and QA stage regardless of task_type."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_new_stage_added_without_regression():
    """AC-9: a new stage type can be added (anatomy + skills + edges) without modifying existing stages."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_capability_gap_raises_card():
    """AC-10: a mid-build capability gap raises a CEO card rather than a silent skill add."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_build_qa_loop_bounded():
    """AC-11: the Build↔QA loop is bounded; after N failed cycles the feature surfaces to the operator."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_three_signatures_enforced():
    """AC-12: all three signature points are enforced at their edges (plan, ticket, merge)."""
