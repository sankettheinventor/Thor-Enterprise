"""
The PM Surface — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_pmsurface.py against the real Manager (Postgres) + Scheduler + Checker.
AC-12 (desktop+mobile consistency) is demonstrated as idempotent shared-model card resolution; the
real Mobile head is Module 16.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_kanban_live_state_and_ready_picked_up():
    """AC-1: kanban reflects live Manager feature states; mark-ready → Scheduler picks it up."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_merge_card_verified_signature_drives_merge():
    """AC-2: approving a merge card with a verified Ed25519 signature drives the merge; forged rejected."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_legible_refusal_plain_language():
    """AC-3: a governance block is shown in plain language (not a raw code/trace)."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_room_logs_read_only_no_mutate():
    """AC-4: room logs are read-only; no control to modify a room exists."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_holds_no_authoritative_state():
    """AC-5: the PM Surface holds no authoritative state; reopen → all state from the Manager."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_disconnected_disables_signing_no_stale():
    """AC-6: Manager unreachable → "disconnected", signing disabled, never stale-as-live."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_cost_caps_alert_dryrun():
    """AC-7: per-feature/total cost + caps shown; near-cap alert; dry-run shows cost with zero provisioning."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_three_signature_cards_no_autoresolve():
    """AC-8: all three signature points appear as cards requiring a verified signature; none auto-resolves."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_audit_feed_and_export():
    """AC-9: the audit feed shows every event and exports to CSV/JSON."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_checker_findings_view_matches_db():
    """AC-10: Project Checker findings render and match what the Checker wrote to the DB."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_operator_actions_recorded():
    """AC-11: every operator action (sign, reject, mark-ready, add-feature) is recorded as an event."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_desktop_mobile_consistent_one_decision():
    """AC-12: desktop and mobile show the same card and resolve it consistently (one decision)."""
