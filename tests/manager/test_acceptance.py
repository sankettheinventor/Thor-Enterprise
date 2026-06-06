"""
The THOR Manager — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside the build, skipped by default, gated LATER.
Phase-now coverage (demonstrated by tools/smoke_manager.py): AC-1/2/3/4/5/7/8/9/10/11/12.
AC-6 (claim_done → QA → verdict) needs the GovernanceEngine (Module 6) and stays deferred.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_only_manager_writes_eventlog():
    """AC-1: only the Manager appends to the EventLog; other components record THROUGH it."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_signed_chain_tamper_evident():
    """AC-2: valid signature + correct prev_hash→hash chain; altering a past event breaks verify."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_replay_rebuilds_exact_state():
    """AC-3: kill + restart rebuilds the exact registry/cards/feature-states from the log."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_signature_gates_provision_and_merge():
    """AC-4: no build room until the plan is signed; no merge without a verified merge-signature."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_forged_signature_rejected_card_stays_open():
    """AC-5: a forged/wrong-card signature is rejected and the card stays open."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_claim_done_drives_qa_then_verdict():
    """AC-6: on claim_done, QA then verdict; never merged on the agent's claim. [needs M6]"""


@pytest.mark.skip(reason=DEFER)
def test_ac7_eventlog_unwritable_fail_closed():
    """AC-7: with the EventLog unwritable, the Manager refuses new governed actions."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_bad_identity_token_refused():
    """AC-8: a room with a bad identity token is refused routing."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_second_provision_same_branch_refused():
    """AC-9: a second provision on an already-owned branch is refused."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_sentinel_reads_true_health():
    """AC-10: the Sentinel can read the Manager's true health, incl. eventlog-writable status."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_escalated_card_never_auto_resolved():
    """AC-11: an escalated card is never auto-resolved; it stays held with no human action."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_duplicate_appends_idempotent():
    """AC-12: duplicate event appends (retries) are idempotent; the chain has no duplicates."""
