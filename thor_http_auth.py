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

import hmac
import os
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

# Per-client sliding-window rate limit on the mutating surface — bounds brute-force, credential-stuffing,
# and abuse (a real attacker makes far more than a human/CI). Generous default so humans + tests never trip
# it; tune with THOR_RL_MAX (requests) / THOR_RL_WINDOW (seconds); THOR_RL_MAX<=0 disables it.
_RL_MAX = int(os.environ.get("THOR_RL_MAX", "240"))
_RL_WINDOW = float(os.environ.get("THOR_RL_WINDOW", "60"))
_rl_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """FastAPI dependency for mutating endpoints: 429 when a client exceeds the window budget."""
    rl_max = int(os.environ.get("THOR_RL_MAX", _RL_MAX))
    if rl_max <= 0:
        return
    window = float(os.environ.get("THOR_RL_WINDOW", _RL_WINDOW))
    client = request.client.host if request.client else "unknown"
    now = time.time()
    q = _rl_hits[client]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= rl_max:
        raise HTTPException(status_code=429, detail="rate limit exceeded — slow down")
    q.append(now)


def token_required() -> bool:
    """True iff a token is configured (i.e. auth is enforced)."""
    return bool(os.environ.get("THOR_API_TOKEN"))


def is_authorized(authorization: str | None) -> bool:
    """Pure check: authorized iff auth is disabled, or the header carries the exact bearer token."""
    expected = os.environ.get("THOR_API_TOKEN")
    if not expected:
        return True                       # no token configured → auth disabled (dev/test)
    # constant-time compare — never leak the token a byte at a time via response timing (AUD-token-timing)
    return hmac.compare_digest(authorization or "", f"Bearer {expected}")


def require_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency for mutating endpoints: 401 unless authorized."""
    if not is_authorized(authorization):
        raise HTTPException(status_code=401, detail="missing or invalid API token")
