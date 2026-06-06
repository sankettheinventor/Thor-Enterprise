"""
The Development-Governance Engine — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_govengine.py against real git + real test execution + the real Manager.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_incomplete_not_done_m3_blocker():
    """AC-1: a genuinely incomplete feature (contracted file untouched) → not_done, M3 blocker."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_fabricated_claim_caught_by_divergence():
    """AC-2: a feature where the agent claims work it didn't do is caught by divergence; not done."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_hollow_fake_test_not_done():
    """AC-3: a passing-but-hollow test fails the fake-test-checker → not_done."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_ci_pass_diff_mismatch_escalate():
    """AC-4: CI passing but diff not matching contracted files → escalate (conflict), not done."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_verdict_read_only():
    """AC-5: running the verdict changes nothing in the codebase or state."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_deterministic_replay():
    """AC-6: the same reality snapshot produces the identical verdict on replay."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_stale_verdict_freshness():
    """AC-7: a stale verdict (branch changed since) does not count; a fresh run is required."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_inputs_unreadable_fail_closed():
    """AC-8: with git/CI/audit unreadable, the engine returns escalate/error, never done."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_canary_always_not_done():
    """AC-9: the canary (deliberately incomplete) always verdicts not_done."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_high_stakes_requires_signature():
    """AC-10: a high-stakes change with all probes passing still requires a human signature."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_verdict_recorded_event():
    """AC-11: every verdict + divergence result is recorded as a signed event."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_adversarial_no_false_done():
    """AC-12: an adversarial suite (fake tests, fabricated claims, gamed gates) cannot get a done."""
