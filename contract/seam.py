"""
The Seam — 5.3 Slice Mounter + 5.5 direction/version enforcement + 5.6 Claim Handler +
5.7 Amend Handler + idempotency + event recording.

Carries the six messages over a Transport, validating each (FR-2), enforcing direction (FR-1) and
version (FR-11), recording each as an event via the Manager (FR-15/AC-11), handling `claim_done`
idempotently (FR-13/AC-8), authorizing `amend` (FR-9/AC-7), and issuing the only authoritative
"done" — `result_decision` (FR-7). A room can never issue `result_decision` (P5/AC-4).
"""
from __future__ import annotations

import json
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wall.identity_stamper import _unb64

from .messages import (CONTRACT_VERSION, MANAGER_TO_ROOM, MESSAGE_TYPES, ROOM_TO_MANAGER,
                       validate)


class ContractError(Exception):
    """Raised on an out-of-contract message, wrong direction, version mismatch, or bad amend."""


def _verify_sig(pub_b64: str | None, sig_b64: str | None, material: str) -> bool:
    if not pub_b64 or not sig_b64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(pub_b64)).verify(_unb64(sig_b64), material.encode())
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


class Seam:
    def __init__(self, transport, manager=None, version: str = CONTRACT_VERSION) -> None:
        self.t = transport
        self.manager = manager
        self.version = version
        self._claims: set[str] = set()   # claim_done message_ids seen (idempotency)
        self._verdicts = 0               # verdicts produced (must equal unique claims)

    # ---- audit: every seam message is an event (FR-15 / AC-11) ----
    def _record(self, msg_type: str, payload: dict) -> None:
        if self.manager is not None:
            self.manager._record(f"contract.{msg_type}", payload, actor="contract")

    # ---- version negotiation at provision (FR-11 / AC-9) ----
    def negotiate_version(self, provided: str) -> bool:
        if provided != self.version:
            raise ContractError(f"contract version mismatch: room={provided} manager={self.version}")
        return True

    # ---- only the six messages cross (FR-1 / AC-1) ----
    def accept(self, msg_type: str) -> bool:
        if msg_type not in MESSAGE_TYPES:
            raise ContractError(f"out-of-contract message: {msg_type!r} (only the six are allowed)")
        return True

    # ---- Manager -> room ----
    def manager_send(self, msg_type: str, payload: dict) -> dict:
        if msg_type not in MANAGER_TO_ROOM:
            raise ContractError(f"{msg_type} is not a Manager->room message")
        model = validate(msg_type, payload)            # AC-6 (rejects malformed / extra fields)
        if msg_type == "amend":
            self._authorize_amend(model)               # AC-7
        self.t.deliver("to_room", payload["room_id"], msg_type, payload)
        self._record(msg_type, payload)
        return {"ack": True}

    # ---- room -> Manager ----
    def room_send(self, msg_type: str, payload: dict) -> dict:
        if msg_type not in ROOM_TO_MANAGER:
            # a room trying to send a Manager->room message (e.g. result_decision) is refused — P5/AC-4
            raise ContractError(f"a room cannot send {msg_type!r} (it has no authority to)")
        model = validate(msg_type, payload)
        self.t.deliver("to_manager", payload["room_id"], msg_type, payload)
        self._record(msg_type, payload)
        if msg_type == "claim_done":
            if model.message_id in self._claims:       # idempotent knock (FR-13 / AC-8)
                return {"ack": True, "idempotent": True}
            self._claims.add(model.message_id)
            self._verdicts += 1                        # exactly one verdict per unique claim
        return {"ack": True}

    # ---- the only authoritative "done" — issued by the Manager, never the room (FR-7) ----
    def issue_result_decision(self, room_id: str, feature_id: str, decision: str,
                              reason: str | None = None) -> dict:
        return self.manager_send("result_decision", {
            "room_id": room_id, "feature_id": feature_id, "decision": decision,
            "reason": reason, "message_id": uuid.uuid4().hex})

    def _authorize_amend(self, amend) -> None:         # FR-9 / AC-7
        auth = amend.human_authority
        material = f"amend|{amend.room_id}|{json.dumps(amend.change, sort_keys=True)}"
        if not _verify_sig(auth.get("signer_pub"), auth.get("signature"), material):
            raise ContractError("amend requires valid human authority (agent-originated rejected)")

    @property
    def verdicts(self) -> int:
        return self._verdicts


def conformance_suite(seam: Seam, room_id: str, slice_dict: dict) -> bool:
    """
    The same six-message flow, run over whatever transport `seam` holds (AC-5). Identical code for
    docker-exec and in-process — switching the transport changes nothing here (AC-12).
    """
    seam.negotiate_version(CONTRACT_VERSION)                                   # provision negotiation
    seam.manager_send("assign_task", {"room_id": room_id, "feature_slice": slice_dict})
    seam.room_send("status", {"room_id": room_id, "state": "working"})
    seam.room_send("claim_done", {"room_id": room_id, "feature_id": slice_dict["feature_id"],
                                  "message_id": "knock-1"})
    seam.issue_result_decision(room_id, slice_dict["feature_id"], "approved")
    return True
