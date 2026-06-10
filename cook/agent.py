"""
The Cook — the AI builder that writes code for a feature. THOR's invariant (FR-1/FR-2): the cook
NEVER touches governance; EVERY action it proposes is submitted through the Leash proxy (allow / deny /
escalate decided BEFORE any side effect). This module provides that governed-build loop plus two cooks
behind one interface:

  ScriptedCook — a deterministic cook (a fixed action list). Tests / demo / CI; no LLM, no network.
  ClaudeCook   — a real LLM builder (Anthropic). It asks the model for a list of file-write actions and
                 routes EACH through the Leash. The client is injectable (unit-testable with a stub).
                 A LIVE run additionally needs: ANTHROPIC_API_KEY, the `anthropic` SDK, and the sealed
                 room's ONE-DOOR egress (M2 Phase 2b) so the room can reach the API. Until egress lands,
                 a live cook runs control-plane-side; the Leash governs every action either way.

Architectural note: the cook PROPOSES, the Leash DISPOSES. Governance is the Leash gating each action —
independent of where the cook process runs. The hardened target is an in-room agent-server behind the
one-door egress; the seam below does not change when that lands.
"""
from __future__ import annotations

import json
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


class ClaudeCook(CookAgent):
    """Real LLM builder (Anthropic). `client` is injectable so this is unit-testable with a stub; a live
    run needs ANTHROPIC_API_KEY + the `anthropic` SDK + the room's one-door egress."""

    def __init__(self, client=None, model: str = "claude-opus-4-8") -> None:
        self._client = client
        self.model = model

    def _llm(self):
        if self._client is None:
            import anthropic   # lazy — only a LIVE run needs the SDK/key
            self._client = anthropic.Anthropic()
        return self._client

    def propose(self, feature_slice: dict) -> list[dict]:
        prompt = (
            "You are a THOR cook. Implement the feature writing ONLY files within scope_files. Reply "
            "with a JSON array of actions: [{\"name\":\"write_file\",\"args\":{\"path\":\"...\","
            "\"content\":\"...\"}}]. Feature: "
            + json.dumps({k: feature_slice.get(k) for k in
                          ("feature_id", "acceptance_criteria", "scope_files", "planned_test")}))
        msg = self._llm().messages.create(
            model=self.model, max_tokens=4096, messages=[{"role": "user", "content": prompt}])
        block = msg.content[0]
        text = block.text if hasattr(block, "text") else block["text"]
        start, end = text.find("["), text.rfind("]")           # the model may wrap JSON in prose/fences
        return json.loads(text[start:end + 1]) if start != -1 and end != -1 else []
