"""
Edge/race cases from Integration PRD §5 (R1–R16). DOCKER-FREE subset only — these gate every run.

Coverage map (so the deferral is honest, not silent):
  R1  one-branch-one-room race ........ LIVE (needs provision_room+Postgres) → make prove / flow tests
  R2  verdict after room destroyed ..... LIVE → covered by the moat verdict-on-branch behaviour
  R3  signature replay .................. covered by tests/integration/test_flow_e_human_signs.py (deferred)
  R4  eventlog unwritable mid-flow ...... LIVE (Manager+Postgres) → make prove
  R5  Docker full / no container ........ LIVE (Docker) → make prove
  R6  governor flapping (no thrash) ..... MULTI-PROCESS — DEFERRED, named (needs concurrent probes)
  R7  heartbeat silence = alarm ......... HERE (docker-free)
  R8  two operators sign same card ...... covered by flow_e dedupe + BUG-3 (deferred)
  R9  stale snapshot SHA ............... covered by tests/govengine ac7 (deferred)
  R10 self-audit confidently wrong ..... covered by tests/selfaudit (deferred)
  R11 maintenance window auto-close .... HERE (docker-free)
  R12 projection drift / replay ........ LIVE (Postgres replay) → Phase 4 persistence proof
  R13 QA room == build room (independence) LIVE (provision) → make prove
  R14 forbidden+in-scope precedence .... covered by tests/leash/test_policy_logic.py (gate)
  R15 dependency-manifest edit escalates  covered by tests/leash/test_policy_logic.py (gate)
  R16 FrozenPolicy immutable ........... covered by tests/leash/test_policy_logic.py (gate)
  LOAD tests (many parallel rooms) ..... MULTI-PROCESS — DEFERRED, named.
"""
from sentinel.core import Sentinel


def test_R7_heartbeat_silence_is_the_alarm():
    """The canary base case: if the heartbeat does not advance, the Sentinel is considered dead."""
    s = Sentinel()
    seen = s.heartbeat()                 # advance once; external watcher records `seen`
    assert s.heartbeat_alive(seen) is False      # no further beat → silence → dead (alarm)
    s.heartbeat()                        # it beats again
    assert s.heartbeat_alive(seen) is True       # advanced past last_seen → alive


def test_R11_maintenance_window_requires_human_and_auto_closes():
    s = Sentinel()
    # (a) maintenance cannot be opened without human authority (FR-15)
    assert s.set_maintenance(["disk"], ticks=2, human_authority=False)["ok"] is False
    # (b) a human opens a bounded window → matching alarms are suppressed WHILE open
    assert s.set_maintenance(["disk"], ticks=2, human_authority=True)["ok"] is True
    assert s.alarm("degraded", "disk pressure").get("suppressed") is True
    # (c) a NON-matching alarm is never silenced, even inside the window
    assert s.alarm("critical", "governor down").get("suppressed") is not True
    # (d) the window auto-closes after N ticks → alarms fire again (never silences outside the window)
    s.tick(); s.tick()
    assert s.alarm("degraded", "disk pressure").get("suppressed") is not True
