"""
Sub-module 11.6 — URGENT Escalator (FR-7/FR-8 / AC-4/AC-7). The ONLY path by which this read-only
observer influences enforcement — and it never enforces itself.

For HIGH-severity findings it raises URGENT to the Sentinel; the Sentinel decides whether to halt.
A Self-Audit false positive costs at most a Sentinel evaluation, never a wrongful halt — the cheap,
fallible model must never hold a stop button (the safety boundary). Only high-severity findings
escalate (calibration, D2); everything else is just a DB report.
"""
from __future__ import annotations


def maybe_escalate(findings: list[dict], sentinel) -> list[dict]:
    out = []
    for f in findings:
        if f.get("severity") == "high":
            # the cheap model only FLAGS — it does not confirm criticality; the Sentinel decides.
            decision = sentinel.receive_urgent(
                {"detail": f["pattern"], "scope": "system",
                 "confirmed_critical": False, "source": "self-audit"})
            out.append({"finding": f["pattern"], "sentinel_decision": decision["decision"]})
    return out
