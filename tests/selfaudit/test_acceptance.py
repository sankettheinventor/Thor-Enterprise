"""
The Self-Audit Model — Acceptance Criteria AC-1..AC-12 (PRD §15).

DEFERRED PROVING (P7 / Rule 2): written alongside, skipped by default, gated LATER. All 12 are
demonstrated by tools/smoke_selfaudit.py against a real read-only Postgres role + the real Sentinel.
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_zero_token_cost():
    """AC-1: runs continuously and incurs zero token cost (no frontier-model API calls)."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_writes_reports_and_metatrust():
    """AC-2: writes correctness reports + a meta-trust score to the DB."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_read_only_write_denied():
    """AC-3: read-only — a write to the EventLog is denied (DB permissions block it)."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_severe_anomaly_escalated_no_halt():
    """AC-4: a seeded severe anomaly is escalated URGENT to the Sentinel; the model never halts."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_system_runs_without_selfaudit():
    """AC-5: the system functions with the Self-Audit down; its absence is alarmed."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_metatrust_is_system_not_agent():
    """AC-6: the meta-trust score reflects system reliability, not per-agent scoring."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_false_positive_no_wrongful_halt():
    """AC-7: a false-positive escalation results in at most a Sentinel evaluation, never a halt."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_retro_benchmark_zero_frontier():
    """AC-8: retrospectives + benchmarks run over existing data without frontier-model calls."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_sentinel_probes_selfaudit_liveness():
    """AC-9: the Sentinel probes the Self-Audit model's liveness (it is itself watched)."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_findings_persist_in_db():
    """AC-10: findings live in the DB, not agent memory (persistent across restarts)."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_inspection_respects_resource_bounds():
    """AC-11: inspection respects resource bounds and never starves rooms of compute."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_toras_ready_seam():
    """AC-12: the inspection interface has a clean observe→assess→emit seam for Toras v2."""
