"""
The Leash — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside the build, skipped by default, run as a gate
LATER. Nothing here fabricates a pass (Rule 11): an unimplemented check stays skipped.

Phase 2a (built now) targets AC-1, AC-2, AC-3, AC-4, AC-11 (+ partial AC-7 escalate-hold);
those are demonstrated by tools/smoke_leash.py. AC-5/6/8/9/10/12 need Phase 2b (egress lock,
credentials, cook-adapter, kill-switch, load test, AGT upgrade test).
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_out_of_scope_denied_before_write():
    """AC-1: a tool call to an out-of-scope path is denied BEFORE the write happens (file never modified)."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_denial_reaches_cook_with_reason():
    """AC-2: the denial reaches the cook with a structured reason."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_every_decision_signed_event():
    """AC-3: every allow/deny/escalate is a signed event in the EventLog (verified by reading the log)."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_adapter_down_denies_all():
    """AC-4: with the AGT adapter down, all actions are denied (fail-closed)."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_raw_http_bypass_blocked():
    """AC-5: a raw-HTTP bypass (not via structured tools) is blocked by Layer B. [Phase 2b]"""


@pytest.mark.skip(reason=DEFER)
def test_ac6_no_credentials_inside_container():
    """AC-6: credentials never appear inside the container; approved outbound still succeeds. [Phase 2b]"""


@pytest.mark.skip(reason=DEFER)
def test_ac7_dependency_add_escalates_and_holds():
    """AC-7: a dependency-add escalates to a CEO card and is held until decided."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_second_cook_governed_same_leash():
    """AC-8: a different cook (not Claude Code) is governed by the same Leash via its Cook-adapter. [Phase 2b]"""


@pytest.mark.skip(reason=DEFER)
def test_ac9_malicious_tool_triggers_killswitch():
    """AC-9: a malicious tool definition triggers the kill-switch; the room is terminated. [Phase 2b]"""


@pytest.mark.skip(reason=DEFER)
def test_ac10_no_unaudited_allows_under_load():
    """AC-10: under load, no action is allowed without a recorded decision (decisions == actions). [Phase 2b]"""


@pytest.mark.skip(reason=DEFER)
def test_ac11_policy_immutable_from_inside_room():
    """AC-11: the per-room policy cannot be modified from inside the room (frozen)."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_agt_version_bump_only_touches_adapter():
    """AC-12: an AGT version bump doesn't break THOR — only the adapter's tests touch AGT. [Phase 2b/M12]"""
