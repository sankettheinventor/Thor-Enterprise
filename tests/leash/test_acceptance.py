"""
The Leash — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 3). The Phase-2a ACs verify the WIRED decide-before path against reality — a
real Postgres-backed Manager ledger, the real InRoomProxy + policy engine + AGT adapter, a real
worktree on disk. No stand-ins (Rule 11). Deferred (live); run: pytest -m deferred tests/leash.

AC-1/2/3/4/5/6/7/8/11 prove now (the cook path + the one-door egress lock are wired). AC-9/10/12
(kill-switch on a malicious tool-def, under-load no-unaudited-allow, AGT upgrade) stay skipped.
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


def _one_door_room(tag, allowlist=("example.com",)):
    """Start the leash gateway + a one-door room. Returns (cli, room); caller tears down."""
    import tempfile

    import docker

    from leash import gateway
    from wall import provisioner

    cli = docker.from_env()
    for n in (gateway.GATEWAY_NAME, gateway.UPSTREAM_NAME):
        for c in cli.containers.list(all=True, filters={"name": n}):
            c.remove(force=True)
    wt = tempfile.mkdtemp(prefix=f"{tag}-")
    os.chmod(wt, 0o777)
    gateway.start_gateway(cli, leash_host_path=os.path.join(os.getcwd(), "leash"),
                          decision_log_dir=f"/tmp/leash-{tag}", allowlist=allowlist)
    room = provisioner.provision_room(task_type="build", feature_slice={"feature_id": tag.upper()},
                                      worktree_host_path=wt, network_mode="one_door")
    return cli, room


def test_ac5_raw_http_bypass_blocked():
    """AC-5: from a one-door room, a raw-HTTP egress to a NON-allowlisted host is blocked (Layer B);
    only the single governed door (the allowlisted host) is reachable."""
    from leash import gateway
    from wall import network_enforcer as ne
    from wall import provisioner

    cli, room = _one_door_room("ac5", allowlist=("example.com",))
    c = cli.containers.get(room["room_id"])
    try:
        assert ne.assert_no_internet(c), "the room must be on the internal net ONLY"

        def reach(url):
            code = ("import urllib.request as u\n"
                    "try:\n  print('OK', u.urlopen(%r, timeout=12).status)\n"
                    "except Exception as e:\n  print('BLOCKED', type(e).__name__)\n" % url)
            return c.exec_run(["python3", "-c", code], user="cook").output.decode().strip()

        assert reach("https://www.google.com").startswith("BLOCKED"), "raw egress to a non-allowlisted host must be blocked"
        assert reach("https://example.com").startswith("OK"), "the one allowlisted door must work"
    finally:
        provisioner.destroy_room(room["room_id"], room.get("_mount_plan"))
        gateway.teardown(cli)


def test_ac6_no_credentials_inside_container():
    """AC-6: the upstream model credential lives in the GATEWAY, never in the room env (capability
    separation) — the cook cannot read or leak it."""
    from leash import gateway
    from wall import provisioner

    # Production keeps NO hardcoded secret (it comes from env); this test supplies its OWN non-empty test
    # credential to verify the capability separation (cred in the gateway, never in the room).
    gateway.UPSTREAM_CRED = "AC6-TEST-UPSTREAM-CRED-do-not-leak"
    cli, room = _one_door_room("ac6")
    try:
        room_env = cli.containers.get(room["room_id"]).exec_run(["env"], user="cook").output.decode()
        assert gateway.UPSTREAM_CRED not in room_env, "the credential must NEVER appear in the room"
        gw_env = cli.containers.get(gateway.GATEWAY_NAME).exec_run(["env"]).output.decode()
        assert gateway.UPSTREAM_CRED in gw_env, "the credential must live in the gateway"
    finally:
        provisioner.destroy_room(room["room_id"], room.get("_mount_plan"))
        gateway.teardown(cli)


def test_ac7_dependency_add_escalates_and_holds(fresh_ledger, host_repo):
    """AC-7: a dependency-manifest add escalates and is HELD (not written); recorded in the ledger."""
    proxy, mgr = _proxy(fresh_ledger, host_repo)
    res = _write(proxy, "package.json", "{}")
    assert res["status"] == "escalate" and res.get("held") is True
    assert not os.path.exists(os.path.join(host_repo, "package.json"))
    assert any(e["event_type"] == "action.escalated" for e in mgr.eventlog.all_events())


def test_ac8_second_cook_governed_same_leash(fresh_ledger, host_repo):
    """AC-8: a DIFFERENT cook (an arbitrary ScriptedCook, not the default code_files puppet) is governed
    by the SAME Leash — its in-scope write lands, its out-of-scope escape is denied before disk."""
    from cook.agent import ScriptedCook

    proxy, mgr = _proxy(fresh_ledger, host_repo)
    cook = ScriptedCook([
        {"name": "write_file", "args": {"path": "src/ok.py", "content": "x = 1\n"}},          # in scope
        {"name": "write_file", "args": {"path": "infra/evil.tf", "content": "leak"}},         # out of scope
    ])
    result = cook.build({"room_id": ROOM}, proxy)
    status = {a["args"]["path"]: a["_verdict"]["status"]
              for a in (result["allowed"] + result["denied"] + result["escalated"])}
    assert status.get("src/ok.py") == "allow", status
    assert status.get("infra/evil.tf") == "deny", status
    assert os.path.exists(os.path.join(host_repo, "src/ok.py"))
    assert not os.path.exists(os.path.join(host_repo, "infra/evil.tf"))


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
