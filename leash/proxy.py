"""
Sub-module 2.1 — In-Room Proxy. The cook's only exit; the enforcement point.

Every tool/model call the cook makes hits the proxy first (FR-1). The proxy does NOT decide;
it asks the AGT adapter and ENFORCES the verdict (FR-2): allow→execute, deny→block with reason,
escalate→hold. Fail-closed throughout (FR-6/P2): if the governor is unreachable, or the decision
cannot be recorded, the action is DENIED — never allowed.

The critical invariant: the real side effect (`_execute`) happens ONLY after an `allow`. The
check is strictly pre-action (P3) — an out-of-scope write is stopped before the file is touched.

Phase 2a runs the proxy logic in-process (the smoke calls `handle_tool_call`). The HTTP service
on :8001 and the physical one-door wiring (so this is the ONLY egress) are Phase 2b.
"""
from __future__ import annotations

import os

from . import inspector
from .decision import DecisionRecorder
from .escalation import EscalationRouter
from .policy import Verdict


class GovernanceDenied(Exception):
    """Raised/returned to the cook when an action is denied — carries the structured reason (FR-4)."""


class InRoomProxy:
    def __init__(self, adapter, recorder: DecisionRecorder, worktree_root: str,
                 escalation: EscalationRouter | None = None) -> None:
        self.adapter = adapter                 # the AGT adapter (THOR-vocabulary check_action)
        self.recorder = recorder
        self.worktree_root = worktree_root
        self.escalation = escalation or EscalationRouter(recorder)

    def handle_tool_call(self, tool_call: dict) -> dict:
        """Intercept one structured tool call, govern it pre-action, enforce the verdict."""
        action = inspector.inspect_tool_call(tool_call)   # Layer A normalization

        # Ask the governor. Fail-closed if it is unreachable or errors (P2/FR-6).
        try:
            verdict = self.adapter.check_action(action)
        except Exception as e:  # adapter down / AGT error / timeout → DENY, never allow
            verdict = Verdict("deny", f"governor_unavailable: {e}", "denied")

        # Record the decision. If we cannot record it, we cannot allow it (no unaudited actions).
        try:
            self.recorder.record_decision(verdict, action)
        except Exception as e:
            return {"status": "deny", "reason": f"unaudited_action_forbidden: {e}"}

        # Enforce. The side effect happens ONLY on allow (strictly pre-action — P3).
        if verdict.decision == "allow":
            try:
                self._execute(action)
            except GovernanceDenied as e:   # BUG-1 defense-in-depth: a path that slipped scope is
                return {"status": "deny", "reason": str(e)}   # still refused at the disk boundary
            return {"status": "allow", "classification": verdict.classification}
        if verdict.decision == "escalate":
            self.escalation.hold(action, verdict)
            return {"status": "escalate", "reason": verdict.reason, "held": True}
        return {"status": "deny", "reason": verdict.reason}

    def _execute(self, action: dict) -> None:
        """Perform the approved tool. Only reached AFTER an allow verdict."""
        name = action.get("name")
        if name in ("write_file", "append_file", "edit_file"):
            target = action["target"]
            # BUG-1 defense-in-depth: even past the policy, refuse a write that resolves outside the
            # worktree. Reject absolute / '..' targets, then assert the REAL (symlink-resolved) path is
            # contained — so neither path-traversal nor a symlink can put the side effect outside the room.
            if target.startswith("/") or target.startswith("\\") or ".." in target.replace("\\", "/").split("/"):
                raise GovernanceDenied(f"path traversal blocked at disk boundary: {target!r}")
            root = os.path.realpath(self.worktree_root)
            path = os.path.realpath(os.path.join(root, target))
            if path != root and not path.startswith(root + os.sep):
                raise GovernanceDenied(f"resolved path escapes the worktree: {target!r}")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            mode = "a" if name == "append_file" else "w"
            with open(path, mode) as f:
                f.write(action["args"].get("content", ""))
        # other tools (read_file, run, model_call forwarding) are wired as the cook/agent lands (Phase 2b)
