"""
Sub-module 12.2 — Compliance Mapper (FR-4 / FR-16 / AC-3).

Maps THOR's already-generated audit events to named regulatory frameworks and exports evidence
DERIVED from the tamper-evident chain (not reconstructed) — so "here is the SOC2 report" is a cheap
export, traceable to real chain entries. In production these mappings come from AGT Agent Compliance;
here a faithful representative mapping demonstrates the export + chain-traceability.
"""
from __future__ import annotations

import csv
import io

# event_type -> the controls it provides evidence for, per framework
_MAP: dict[str, dict[str, str]] = {
    "card.approved":      {"SOC2": "CC8.1 change authorization", "EU_AI_ACT": "Art.14 human oversight",
                           "NIST": "AC-6 least privilege", "HIPAA": "164.312(a) access control"},
    "feature.merged":     {"SOC2": "CC8.1 change management", "EU_AI_ACT": "Art.12 record-keeping",
                           "NIST": "CM-3 change control"},
    "verdict.computed":   {"SOC2": "CC7.2 monitoring", "EU_AI_ACT": "Art.15 accuracy/robustness",
                           "OWASP": "A09 logging"},
    "divergence.detected": {"SOC2": "CC7.3 anomaly detection", "EU_AI_ACT": "Art.15 robustness"},
    "sentinel.halt":      {"SOC2": "CC7.4 incident response", "NIST": "IR-4 incident handling"},
    "leash.denied":       {"OWASP": "A01 broken access control", "NIST": "AC-3 access enforcement"},
}

FRAMEWORKS = ("SOC2", "EU_AI_ACT", "HIPAA", "NIST", "OWASP")


def export(events: list[dict], framework: str, fmt: str = "json"):
    fw = framework.upper().replace(" ", "_")
    rows = []
    for e in events:
        control = _MAP.get(e["event_type"], {}).get(fw)
        if control:
            rows.append({"seq": e["seq"], "chain_hash": e["hash"], "event_type": e["event_type"],
                         "framework": fw, "control": control})
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["seq", "chain_hash", "event_type", "framework", "control"])
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()
    return {"framework": fw, "evidence": rows, "derived_from": "tamper-evident chain", "count": len(rows)}
