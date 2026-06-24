"""
GDPR Art.17 'right to erasure' for THOR's append-only, hash-chained ledger.

The ledger is immutable + hash-chained: deleting a row would break `verify_chain` and destroy the
tamper-evidence the whole system rests on. The correct pattern for an immutable audit ledger is
**auditable tombstone + redaction-at-read** (and, for stored plaintext PII, crypto-shredding):

  1. An erasure REQUEST is itself recorded as a hash-chained `subject.erasure` event — so honoring a
     deletion is provable and itself audited (who erased whom, when). This is required to demonstrate
     compliance.
  2. The subject's personal identifiers are REDACTED from everything the plane SERVES (audit feed/export,
     cockpit) — while the raw rows and their hashes are untouched, so the chain still verifies.
  3. Mutable personal state (the RBAC user registration: pubkey -> role) is actually DELETED.

What is 'personal data' in THOR is small and mostly pseudonymous: operator Ed25519 **public keys** and any
free-text a human typed into a feature's title/context. Secrets (tokens) live in env only, never the ledger.

CRYPTO-SHRED upgrade (for deployments that store real PII — names/emails — in event payloads): encrypt
those fields per-subject at WRITE time and destroy the subject's key on erasure, making the ciphertext
unrecoverable while the chain (computed over ciphertext) stays intact. Redaction-at-read below is the
baseline that always applies; crypto-shred is the stronger guarantee when plaintext PII is unavoidable.

Note (GDPR Art.17(3)): an audit/security log kept for a legal obligation or to establish/exercise legal
claims may be exempt from erasure; THOR redacts the *subject identifiers* while preserving the *fact* of
the governance events, which is the defensible middle path for a security-audit ledger.
"""
from __future__ import annotations

import json

ERASURE_EVENT = "subject.erasure"
_MASK = "[erased]"


def request_erasure(manager, subject_id: str, requested_by: str = "operator") -> int:
    """Honor an erasure request for a data subject (an operator pubkey or a user_id). Records the auditable
    tombstone AND removes the subject from mutable RBAC state. Ledger reads are redacted thereafter."""
    if not subject_id:
        raise ValueError("subject_id is required")
    seq = manager._record(ERASURE_EVENT, {"subject": subject_id, "requested_by": requested_by})
    # delete the mutable personal state (registration) — these are not ledger rows, so they CAN be removed
    roles = getattr(manager, "user_roles", None)
    if isinstance(roles, dict):
        roles.pop(subject_id, None)
    signers = getattr(manager, "authorized_signers", None)
    try:
        if subject_id in signers:                  # set or dict of registered signer keys
            signers.discard(subject_id) if hasattr(signers, "discard") else signers.pop(subject_id, None)
    except TypeError:
        pass
    return seq


def erased_subjects(events: list[dict]) -> set[str]:
    """The set of subject identifiers erased so far, read from the ledger's `subject.erasure` tombstones."""
    out: set[str] = set()
    for e in events:
        if e.get("event_type") != ERASURE_EVENT:
            continue
        p = e.get("payload")
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except (ValueError, TypeError):
                p = {}
        s = (p or {}).get("subject")
        if s:
            out.add(s)
    return out


def _redact(obj, erased: set[str]):
    if isinstance(obj, str):
        for sub in erased:
            if sub and sub in obj:
                obj = obj.replace(sub, _MASK)
        return obj
    if isinstance(obj, dict):
        return {k: _redact(v, erased) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v, erased) for v in obj]
    return obj


def redact_events(events: list[dict]) -> list[dict]:
    """Mask every erased subject's identifiers in a list of events — for ANYTHING served to a client.
    Pure + non-mutating: the raw ledger rows (and the chain over them) are never touched."""
    erased = erased_subjects(events)
    if not erased:
        return events
    return [_redact(e, erased) for e in events]
