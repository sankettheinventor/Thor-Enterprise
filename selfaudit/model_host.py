"""
Sub-module 11.2 — Local Model Host + the Toras-ready inspection seam (FR-13 / AC-12).

`InspectionModel` is the clean observe → assess → emit interface. v1 is a DETERMINISTIC analyzer
(zero token cost — makes ZERO frontier calls, AC-1). v2 (Toras) plugs a real local Qwen here behind
the SAME interface, evolving observe→report into observe→understand→correct — an evolution in place,
not a rebuild. `frontier_calls` is the proof of zero token cost: it must stay 0.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class InspectionModel(ABC):
    """The Toras-ready seam: read observations → assess correctness → emit findings."""

    frontier_calls: int = 0   # MUST remain 0 — no frontier-model API is ever called (zero token cost)

    @abstractmethod
    def assess(self, observations: dict) -> list[dict]:
        """Return a list of findings: {pattern, severity, occurrences, ...}."""


class DeterministicInspector(InspectionModel):
    """
    v1 stand-in for the local Qwen model: zero-cost statistical anomaly detection over observations.
    Focused (not chatty) correctness questions — failure-rate anomalies, divergence trends, escalation
    patterns — so findings are useful, not noise (D1). Makes no model calls at all.
    """

    def assess(self, obs: dict) -> list[dict]:
        findings: list[dict] = []
        verdicts = max(obs.get("verdict_total", 0), 1)

        div_rate = obs.get("divergence", 0) / verdicts
        if div_rate >= 0.3:
            findings.append({"pattern": "claim-vs-reality divergence rate is high",
                             "severity": "high", "occurrences": obs.get("divergence", 0),
                             "signal": "divergence_rate", "value": round(div_rate, 2)})

        esc_rate = obs.get("verdict_escalate", 0) / verdicts
        if esc_rate >= 0.4:
            findings.append({"pattern": "verdicts escalating suspiciously often",
                             "severity": "high", "occurrences": obs.get("verdict_escalate", 0),
                             "signal": "verdict_escalation_rate", "value": round(esc_rate, 2)})

        if obs.get("qa_findings", 0) >= 5:
            findings.append({"pattern": "QA failures clustering (possible correctness drift)",
                             "severity": "medium", "occurrences": obs.get("qa_findings", 0),
                             "signal": "qa_failure_count", "value": obs.get("qa_findings", 0)})
        return findings
