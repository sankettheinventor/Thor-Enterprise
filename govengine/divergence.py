"""
Sub-module 6.7 — Divergence Detector (the lie-detector, FR-6 / US-2).

Builds a reality manifest (what git+audit show actually happened) and compares it to the agent's
CLAIM (collected via Module 5's claim_done context, treated as untrusted). The gap is a measurable
honesty signal. Divergence flags FACTS (claimed X, git shows Y), not intent — material divergence
escalates to a human who judges intent (D1).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Divergence:
    found: bool = False
    signals: list[str] = field(default_factory=list)


def detect(claim: dict, changed_files: set[str], verifier_passed: bool,
           gate_hits: int) -> Divergence:
    """`claim` is the agent's untrusted self-report: {files_touched:[...], tests_passed:bool}."""
    d = Divergence()
    if not claim:
        return d   # no claim to compare — divergence only flags contradicted claims

    claimed = set(claim.get("files_touched", []))

    # claimed-but-absent: said it changed a file git shows untouched → fabrication
    for f in sorted(claimed - changed_files):
        d.signals.append(f"claimed to modify {f!r} but git shows it untouched (fabrication)")

    # undisclosed: git changed files the agent didn't claim
    for f in sorted(changed_files - claimed):
        if claimed:   # only meaningful if the agent made a files claim
            d.signals.append(f"undisclosed change to {f!r} (not in the agent's claim)")

    # claimed tests passed but the verifier (reality) disagrees → fabrication
    if claim.get("tests_passed") and not verifier_passed:
        d.signals.append("claimed tests passed, but the verifier failed (fabrication)")

    # claimed done while gaming the gate during the work
    if gate_hits:
        d.signals.append(f"claimed done but {gate_hits} gate-gaming hit(s) in the work window")

    d.found = bool(d.signals)
    return d
