"""
The Sentinel — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_sentinel.py against the real Manager + real Leash/Engine canaries + Docker.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_dead_leash_detected_fail_closed():
    """AC-1: a killed/hung leash is detected as unresponsive and the affected scope fail-closes."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_passing_canary_alarms_and_halts():
    """AC-2: a canary forced to pass (broken detector) triggers an alarm + halt of that scope."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_hung_component_detected_unhealthy():
    """AC-3: a hung-but-running component (alive, not responsive) is detected as unhealthy."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_rule_tamper_crawler_alarm_halt():
    """AC-4: tampering a governance rule (hash mismatch) triggers CRAWLER_ALARM + halt."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_unloaded_skill_fail_closes():
    """AC-5: a stage whose declared skill failed to load is caught and fail-closes."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_failed_boot_self_test_blocks_startup():
    """AC-6: a failed boot self-test prevents THOR from accepting work."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_sentinel_death_caught_by_silent_heartbeat():
    """AC-7: the Sentinel's own simulated death is detected via the silent-heartbeat base case."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_proportionate_halt_scope():
    """AC-8: a local fault halts only the room; a systemic fault halts broadly."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_self_audit_urgent_sentinel_decides():
    """AC-9: a Self-Audit URGENT is evaluated by the Sentinel (halt or note); the model never halts directly."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_shadow_discovered_orphan_reaped():
    """AC-10: a shadow (unregistered) container is discovered + alarmed; an orphan is reaped."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_maintenance_mode_scoped_and_bounded():
    """AC-11: maintenance silences only the specified alarms for a bounded window, auto-closes."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_chaos_test_pages_each_failure_class():
    """AC-12: a chaos test confirms the Sentinel pages correctly for each failure class."""
