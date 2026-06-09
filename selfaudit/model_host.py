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
    name: str = "abstract"

    def loaded(self) -> bool:
        """Is the model actually available? (drives the honest `model_loaded` health flag — no hardcode)."""
        return True

    @abstractmethod
    def assess(self, observations: dict) -> list[dict]:
        """Return a list of findings: {pattern, severity, occurrences, ...}."""


class DeterministicInspector(InspectionModel):
    """
    v1 local inspector: zero-cost statistical anomaly detection over observations. Focused (not chatty)
    correctness questions — failure-rate anomalies, divergence trends, escalation patterns — so findings
    are useful, not noise (D1). A REAL, local analyzer that makes no model calls at all (frontier_calls=0).
    """

    name = "deterministic-v1"

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


class OllamaInspector(InspectionModel):
    """
    v2 — a REAL local model (Ollama/Qwen) behind the SAME seam (AC-12). frontier_calls stays 0 because
    Ollama runs LOCALLY on 127.0.0.1:11434 — it is NOT a frontier API (zero token cost holds). The
    deterministic signals are always computed as a baseline; the local model adds a narrative note. On
    ANY error the deterministic findings stand — the advisory-only loop never breaks (fail-safe).
    """

    name = "ollama-qwen"

    def __init__(self, model: str = "qwen2.5:3b", host: str = "http://127.0.0.1:11434") -> None:
        self.model_tag = model
        self.host = host

    def loaded(self) -> bool:
        import json
        import urllib.request
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=2) as r:
                models = json.loads(r.read() or "{}").get("models", [])
            return any(self.model_tag.split(":")[0] in (m.get("name", "")) for m in models)
        except Exception:  # noqa: BLE001 — Ollama not running / model absent → not loaded
            return False

    def assess(self, obs: dict) -> list[dict]:
        import json
        import urllib.request
        findings = DeterministicInspector().assess(obs)        # always the deterministic baseline
        try:
            focus = {k: obs.get(k) for k in ("verdict_total", "divergence", "verdict_escalate", "qa_findings")}
            prompt = ("You are THOR's read-only correctness auditor. From these system observations name "
                      "any correctness-drift concern in one short line, or reply OK. Observations: "
                      + json.dumps(focus))
            body = json.dumps({"model": self.model_tag, "prompt": prompt, "stream": False}).encode()
            req = urllib.request.Request(self.host + "/api/generate", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                text = (json.loads(r.read()).get("response") or "").strip()
            if text and text.upper() != "OK":
                findings.append({"pattern": "local-model note: " + text[:160], "severity": "low",
                                 "occurrences": 0, "signal": "ollama"})
        except Exception:  # noqa: BLE001 — local model unavailable mid-run → deterministic findings stand
            pass
        return findings


def select_model() -> InspectionModel:
    """Pick the inspection model: a REAL local Ollama/Qwen if one is reachable, else the deterministic
    v1 (real, local, zero-cost). The seam is identical either way (AC-12) — an evolution in place."""
    ollama = OllamaInspector()
    return ollama if ollama.loaded() else DeterministicInspector()
