"""
Sub-module 10.5 — Canary Engine (FR-5 / AC-2). The efficacy moat of meta-governance.

Fires PLANTED must-fail actions at the REAL detectors and checks they still catch them:
  - leash canary: an out-of-scope write that the Leash policy MUST deny. If it's allowed → the
    detector is broken → alarm + halt.
  - engine canary: the deliberately-incomplete feature that the GovernanceEngine MUST verdict
    not_done (shared with Module 6's canary invariant).

A passing canary means a broken detector, not a flaky test. This is the only way to KNOW a detector
still detects rather than assuming it does.
"""
from __future__ import annotations

from leash.policy import FrozenPolicy, evaluate


def leash_canary(policy: FrozenPolicy) -> dict:
    """A planted out-of-scope write that MUST be denied. `healthy` iff the Leash denies it."""
    action = {"type": "tool_call", "name": "write_file",
              "target": "infra/secrets.tf", "room_id": "canary"}
    verdict = evaluate(policy, action)
    healthy = verdict.decision != "allow"        # must be denied/escalated; allow = broken detector
    return {"name": "leash-deny-out-of-scope", "expected": "deny",
            "result": verdict.decision, "healthy": healthy}


def engine_canary(engine, canary_ctx) -> dict:
    """The deliberately-incomplete feature that MUST verdict not_done (reuses M6's canary)."""
    status = engine.canary_status(canary_ctx)
    return {"name": "engine-must-not-done", "expected": "not_done",
            "result": status["actual"], "healthy": status["healthy"]}
