"""
Sub-module 2.6 — Credential Injector.

Holds destination credentials (LLM API keys, Gitea tokens) and injects them ONLY into approved,
allowed outbound requests — NEVER into the room (FR-12, AC-6 / P4 capability separation).

⚠️ Phase 2b: this is interface-only today. Real credential injection is meaningful only once the
one-door egress path exists (Phase 2b) and there are real outbound destinations (model API, Gitea
at M12). The point recorded here for the build: creds live in the adapter/control-plane and are
injected outbound per-destination — they are never mounted or env-injected into the container.
"""
from __future__ import annotations


class CredentialInjector:
    def __init__(self) -> None:
        # In Phase 2b this loads from the control-plane credential store ([OPEN D1] backend).
        self._store: dict[str, str] = {}

    def inject(self, destination: str, request_headers: dict) -> dict:
        """Add creds for an APPROVED destination only; refuse unknown destinations (no leak)."""
        cred = self._store.get(destination)
        if cred is None:
            # No creds for an unapproved destination → return headers untouched (request will fail
            # upstream rather than leak anything). Logged as a refused-injection in Phase 2b.
            return request_headers
        return {**request_headers, "Authorization": f"Bearer {cred}"}
