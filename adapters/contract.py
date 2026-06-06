"""
Sub-module 12.7 — Adapter Contract & Versioning.

The formal THOR-vocabulary interfaces each adapter implements — the seam the Strangler strategy
depends on (FR-1/FR-11). THOR code calls ONLY these methods; no AGT or Gitea type ever crosses the
boundary. Each port is versioned so an external (AGT "Public Preview") upgrade is an adapter-local
change, never a THOR-wide one (FR-12). The Substitution Harness checks a backend satisfies its port.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

CONTRACT_VERSION = "1.0"


class GitPort(ABC):
    """The git/PR/CI backbone in THOR vocabulary (Gitea today; GitHub/local-git swappable)."""
    version = CONTRACT_VERSION

    @abstractmethod
    def open_pr(self, repo: str, branch: str, meta: dict) -> dict: ...
    @abstractmethod
    def ci_result(self, repo: str, branch: str) -> dict: ...
    @abstractmethod
    def merge(self, repo: str, pr_id: str, signature_ref: str | None, base: str = "main") -> dict: ...
    @abstractmethod
    def list_issues(self, repo: str) -> list[dict]: ...


class AuditPort(ABC):
    """The tamper-evident audit chain in THOR vocabulary (AGT Merkle/HMAC today; swappable)."""
    version = CONTRACT_VERSION

    @abstractmethod
    def append_event(self, event_type: str, payload: dict, **kw) -> dict: ...
    @abstractmethod
    def verify_chain(self) -> bool: ...


class IdentityPort(ABC):
    """Cryptographic identity + signature verification in THOR vocabulary (AGT Mesh today)."""
    version = CONTRACT_VERSION

    @abstractmethod
    def mint_room_identity(self, room_id: str, task_type: str) -> dict: ...
    @abstractmethod
    def verify_identity(self, token: str, room_id: str | None = None) -> dict: ...
    @abstractmethod
    def verify_signature(self, public_key_b64: str, material: str, signature_b64: str) -> dict: ...
