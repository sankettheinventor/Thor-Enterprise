"""
BUG-1 (CRITICAL — scope/sandbox escape).

leash/policy._matches() checks the RAW path string, so a cook write whose target *textually*
startswith an in-scope prefix but climbs out with `..` ("src/../../escaped.txt") passes the scope
check and is ALLOWED. leash/proxy._execute() then os.path.join()s that raw target and writes OUTSIDE
the worktree (os.path.join even discards the root entirely for an absolute target). This defeats
FLOW B's sandbox.

This test proves such writes are DENIED and never reach disk outside the worktree.

Docker-free (no Postgres): the policy decision is pure, and the proxy escape uses a no-op recorder —
the bug is in policy+proxy, not the ledger. Un-deferred → runs on every `make qa` / `make test`.
"""
import os
import shutil
import tempfile

from adapters import agt_adapter
from leash.policy import FrozenPolicy, evaluate
from leash.proxy import InRoomProxy

ROOM = "room-bug1"
POLICY = FrozenPolicy(room_id=ROOM, scope_files=("src/",),
                      forbidden_patterns=("infra/", "**/secrets*"),
                      language_lock="python", frozen_at=0.0)

# Targets that TEXTUALLY pass a startswith("src/") scope check but escape via traversal.
TRAVERSAL_TARGETS = [
    "src/../../escaped.txt",
    "src/../etc/passwd",
    "src/../../../../../../../../tmp/thor_escape_bug1",
]


class _NoopRecorder:
    """Records nothing — isolates the test to the policy+proxy path (docker-free, no ledger)."""

    def record_decision(self, verdict, action):
        return {"recorded": True}


def test_bug1_policy_denies_path_traversal():
    """policy.evaluate must DENY a traversal target — never 'allow'."""
    for target in TRAVERSAL_TARGETS:
        v = evaluate(POLICY, {"type": "tool_call", "name": "write_file", "target": target,
                              "room_id": ROOM, "args": {}})
        assert v.decision != "allow", f"traversal target was ALLOWED by policy: {target!r} -> {v}"
    # a genuinely in-scope path must still be allowed (the fix must not over-block)
    ok = evaluate(POLICY, {"type": "tool_call", "name": "write_file", "target": "src/login.py",
                           "room_id": ROOM, "args": {}})
    assert ok.decision == "allow", f"legit in-scope write was wrongly blocked: {ok}"


def test_bug1_proxy_write_cannot_escape_worktree():
    """End-to-end: a traversal write must be denied AND must NOT create a file outside the worktree."""
    base = tempfile.mkdtemp(prefix="thor-bug1-")
    worktree = os.path.join(base, "wt")
    os.makedirs(os.path.join(worktree, "src"))
    agt_adapter.load_policy(POLICY)
    proxy = InRoomProxy(agt_adapter, _NoopRecorder(), worktree)
    try:
        target = "src/../../escaped.txt"   # resolves to base/escaped.txt — OUTSIDE the worktree
        escaped_path = os.path.realpath(os.path.join(worktree, target))
        assert not escaped_path.startswith(os.path.realpath(worktree) + os.sep), \
            "test setup invalid: target must resolve outside the worktree"
        res = proxy.handle_tool_call(
            {"name": "write_file", "room_id": ROOM, "args": {"path": target, "content": "PWNED"}})
        assert res["status"] != "allow", f"traversal write was ALLOWED by the proxy: {res}"
        assert not os.path.exists(escaped_path), f"file escaped the worktree to {escaped_path!r}"
    finally:
        shutil.rmtree(base, ignore_errors=True)
