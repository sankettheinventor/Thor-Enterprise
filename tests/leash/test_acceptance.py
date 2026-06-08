"""
The Leash — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 3). The Phase-2a ACs verify the WIRED decide-before path against reality — a
real Postgres-backed Manager ledger, the real InRoomProxy + policy engine + AGT adapter, a real
worktree on disk. No stand-ins (Rule 11). Deferred (live); run: pytest -m deferred tests/leash.

AC-1/2/3/4/7/11 prove now (the cook path is wired at C1). AC-5/6/8/9/10/12 need Phase 2b
(egress lock, credentials, cook-adapter, kill-switch, load test, AGT upgrade) and stay skipped.
"""
import dataclasses
import os

import pytest

pytestmark = pytest.mark.deferred

ROOM = "room-leash-ac"


def _proxy(conn, worktree, scope=("src/",), forbidden=("infra/",), adapter=None):
    """Build the REAL wired proxy: a frozen policy loaded host-side + a Manager-backed recorder."""
    from adapters import agt_adapter
    from leash.decision import DecisionRecorder
    from leash.policy import FrozenPolicy
    from leash.proxy import InRoomProxy
    from manager.core import ThorManager

    mgr = ThorManager(conn)
    agt_adapter.load_policy(FrozenPolicy(room_id=ROOM, scope_files=scope,
                                         forbidden_patterns=forbidden, frozen_at=0.0))
    proxy = InRoomProxy(adapter or agt_adapter, DecisionRecorder(mgr), worktree)
    return proxy, mgr


def _write(proxy, path, content="x"):
    return proxy.handle_tool_call({"name": "write_file", "room_id": ROOM,
                                   "args": {"path": path, "content": content}})


class _DownAdapter:
    def check_action(self, action):
        raise ConnectionError("governor unreachable")


def test_ac1_out_of_scope_denied_before_write(fresh_ledger, host_repo):
    """AC-1: an out-of-scope path is denied BEFORE the write happens (file never created)."""
    proxy, _ = _proxy(fresh_ledger, host_repo, scope=("src/",))
    res = _write(proxy, "docs/notes.py")
    assert res["status"] == "deny"
    assert not os.path.exists(os.path.join(host_repo, "docs/notes.py"))


def test_ac2_denial_reaches_cook_with_reason(fresh_ledger, host_repo):
    """AC-2: the denial reaches the cook with a structured, legible reason."""
    proxy, _ = _proxy(fresh_ledger, host_repo)
    res = _write(proxy, "infra/x.tf")
    assert res["status"] == "deny" and isinstance(res.get("reason"), str) and res["reason"]


def test_ac3_every_decision_signed_event(fresh_ledger, host_repo):
    """AC-3: every allow/deny is a signed event in the single ledger (chain verifies)."""
    proxy, mgr = _proxy(fresh_ledger, host_repo)
    _write(proxy, "src/ok.py")       # allow
    _write(proxy, "docs/no.py")      # deny
    decided = [e for e in mgr.eventlog.all_events() if e["event_type"] == "action.decided"]
    assert len(decided) >= 2 and all(e["actor"] == "leash" for e in decided)
    assert mgr.eventlog.verify_chain() is True


def test_ac4_adapter_down_denies_all(fresh_ledger, host_repo):
    """AC-4: with the AGT adapter down, the action is denied — fail-closed (no write)."""
    proxy, _ = _proxy(fresh_ledger, host_repo, adapter=_DownAdapter())
    res = _write(proxy, "src/ok.py")
    assert res["status"] == "deny" and "governor_unavailable" in res.get("reason", "")
    assert not os.path.exists(os.path.join(host_repo, "src/ok.py"))


@pytest.mark.skip(reason="Phase 2b: raw-HTTP/Layer-B needs the one-door network lock (M2). No fake green (Rule 11).")
def test_ac5_raw_http_bypass_blocked():
    """AC-5: a raw-HTTP bypass is blocked by Layer B."""


@pytest.mark.skip(reason="Phase 2b: credential isolation lands with the AGT credential injector (M12).")
def test_ac6_no_credentials_inside_container():
    """AC-6: credentials never appear inside the container."""


def test_ac7_dependency_add_escalates_and_holds(fresh_ledger, host_repo):
    """AC-7: a dependency-manifest add escalates and is HELD (not written); recorded in the ledger."""
    proxy, mgr = _proxy(fresh_ledger, host_repo)
    res = _write(proxy, "package.json", "{}")
    assert res["status"] == "escalate" and res.get("held") is True
    assert not os.path.exists(os.path.join(host_repo, "package.json"))
    assert any(e["event_type"] == "action.escalated" for e in mgr.eventlog.all_events())


@pytest.mark.skip(reason="Phase 2b: a non-Claude cook via its Cook-adapter (M12).")
def test_ac8_second_cook_governed_same_leash():
    """AC-8: a different cook is governed by the same Leash."""


@pytest.mark.skip(reason="Phase 2b: kill-switch on a malicious tool-def is exercised by smoke_leash_2b (M12).")
def test_ac9_malicious_tool_triggers_killswitch():
    """AC-9: a malicious tool definition triggers the kill-switch."""


@pytest.mark.skip(reason="Phase 2b: under-load no-unaudited-allow is a load test (M2 Phase 2b).")
def test_ac10_no_unaudited_allows_under_load():
    """AC-10: under load, no action is allowed without a recorded decision."""


def test_ac11_policy_immutable_from_inside_room():
    """AC-11: the per-room policy is frozen — the cook cannot relax its own scope from inside."""
    from leash.policy import FrozenPolicy
    p = FrozenPolicy(room_id="r", scope_files=("src/",), forbidden_patterns=(), frozen_at=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.scope_files = ("anything/",)  # type: ignore[misc]


@pytest.mark.skip(reason="Phase 2b/M12: an AGT version bump only touching the adapter is the Strangler test (T10).")
def test_ac12_agt_version_bump_only_touches_adapter():
    """AC-12: an AGT version bump doesn't break THOR — only the adapter changes."""
