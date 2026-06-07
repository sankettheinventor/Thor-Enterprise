"""
MCP Security Gateway (sub-module from FR-17/FR-18) — tool-definition scanning + kill-switch path.

Phase 2b scope: scan a tool definition for hidden-instruction / prompt-injection / typosquat
signals; on a max-severity finding, the Leash triggers the kill-switch (terminate the room) via
the Lifecycle Controller (FR-18). Real AGT MCP Security Gateway plugs in at Module 12.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Crude but real signals of a poisoned tool description (prompt-injection / hidden instructions).
_INJECTION_PATTERNS = (
    r"ignore (all|previous) instructions",
    r"disregard .* (rules|policy)",
    r"exfiltrate|leak .* (key|secret|token)",
    r"do not tell|without telling the (user|operator)",
)
# Zero-width / bidi characters often used to HIDE instructions in a description.
_HIDDEN_CHARS = re.compile(r"[​‌‍\u202E\u2066-\u2069]")


@dataclass
class ScanResult:
    safe: bool
    findings: list[dict]


def scan_tool(tool_definition: dict) -> ScanResult:
    """Return safe=False with findings if the tool looks malicious (FR-17)."""
    text = f"{tool_definition.get('name', '')} {tool_definition.get('description', '')}".lower()
    findings: list[dict] = []
    for pat in _INJECTION_PATTERNS:
        if re.search(pat, text):
            findings.append({"type": "hidden_instruction", "detail": f"matched: {pat}"})
    if _HIDDEN_CHARS.search(tool_definition.get("description", "")):
        findings.append({"type": "hidden_instruction", "detail": "hidden/bidi control characters"})
    return ScanResult(safe=not findings, findings=findings)


def enforce(tool_definition: dict, room_id: str, lifecycle, recorder=None) -> dict:
    """
    Scan a tool; on a max-severity finding trigger the kill-switch (terminate the room — FR-18).
    Returns the action taken. `lifecycle` is a wall.lifecycle.LifecycleController.
    """
    result = scan_tool(tool_definition)
    if result.safe:
        return {"room_id": room_id, "action": "allow", "findings": []}
    if recorder is not None:
        recorder.record_event(   # H7: through the Manager (single ledger), not a local chain
            "sentinel.kill", {"room_id": room_id, "reason": "malicious tool", "findings": result.findings},
            room_id=room_id,
        )
    lifecycle.destroy(room_id)  # max-severity: terminate, quarantine (PRD §8.5)
    return {"room_id": room_id, "action": "killed", "findings": result.findings}
