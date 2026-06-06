"""
Sub-module 12.1 — Audit Trail Adapter (the AGT-audit seam) + 12.2 Compliance via `compliance.py`.

Exposes THOR vocabulary (append_event / verify_chain / export_compliance) over a tamper-evident,
Ed25519-signed, hash-chained substrate. The Manager (M3) is the SOLE writer (FR-3); this adapter is
the THOR-owned boundary around the chain. Today the backend IS THOR's own M3 hash-chain — which is
exactly the Merkle/HMAC tamper-evidence AGT provides; swapping in real AGT changes only this file.
"""
from __future__ import annotations

from manager.eventlog import EventLogWriter

from . import compliance
from .contract import AuditPort


class ChainAudit(AuditPort):
    """AuditPort backed by the real M3 EventLog chain (the AGT Merkle/HMAC backend slot)."""

    def __init__(self, writer: EventLogWriter) -> None:
        self._writer = writer

    def append_event(self, event_type: str, payload: dict, **kw) -> dict:
        # only the Manager's writer path reaches here — tamper-evidence + chaining underneath
        return self._writer.append(event_type, payload, **kw)

    def verify_chain(self) -> bool:
        return self._writer.verify_chain()

    def all_events(self) -> list[dict]:
        return self._writer.all_events()


def verify_chain(audit: AuditPort) -> dict:
    """Re-verify the whole chain; altering any past event makes this False (FR-2 / AC-2)."""
    return {"intact": audit.verify_chain()}


def export_compliance(audit: ChainAudit, framework: str, fmt: str = "json") -> dict | str:
    """Derive compliance evidence for a named framework FROM the tamper-evident chain (FR-4/16/AC-3)."""
    return compliance.export(audit.all_events(), framework, fmt)
