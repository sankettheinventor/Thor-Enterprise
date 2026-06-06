"""
Sub-module 10.4 — Integrity Crawler (FR-4 / AC-4).

Hashes THOR's governance code/rules at boot and re-checks continuously for drift/tampering. Any
mismatch against the recorded baseline is a CRAWLER_ALARM — the rules can't be trusted, so halt and
make the operator re-verify before resuming.
"""
from __future__ import annotations

import hashlib


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class IntegrityCrawler:
    def __init__(self) -> None:
        self.baseline: dict[str, str] = {}

    def record_baseline(self, items: dict[str, bytes]) -> None:
        """Record the trusted hashes of governance code/rules at boot (the freeze)."""
        self.baseline = {k: _hash(v) for k, v in items.items()}

    def check(self, items: dict[str, bytes]) -> dict:
        """Re-hash and compare to the baseline. Returns the tampered keys (empty = intact)."""
        tampered = [k for k, v in items.items() if self.baseline.get(k) != _hash(v)]
        return {"ok": not tampered, "tampered": tampered}
