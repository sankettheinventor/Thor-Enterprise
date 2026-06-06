"""
The Foundation Adapters — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_adapters.py against the real hash-chain, real Ed25519, and real git.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_no_external_type_leaks():
    """AC-1: no AGT or Gitea type appears in THOR code outside its adapter (arch lint)."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_audit_chain_detects_tamper():
    """AC-2: every event signed + hash-chained; a forced edit to a past event is detected."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_compliance_evidence_traces_to_chain():
    """AC-3: compliance evidence for a framework is exported and traces to the chain."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_room_identity_verify_reject_forged():
    """AC-4: a room identity verifies; a forged/stale identity is rejected."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_three_signatures_verify_reject_replay():
    """AC-5: each of the three signature points verifies; a replayed/forged signature is rejected."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_real_merge_after_signature3():
    """AC-6: a real merge runs through the Gitea adapter only after a verified Signature 3."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_substitution_only_adapter_changes():
    """AC-7: swapping the Gitea adapter for an alternate leaves THOR's authority + modules unchanged."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_agt_version_bump_absorbed():
    """AC-8: an AGT version bump is absorbed by the adapter alone; THOR-vocabulary callers unchanged."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_audit_cant_record_fail_closed():
    """AC-9: when the audit substrate can't record, governed actions don't proceed."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_identity_cant_verify_fail_closed():
    """AC-10: when identity can't verify, the room/signature isn't trusted."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_credentials_never_in_room():
    """AC-11: external credentials are never present in a room."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_identity_no_agent_scoring():
    """AC-12: identity is used only for verification/system-trust; no per-agent trust score anywhere."""
