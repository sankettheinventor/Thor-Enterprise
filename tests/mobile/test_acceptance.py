"""
Mobile / Remote — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_mobile.py against the real Manager + DashboardService + the E2EE bridge.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_merge_signed_from_phone_verified():
    """AC-1: a merge approved on the phone produces a Manager-verified Ed25519 signature + merges."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_relay_zero_knowledge():
    """AC-2: a fully-compromised relay reads no card contents, no keys, and forges no signature."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_no_inbound_port():
    """AC-3: the control plane opens no inbound port for the phone capability."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_non_allowlisted_rejected_logged():
    """AC-4: a non-allowlisted command from the phone is rejected and logged."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_legible_block_one_sentence():
    """AC-5: a block shown on the phone includes a one-sentence plain-language reason."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_already_decided_no_double_resolve():
    """AC-6: a card resolved on desktop shows "already decided" on the phone."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_disconnect_disables_signing():
    """AC-7: on disconnect the phone disables signing; never presents cached data as live."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_replayed_approval_rejected():
    """AC-8: a captured/replayed approval is rejected (signature bound to card+payload+nonce)."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_lost_device_revoked():
    """AC-9: a lost device's signing identity can be revoked; its signatures are then rejected."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_phone_actions_recorded():
    """AC-10: every phone action is recorded as an event identically to desktop."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_phone_cannot_reach_room_or_change_rules():
    """AC-11: the phone cannot reach into a room or change rules (no such path exists)."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_phone_desktop_consistent_card():
    """AC-12: phone and desktop render the same card from the same Manager state consistently."""
