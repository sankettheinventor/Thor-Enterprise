"""
Sub-module 2.7 — Decision Recorder + the signed, hash-chained EventLog.

Every allow/deny/escalate becomes a first-class, signed, append-only event (FR-11, AC-3).
This is the audit trail: altering any past entry breaks the hash chain visibly.

⚠️ This is a LOCAL stub for ThorManager's EventLog (Module 3). The PRD has the Leash POST
decisions to ThorManager `:7100 /events/append`; until M3 exists we append to a local JSONL
file, signed with the same Ed25519 instance key (wall.identity_stamper). At M3 the recorder's
sink swaps from "local file" to "ThorManager" — the signing + chaining stay identical.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

from wall.identity_stamper import IdentityStamper

from .policy import Verdict

GENESIS = "GENESIS"


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


class EventLog:
    """Append-only, signed, hash-chained event stream (the audit trail / replay source)."""

    def __init__(self, path: str = ".thor/eventlog.jsonl", stamper: IdentityStamper | None = None) -> None:
        self.path = path
        self.stamper = stamper or IdentityStamper()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

    def _records(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, event_type: str, payload: dict, actor: str = "leash") -> dict:
        records = self._records()
        prev_hash = records[-1]["hash"] if records else GENESIS
        body = {
            "seq": len(records),
            "prev_hash": prev_hash,
            "timestamp": time.time(),
            "actor": actor,
            "event_type": event_type,
            "payload": payload,
        }
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        signature = self.stamper.sign_blob(digest.encode())
        record = {**body, "hash": digest, "signature": signature}
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def verify_chain(self) -> bool:
        """Recompute every hash, every signature, and every prev-link. True iff intact."""
        prev = GENESIS
        for rec in self._records():
            body = {k: rec[k] for k in ("seq", "prev_hash", "timestamp", "actor", "event_type", "payload")}
            digest = hashlib.sha256(_canonical(body)).hexdigest()
            if digest != rec["hash"]:
                return False
            if rec["prev_hash"] != prev:
                return False
            if not self.stamper.verify_blob(digest.encode(), rec["signature"]):
                return False
            prev = rec["hash"]
        return True

    def count(self) -> int:
        return len(self._records())


class DecisionRecorder:
    """Thin recorder: turns a Verdict on an action into a signed `action.decided` event."""

    def __init__(self, eventlog: EventLog) -> None:
        self.eventlog = eventlog

    def record_decision(self, verdict: Verdict, action: dict) -> dict:
        decision_id = uuid.uuid4().hex
        return self.eventlog.append(
            "action.decided",
            {
                "decision_id": decision_id,
                "room_id": action.get("room_id"),
                "action": {"type": action.get("type"), "name": action.get("name"),
                           "target": action.get("target")},
                "decision": verdict.decision,
                "reason": verdict.reason,
                "classification": verdict.classification,
            },
        )
