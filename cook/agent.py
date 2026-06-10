"""
The Cook — the AI builder that writes code for a feature. THOR's invariant (FR-1/FR-2): the cook
NEVER touches governance; EVERY action it proposes is submitted to the Leash (allow / deny / escalate
decided BEFORE any side effect).

The PRODUCTION cook is **Claude Code running inside the sealed room**, governed by the Leash via the
`leash.claude_code_hook` PreToolUse hook (wired through managed settings the cook cannot disable). See
`wall/image/Dockerfile.claude` + DEPLOYMENT.md.

This module is the IN-PROCESS governance seam used by tests/demo:
  ScriptedCook — a deterministic cook (a fixed action list); every action routed through the Leash
                 proxy by `run_through_leash`. The same invariant, exercised with no LLM/no network.

Architectural note: the cook PROPOSES, the Leash DISPOSES. Governance is the Leash gating each action —
independent of where the cook process runs (in-room Claude Code, or this in-process scripted cook).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


def run_through_leash(actions: list[dict], proxy, room_id: str) -> dict:
    """Submit EACH proposed action through the Leash proxy. The cook can only effect the changes the
    governor permitted — an out-of-scope / forbidden / unsafe action is blocked before it hits disk."""
    allowed: list[dict] = []
    denied: list[dict] = []
    escalated: list[dict] = []
    for a in actions:
        res = proxy.handle_tool_call(
            {"name": a["name"], "room_id": room_id, "args": a.get("args", {})})
        {"allow": allowed, "deny": denied, "escalate": escalated}.get(res["status"], denied).append(
            {**a, "_verdict": res})
    return {"allowed": allowed, "denied": denied, "escalated": escalated,
            "n_allowed": len(allowed), "n_denied": len(denied), "n_escalated": len(escalated)}


class CookAgent(ABC):
    @abstractmethod
    def propose(self, feature_slice: dict) -> list[dict]:
        """The actions the cook WANTS to take: [{name, args:{path, content}}, ...]. UNTRUSTED — the
        Leash decides what actually happens."""

    def build(self, feature_slice: dict, proxy) -> dict:
        """Propose actions, then route EACH through the Leash. The returned summary reflects REALITY
        (what the governor allowed), never the cook's intent."""
        actions = self.propose(feature_slice)
        room_id = feature_slice.get("room_id") or feature_slice.get("feature_id")
        return run_through_leash(actions, proxy, room_id)


class ScriptedCook(CookAgent):
    """Deterministic cook — a fixed action list. No LLM, no network (tests / demo / CI)."""

    def __init__(self, actions: list[dict]) -> None:
        self._actions = actions

    def propose(self, feature_slice: dict) -> list[dict]:
        return list(self._actions)
