"""
Sub-module 8.7 — Cost & Budget Panel (FR-10 / AC-7).

Per-feature and total token spend, the active budget cap, and an alert when a cap is approached.
Because tokens are the dominant cost (Bible §12), the accountable human must see spend, not just
correctness. Dry-run cost previews come from the Scheduler (Module 4) — zero provisioning.
"""
from __future__ import annotations

ALERT_FRACTION = 0.8   # warn when spend reaches 80% of the cap


def report(features: list[dict], spent_by_feature: dict[str, int], cap: int | None) -> dict:
    per_feature = []
    total_est = total_spent = 0
    for f in features:
        est = f.get("est_tokens", 0) or 0
        spent = spent_by_feature.get(f["feature_id"], 0)
        total_est += est
        total_spent += spent
        per_feature.append({"feature_id": f["feature_id"], "est_tokens": est, "spent": spent})
    alert = bool(cap and total_spent >= ALERT_FRACTION * cap)
    over = bool(cap and total_spent > cap)
    return {"per_feature": per_feature, "total_est": total_est, "total_spent": total_spent,
            "cap": cap, "alert": alert, "over_cap": over}
