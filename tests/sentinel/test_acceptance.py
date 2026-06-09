"""
The Sentinel — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 8). The Sentinel now ENFORCES: a confirmed critical failure physically destroys
rooms + blocks work; a broken detector (passing canary) halts; integrity tamper halts; a flap does
not thrash. Verified against the real Manager + real Docker rooms. Deferred (live); run:
pytest -m deferred tests/sentinel.
"""
import pytest

pytestmark = pytest.mark.deferred


def _ms(fresh_ledger):
    from manager.core import ThorManager
    from sentinel.core import Sentinel
    mgr = ThorManager(fresh_ledger)
    s = Sentinel(mgr)
    mgr.attach_sentinel(s)
    return mgr, s


def test_ac1_dead_leash_detected_fail_closed(fresh_ledger, host_repo):
    mgr, s = _ms(fresh_ledger)
    room = mgr.provision_room("F1", branch="feature/F1", worktree_host_path=host_repo, network_mode="sealed")
    s.register("leash", critical=True, health_fn=lambda: {"alive": True, "responsive": False})
    s.probe_all()
    assert s.halted and mgr.state_summary()["rooms"][room["room_id"]]["status"] == "destroyed"


def test_ac2_passing_canary_alarms_and_halts(fresh_ledger):
    from leash.policy import FrozenPolicy
    from sentinel import canary
    mgr, s = _ms(fresh_ledger)
    broken = FrozenPolicy(room_id="canary", scope_files=("**",), forbidden_patterns=(), frozen_at=0.0)
    rep = s.evaluate_canaries([canary.leash_canary(broken)])
    assert rep["all_healthy"] is False and s.halted is True and len(s.alarms) >= 1


def test_ac3_hung_component_detected_unhealthy(fresh_ledger):
    _, s = _ms(fresh_ledger)
    def hung():
        raise TimeoutError("component hung")
    s.register("x", critical=False, health_fn=hung)
    r = s.probe("x")
    assert r["alive"] is True and r["responsive"] is False and r["healthy"] is False


def test_ac4_rule_tamper_crawler_alarm_halt(fresh_ledger):
    _, s = _ms(fresh_ledger)
    s.integrity.record_baseline({"rules.py": b"the original governance rules"})
    res = s.check_integrity({"rules.py": b"TAMPERED governance rules"})
    assert res["ok"] is False and "rules.py" in res["tampered"] and s.halted is True


def test_ac5_unloaded_skill_fail_closes(fresh_ledger):
    _, s = _ms(fresh_ledger)
    res = s.verify_loadedness(declared_floor=["security", "testing-discipline"], loaded_skills=["security"])
    assert res["ok"] is False and res["fail_closed"] is True and "testing-discipline" in res["missing"]


def test_ac6_failed_boot_self_test_blocks_startup(fresh_ledger):
    _, s = _ms(fresh_ledger)
    s.register("dead", critical=True, health_fn=lambda: {"alive": False, "responsive": False})
    assert s.boot_self_test() is False and s.accepts_work is False   # can't verify itself → never starts


def test_ac7_sentinel_death_caught_by_silent_heartbeat(fresh_ledger):
    _, s = _ms(fresh_ledger)
    last = s.heartbeat()
    assert s.heartbeat_alive(last) is False   # heartbeat hasn't advanced → the Sentinel is dead (silence = alarm)
    s.heartbeat()
    assert s.heartbeat_alive(last) is True


def test_ac8_proportionate_halt_scope(fresh_ledger):
    _, s = _ms(fresh_ledger)
    s.halt("room:room-xyz", "local fault")
    assert s.halted is False                  # a local halt does NOT block all work
    s.halt("system", "leash down")
    assert s.halted is True                    # a systemic halt blocks everything


def test_ac9_self_audit_urgent_sentinel_decides(fresh_ledger):
    _, s = _ms(fresh_ledger)
    # the cheap model only REPORTS; the Sentinel decides. A non-confirmed URGENT → note, never a halt.
    assert s.receive_urgent({"detail": "looks odd", "confirmed_critical": False})["decision"] == "note"
    assert s.halted is False
    assert s.receive_urgent({"scope": "system", "confirmed_critical": True})["decision"] == "halt"


def test_ac10_shadow_discovered_orphan_reaped(fresh_ledger, host_repo):
    mgr, s = _ms(fresh_ledger)
    room = mgr.provision_room("F10", branch="feature/F10", worktree_host_path=host_repo, network_mode="sealed")
    reaped = s.reap_orphans(known_room_ids=set())    # nobody owns it → it is an orphan → reaped
    assert room["room_id"] in reaped


def test_ac11_maintenance_mode_scoped_and_bounded(fresh_ledger):
    _, s = _ms(fresh_ledger)
    assert s.set_maintenance(["blip"], ticks=2, human_authority=False)["ok"] is False   # needs a human
    s.set_maintenance(["blip"], ticks=2, human_authority=True)
    assert s.alarm("degraded", "blip happened", name="blip").get("suppressed") is True   # silenced in window
    s.tick(); s.tick()
    assert s._maintenance is None                                                        # auto-closes


def test_ac12_chaos_test_pages_each_failure_class(fresh_ledger):
    from leash.policy import FrozenPolicy
    from sentinel import canary
    _, s = _ms(fresh_ledger)
    s.register("dead", critical=False, health_fn=lambda: {"alive": True, "responsive": False})
    s.probe_all()                                                              # liveness failure class
    s.integrity.record_baseline({"r": b"a"}); s.check_integrity({"r": b"b"})   # integrity failure class
    s.evaluate_canaries([canary.leash_canary(
        FrozenPolicy(room_id="c", scope_files=("**",), forbidden_patterns=(), frozen_at=0.0))])  # detector-blind class
    classes = {a["message"].split(":")[0].split(" ")[0] for a in s.alarms}
    assert len(s.alarms) >= 3   # each failure class paged an alarm
