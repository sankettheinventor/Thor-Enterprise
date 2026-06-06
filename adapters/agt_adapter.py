"""
AGT adapter — the THOR-owned boundary around the policy engine (Module 2 §2.4 / FR-14).

THOR vocabulary it exposes (System Design §7.1, Leash PRD §6.1):
    load_policy(policy)             -> register a room's frozen Kind-B policy
    check_action(action) -> Verdict -> the pre-action decision (allow/deny/escalate)
    record_decision(decision)       -> (kept for API parity; the Leash's DecisionRecorder owns the log)
    is_component_healthy(name)      -> bool
    agent_identity(room_id)         -> str

⚠️ STRANGLER SEAM (decision 2026-06-06: keep Rule 5 — stub AGT until Module 12). Today
`check_action` evaluates THOR's OWN policy engine (`leash.policy.evaluate`). At Module 12, this
one method instead calls Microsoft AGT's Agent OS — and ONLY this file changes. The rest of THOR
already speaks THOR vocabulary and never sees AGT types.

This is the ONLY file (with gitea_adapter.py) allowed to import AGT (Rule 4). It does not import
AGT yet — `leash.policy` stands in for the engine until M12.
"""
from __future__ import annotations

import logging

from leash.policy import FrozenPolicy, Verdict, evaluate

log = logging.getLogger("thor.agt_adapter")

# THOR vocabulary alias — callers think in ThorVerdict; today it IS leash.policy.Verdict.
ThorVerdict = Verdict

# Per-room frozen policies (Kind B), loaded host-side; never handed into the room.
_POLICIES: dict[str, FrozenPolicy] = {}


def load_policy(policy: FrozenPolicy) -> dict:
    """Register a room's frozen policy (PRD §6.1 POST /policy/load)."""
    _POLICIES[policy.room_id] = policy
    return {"room_id": policy.room_id, "loaded": True, "policy_hash": policy.policy_hash}


def check_action(action: dict) -> Verdict:
    """
    Pre-action policy check (P3). Looks up the room's frozen policy and evaluates the action.
    Fail-closed: a room with NO loaded policy is forbidden — deny (PRD §10 "policy won't load").
    """
    room_id = action.get("room_id")
    policy = _POLICIES.get(room_id)
    if policy is None:
        log.warning("no policy loaded for room %s -> fail-closed deny", room_id)
        return Verdict("deny", f"no policy loaded for room {room_id} (fail-closed)", "denied")
    verdict = evaluate(policy, action)
    log.info("decision room=%s target=%s -> %s (%s)",
             room_id, action.get("target"), verdict.decision, verdict.classification)
    return verdict


def record_decision(decision: dict) -> None:
    # The Leash's DecisionRecorder writes the signed EventLog; this stays for API parity.
    log.info("AGT adapter record: %s", decision)


def is_component_healthy(name: str) -> bool:
    return True  # stub: the real Sentinel/SRE substrate lands with Module 3 / M12


def agent_identity(room_id: str) -> str:
    # Identity is handled by wall.identity_stamper (local Ed25519). Real AGT Mesh: M12.
    return f"stub-identity:{room_id}"
