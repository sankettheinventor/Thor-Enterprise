"""
Sub-module 11.4 — Meta-Trust Scorer (FR-6 / AC-6). SYSTEM-trust, NOT agent-trust (Bible §11.4).

THOR rejects scoring agents (inherently inconsistent — a decaying number is meaningless). Instead it
scores THE SYSTEM's own reliability: how often the machinery fails to produce the required output, how
often verdicts escalate, how often components fail. A system SHOULD be consistent, so its failure rate
is a meaningful, actionable signal. No agent is ever scored.
"""
from __future__ import annotations


def score(obs: dict) -> dict:
    verdicts = max(obs.get("verdict_total", 0), 1)
    # SYSTEM-level signals only (no per-agent identity):
    signals = [
        {"signal": "required_output_miss_rate", "value": round(obs.get("not_done", 0) / verdicts, 3)},
        {"signal": "verdict_escalation_rate", "value": round(obs.get("verdict_escalate", 0) / verdicts, 3)},
        {"signal": "divergence_rate", "value": round(obs.get("divergence", 0) / verdicts, 3)},
        {"signal": "component_failure_count", "value": obs.get("alarms", 0)},
    ]
    # reliability = 1 - weighted failure signals (clamped to [0,1])
    penalty = (0.4 * signals[0]["value"] + 0.3 * signals[1]["value"] + 0.3 * signals[2]["value"]
               + 0.02 * signals[3]["value"])
    return {"score": round(max(0.0, 1.0 - penalty), 3), "trend": "flat",
            "contributing_signals": signals, "scope": "system"}
