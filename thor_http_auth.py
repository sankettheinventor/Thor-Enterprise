"""
Shared bearer-token gate for the THOR HTTP surfaces (production hardening).

Posture: DISABLED when THOR_API_TOKEN is unset (dev / test / CI — `make prove`/`make qa` send no token
and keep passing). In PRODUCTION, set THOR_API_TOKEN (a strong random secret) and every MUTATING
endpoint then requires `Authorization: Bearer <token>`. Read-only/health endpoints stay open so k8s
liveness/readiness probes and dashboards keep working. Authority over signed actions is still the
Ed25519 signature; this is the TRANSPORT gate that stops an unauthenticated caller from reaching the
mutating surface at all.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException


def token_required() -> bool:
    """True iff a token is configured (i.e. auth is enforced)."""
    return bool(os.environ.get("THOR_API_TOKEN"))


def is_authorized(authorization: str | None) -> bool:
    """Pure check: authorized iff auth is disabled, or the header carries the exact bearer token."""
    expected = os.environ.get("THOR_API_TOKEN")
    if not expected:
        return True                       # no token configured → auth disabled (dev/test)
    return authorization == f"Bearer {expected}"


def require_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency for mutating endpoints: 401 unless authorized."""
    if not is_authorized(authorization):
        raise HTTPException(status_code=401, detail="missing or invalid API token")
