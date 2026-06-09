"""
The Self-Audit Model — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 9). The read-only correctness eyes run on a REAL Postgres read-only role (writes
outside its own tables are physically denied), make ZERO frontier calls (the local model — a real
Ollama/Qwen if present, else the deterministic v1 — runs locally), and only ESCALATE to the Sentinel;
the model never halts. Deferred (live, needs Postgres); run: pytest -m deferred tests/selfaudit.
"""
import pytest

pytestmark = pytest.mark.deferred


def _setup(fresh_ledger, model=None, max_events=5000):
    from manager.core import ThorManager
    from selfaudit import db as sa_db
    from selfaudit.core import SelfAudit
    from sentinel.core import Sentinel
    mgr = ThorManager(fresh_ledger)
    sa_db.setup(mgr.conn)                                  # create the RO role + own tables + grants
    with mgr.conn.cursor() as cur:
        cur.execute("TRUNCATE selfaudit_reports, meta_trust")
    sentinel = Sentinel(mgr)
    mgr.attach_sentinel(sentinel)
    sa = SelfAudit(sa_db.connect_readonly(), sentinel=sentinel, model=model, max_events=max_events)
    return mgr, sentinel, sa


def _seed_divergence(mgr, n=2):
    for i in range(n):
        mgr._record("verdict.computed", {"verdict": "done", "feature_id": f"F{i}"}, feature_id=f"F{i}")
        mgr._record("divergence.detected", {"feature_id": f"F{i}", "signals": ["lie"]}, feature_id=f"F{i}")


def test_ac1_zero_token_cost(fresh_ledger):
    _, _, sa = _setup(fresh_ledger)
    sa.inspect()
    assert sa.model.frontier_calls == 0


def test_ac2_writes_reports_and_metatrust(fresh_ledger):
    _, _, sa = _setup(fresh_ledger)
    sa.inspect()
    assert sa.reports() and sa.meta_trust() is not None


def test_ac3_read_only_write_denied(fresh_ledger):
    import psycopg
    _, _, sa = _setup(fresh_ledger)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):    # Postgres physically denies the write
        with sa.conn.cursor() as cur:
            cur.execute("INSERT INTO eventlog (seq, prev_hash, hash, ts, actor, event_type, payload) "
                        "VALUES (999999,'x','y',0,'selfaudit','hack','{}')")


def test_ac4_severe_anomaly_escalated_no_halt(fresh_ledger):
    mgr, sentinel, sa = _setup(fresh_ledger)
    _seed_divergence(mgr, 3)                                     # 100% divergence rate → high finding
    out = sa.inspect()
    assert any(f["severity"] == "high" for f in out["findings"])
    assert out["escalations"] and out["escalations"][0]["sentinel_decision"] == "note"
    assert sentinel.halted is False                             # the model escalates; it never halts


def test_ac5_system_runs_without_selfaudit(fresh_ledger):
    # Self-Audit is NOT on the critical path: the Manager records + serves with no SelfAudit attached.
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    mgr.add_feature("F", "x")
    assert mgr.health()["alive"] is True and mgr.list_features()


def test_ac6_metatrust_is_system_not_agent(fresh_ledger):
    from selfaudit import metatrust
    sc = metatrust.score({"verdict_total": 4, "divergence": 0, "verdict_escalate": 0, "qa_findings": 0})
    assert "score" in sc and "contributing_signals" in sc       # a SYSTEM-level score, not per-agent trust


def test_ac7_false_positive_no_wrongful_halt(fresh_ledger):
    _, sentinel, sa = _setup(fresh_ledger)
    # even a HIGH finding only flags; the Sentinel (confirmed_critical=False) declines to halt
    from selfaudit import escalate
    escalate.maybe_escalate([{"pattern": "false alarm", "severity": "high"}], sentinel)
    assert sentinel.halted is False


def test_ac8_retro_benchmark_zero_frontier(fresh_ledger):
    _, _, sa = _setup(fresh_ledger)
    assert sa.run_retro()["frontier_calls"] == 0 and sa.run_benchmark()["frontier_calls"] == 0


def test_ac9_sentinel_probes_selfaudit_liveness(fresh_ledger):
    _, sentinel, sa = _setup(fresh_ledger)
    sentinel.register("selfaudit", critical=False, health_fn=sa.health)
    r = sentinel.probe("selfaudit")
    assert r["healthy"] is True and sa.health()["model_loaded"] is True   # honest flag, not hardcoded


def test_ac10_findings_persist_in_db(fresh_ledger):
    mgr, _, sa = _setup(fresh_ledger)
    _seed_divergence(mgr, 3)
    rid = sa.inspect()["report_id"]
    assert any(r["report_id"] == rid for r in sa.reports())     # queryable DB rows, not agent memory


def test_ac11_inspection_respects_resource_bounds(fresh_ledger):
    mgr, _, sa = _setup(fresh_ledger, max_events=10)
    for i in range(25):
        mgr._record("verdict.computed", {"verdict": "done", "feature_id": f"F{i}"}, feature_id=f"F{i}")
    assert sa.inspect()["observations"]["events_scanned"] <= 10


def test_ac12_toras_ready_seam(fresh_ledger):
    from selfaudit.model_host import InspectionModel
    class Custom(InspectionModel):
        name = "custom"
        def assess(self, obs):
            return [{"pattern": "custom-seam finding", "severity": "low", "occurrences": 1}]
    _, _, sa = _setup(fresh_ledger, model=Custom())
    out = sa.inspect()
    assert any(f["pattern"] == "custom-seam finding" for f in out["findings"]) and sa.model.frontier_calls == 0
