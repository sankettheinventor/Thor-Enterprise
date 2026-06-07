"""
Sub-module 2.8 — Escalation Router.

For `critical`-classified actions, the action is HELD and a CEO card is raised; it proceeds
only on human approval, else is denied (FR-5, FR-13). The action does NOT auto-allow if the
operator is absent (PRD §10 "Escalation never answered → stays held").

Phase 2a: we record the escalation as an event and hold the action (return held). The full CEO
card flow (ThorManager `:7100 /cards/raise`, dashboard, signature) is Phase 2b / needs Module 3.
"""
from __future__ import annotations

from .decision import DecisionRecorder
from .policy import Verdict


class EscalationRouter:
    def __init__(self, recorder: DecisionRecorder) -> None:
        self.recorder = recorder
        self.held: list[dict] = []   # actions awaiting a human decision (no auto-allow)

    def hold(self, action: dict, verdict: Verdict) -> dict:
        """Record the escalation and hold the action pending a human decision."""
        # H7: record THROUGH the Manager (single ledger). Event type is `action.escalated` — NOT
        # `card.raised`: the authoritative CEO card (with card_id) is raised by Manager.raise_card in
        # the live flow; this is the Leash's audit record of holding the action (no projection row).
        self.recorder.record_event(
            "action.escalated",
            {
                "room_id": action.get("room_id"),
                "action": {"name": action.get("name"), "target": action.get("target")},
                "reason": verdict.reason,
                "classification": verdict.classification,
                "status": "held",
            },
            room_id=action.get("room_id"),
        )
        entry = {"action": action, "reason": verdict.reason, "status": "held"}
        self.held.append(entry)
        return entry
