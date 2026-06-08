"""
PM — the plan's admission gate (the role model: PM owns the plan / scope / SDLC rules).

A feature is ADMITTED for build only if it is spec-complete: it declares a testable spec
(acceptance criteria) AND a non-empty scope (an area the cook may touch). A no-spec / no-scope
feature is REFUSED — the cook can do nothing without a plan. This is the Enterprise form of the
original PM's "no drive-by edits on a feature that belongs to no declared scope" rule, applied at
dispatch (fail-closed): an unplanned feature never reaches a room.
"""
from __future__ import annotations


def admit(feature: dict) -> dict:
    """Return {admitted, feature_id, reason}. Refuse a feature with no acceptance criteria or no scope."""
    reasons = []
    if not (feature.get("acceptance_criteria") or []):
        reasons.append("no acceptance criteria (no testable spec)")
    if not (feature.get("scope_files") or []):
        reasons.append("no declared scope (nothing the cook may touch)")
    return {
        "admitted": not reasons,
        "feature_id": feature.get("feature_id"),
        "reason": "spec-complete" if not reasons else "; ".join(reasons),
    }
