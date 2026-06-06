"""
The Task Handoff Contract — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_contract.py (AC-2/3/5(docker)/11 against a real room + Manager).
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_only_six_messages_accepted():
    """AC-1: only the six defined messages are accepted; a seventh/undefined is rejected."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_slice_one_feature_no_catalog():
    """AC-2: the delivered slice contains exactly one feature — no other feature, no catalog."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_slice_readonly_write_fails():
    """AC-3: writing to /task/feature.json from inside the room fails (read-only)."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_no_self_certify_path():
    """AC-4: no message/field lets a room mark itself done; only Manager's result_decision is done."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_same_suite_both_transports():
    """AC-5: the identical six-message suite passes over docker-exec and in-process/REST."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_malformed_rejected():
    """AC-6: a malformed message is rejected and logged, not best-effort interpreted."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_amend_authority():
    """AC-7: an agent-originated amend is rejected; a human-authority amend is applied."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_duplicate_claim_one_verdict():
    """AC-8: a duplicate claim_done produces exactly one verdict (idempotency)."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_version_mismatch_clean_fail():
    """AC-9: a version mismatch at provision fails cleanly (room not trusted)."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_no_credentials_or_other_room_data():
    """AC-10: no message carries credentials or another room's data (schema + audit)."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_every_message_recorded_event():
    """AC-11: every seam message is recorded as an event by the Manager."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_transport_swap_no_logic_change():
    """AC-12: switching the Transport Adapter requires no change to Manager/room logic or shape."""
