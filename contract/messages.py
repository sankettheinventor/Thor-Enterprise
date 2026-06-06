"""
Sub-module 5.1 Message Schema + 5.5 Message Validator.

The single source of truth for what may cross the seam: EXACTLY six messages (FR-1), each a
Pydantic model with `extra="forbid"` so any undefined field (incl. a credential or a self-verdict)
is rejected (FR-2/FR-14). Directions are fixed (FR-1): a room cannot send a Manager→room message
(this is part of why P5 holds — a room cannot issue `result_decision`).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

CONTRACT_VERSION = "1.0"

# The constitution: exactly these six, no others (FR-1).
MESSAGE_TYPES = frozenset(
    {"provision", "assign_task", "amend", "status", "claim_done", "result_decision"}
)
MANAGER_TO_ROOM = frozenset({"provision", "assign_task", "amend", "result_decision"})
ROOM_TO_MANAGER = frozenset({"status", "claim_done"})


class MessageError(ValueError):
    """Raised when a message is malformed or out-of-contract (rejected, not coerced — FR-2)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")   # no undefined fields cross the seam (FR-2/14)


class FeatureSlice(_Strict):
    """The room's complete and only task source — one feature, read-only (FR-5/FR-16)."""
    feature_id: str
    task_type: str
    context: str = ""
    goals: list[str] = []
    non_goals: list[str] = []
    contract: dict = {}            # { acceptance_criteria: [...] }
    scope: dict = {}               # { files: [...] }
    capability_tags: list[str] = []


class Provision(_Strict):
    room_id: str
    task_type: str
    skills: list[str] = []
    scope: dict = {}
    repo: str | None = None
    base_branch: str = "main"
    limits: dict = {}
    contract_version: str


class AssignTask(_Strict):
    room_id: str
    feature_slice: FeatureSlice


class Amend(_Strict):
    room_id: str
    change: dict
    human_authority: dict          # { signer_pub, signature } — verified by the Amend Handler (FR-9)


class Status(_Strict):
    room_id: str
    state: Literal["provisioning", "working", "claims_done", "failed", "blocked"]
    detail: str | None = None


class ClaimDone(_Strict):
    # A KNOCK, not a verdict (FR-6 / P5). NOTE: there is deliberately NO `done`/`verdict`/`result`
    # field here — the protocol gives a room no way to certify itself. That is AC-4, structurally.
    room_id: str
    feature_id: str
    message_id: str


class ResultDecision(_Strict):
    room_id: str
    feature_id: str
    decision: Literal["approved", "rejected"]
    reason: str | None = None
    message_id: str


MODEL_FOR: dict[str, type[_Strict]] = {
    "provision": Provision, "assign_task": AssignTask, "amend": Amend,
    "status": Status, "claim_done": ClaimDone, "result_decision": ResultDecision,
}


def validate(msg_type: str, payload: dict):
    """Validate a message against the schema; raise MessageError on anything out-of-contract."""
    if msg_type not in MODEL_FOR:
        raise MessageError(f"out-of-contract message type: {msg_type!r} (only the six are allowed)")
    try:
        return MODEL_FOR[msg_type](**payload)
    except ValidationError as e:
        raise MessageError(f"malformed {msg_type}: {e}") from e
