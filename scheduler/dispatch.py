"""
Sub-module 4.5 (live) — the Provision Dispatcher wire (Integration PRD seam S2).

The Scheduler decides WHICH ready features run (deterministic, zero-LLM). This is the wire it
dispatches THROUGH: for each ready feature it consults the PM admission gate, asks the CTO to plan
(the ONE planning call — skills + plan-owned scope), then the Manager provisions a real sealed
room. The Scheduler never provisions directly and never calls an LLM (FR-8/FR-1).

A no-spec feature is REFUSED here (PM gate) and NO room is provisioned for it — PM enforcement is
real at the dispatch boundary, not advisory.
"""
from __future__ import annotations

from pm import gate
from scheduler import cto_stub


def make_dispatcher(manager, catalog: dict, on_event=None):
    """
    Build the `dispatch_fn(feature_id, task_type)` the Scheduler calls per ready feature.

    `catalog` maps feature_id -> the feature dict (carries acceptance_criteria + scope_files).
    Refused (no-spec) features provision NOTHING. Returns the dispatcher; its `.log` lists every
    decision (dispatched/refused) so the caller can assert deterministic, audited behaviour.
    """
    log: list[dict] = []

    def dispatch(feature_id: str, task_type: str = "build") -> dict:
        feature = catalog.get(feature_id, {"feature_id": feature_id})
        verdict = gate.admit(feature)
        if not verdict["admitted"]:
            rec = {"feature_id": feature_id, "dispatched": False, "refused": True,
                   "reason": verdict["reason"]}
            log.append(rec)
            if on_event:
                on_event(rec)
            return rec
        plan = cto_stub.plan_task(feature_id, task_type, feature=feature)  # the ONE planning call
        room = manager.provision_room(feature_id, task_type=task_type)
        rec = {"feature_id": feature_id, "dispatched": True, "refused": False,
               "room_id": room["room_id"], "skills": plan["skills"], "_room": room}
        log.append(rec)
        if on_event:
            on_event(rec)
        return rec

    dispatch.log = log  # type: ignore[attr-defined]
    return dispatch
