"""
FINDING-B (HIGH) + FINDING-C (MED): the Sentinel HALT must fail CLOSED.

The C3 guarantee is that a halt physically ENFORCES — it must never silently no-op. Two fail-open holes
the audit found:
  B — if the Manager state is unreadable (e.g. Postgres down, exactly when halts fire), `_destroy_rooms`
      used to `return []` and destroy NOTHING, silently.
  C — if `destroy_room` failed, it was swallowed as "already gone"; a room that genuinely refused to die
      survived the halt with NO alarm.

These tests are DOCKER-FREE: a fake Manager simulates the failures and an injected fake LifecycleController
stands in for Docker. They assert the Sentinel now ALARMS (fail-closed) instead of silently no-opping.
"""
from sentinel.core import Sentinel


class _FakeLC:
    """Stands in for the Docker-label room killer (no real Docker)."""

    def __init__(self, rooms=None, alive=False):
        self._rooms = rooms or []
        self._alive = alive

    def list_rooms(self):
        return self._rooms

    def destroy(self, rid):
        return {"room_id": rid, "status": "destroyed"}

    def health(self, rid):
        return type("H", (), {"alive": self._alive})()


class _FakeMgr:
    def __init__(self, rooms=None, raise_state=False, raise_destroy=False):
        self._rooms = rooms or {}
        self._raise_state = raise_state
        self._raise_destroy = raise_destroy
        self.destroyed = []

    def state_summary(self):
        if self._raise_state:
            raise RuntimeError("postgres unreachable")
        return {"rooms": self._rooms, "cards": {}}

    def destroy_room(self, rid, mount_plan=None):
        if self._raise_destroy:
            raise RuntimeError("docker wedged — container will not die")
        self.destroyed.append(rid)

    def _record(self, *a, **k):
        return {}


def _alarms(s):
    return " | ".join(a["message"] for a in s.alarms)


def test_finding_b_state_unreadable_does_not_silently_skip():
    """B: a halt with unreadable Manager state must ALARM + fall back to a label kill — never silent []."""
    mgr = _FakeMgr(rooms={"r1": {"status": "working"}}, raise_state=True)
    s = Sentinel(mgr, lifecycle=_FakeLC(rooms=[{"room_id": "r1", "status": "running"}]))
    s.halt("system", "leash down")
    assert any("state unreadable" in m for m in (a["message"] for a in s.alarms)), _alarms(s)
    assert s.halts[-1]["rooms_halted"] == ["r1"], "fail-closed fallback must still kill the room by label"


def test_finding_c_failed_destroy_alarms_not_swallowed():
    """C: a room that fails to die during a halt must ALARM (still alive) — never silently skipped."""
    mgr = _FakeMgr(rooms={"r1": {"status": "working"}}, raise_destroy=True)
    s = Sentinel(mgr, lifecycle=_FakeLC(alive=True))   # Docker says it is STILL ALIVE after the attempt
    s.halt("system", "leash down")
    msgs = _alarms(s)
    assert "failed" in msgs.lower() or "still alive" in msgs.lower(), msgs
    assert s.halts[-1]["rooms_halted"] == [], "a room that did not die must NOT be reported as killed"
