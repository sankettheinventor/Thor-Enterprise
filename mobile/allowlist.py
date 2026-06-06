"""
Sub-module 9.5 — Command Allowlist (FR-4 / FR-11). The phone may do exactly a bounded set of things:
direct, observe, sign. Anything else — reach into a room, change rules, bypass governance, arbitrary
commands — is rejected. The most-exposed device carries the least catastrophic risk.
"""
from __future__ import annotations

ALLOWED = frozenset({"approve", "reject", "mark_ready", "add_feature", "prioritize", "view"})


def allowed(command: str) -> bool:
    return command in ALLOWED
