"""
Sub-module 2.7 — Decision Recorder.

Every allow/deny/escalate becomes a first-class, signed, append-only event (FR-11, AC-3).
This is the audit trail.

H7 (T2): the recorder now sinks THROUGH the ThorManager (Module 3) — the SOLE EventLog writer —
instead of its own local `.thor/eventlog.jsonl` chain. There is ONE ledger. The signing + hash-
chaining live in the Manager's EventLogWriter; routing here goes via `Manager.record_decision`
(for decisions) and `Manager._record` (for the Leash's other governed records: escalation holds,
kill-switch events). The old local `EventLog` class is retired (the second ledger is gone).
"""
from __future__ import annotations

import uuid

from .policy import Verdict


class DecisionRecorder:
    """Turns a Verdict on an action into a signed `action.decided` event, recorded THROUGH the
    Manager (the single ledger). Also the Leash's record path for its other governed events."""

    def __init__(self, manager) -> None:
        self.manager = manager   # ThorManager — the sole EventLog writer (H7)

    def record_decision(self, verdict: Verdict, action: dict) -> dict:
        # Preserve the Leash decision_id (the Manager carries it through record_decision now).
        decision_id = action.get("decision_id") or uuid.uuid4().hex
        return self.manager.record_decision(verdict, {**action, "decision_id": decision_id})

    def record_event(self, event_type: str, payload: dict, **kw) -> dict:
        """Record any other governed Leash event through the Manager (actor=leash). Routes through
        `_record` so it hits the fail-closed gate + projection — never the raw eventlog."""
        return self.manager._record(event_type, payload, actor="leash", **kw)
