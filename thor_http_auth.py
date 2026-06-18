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


def require_role(min_role: str):
    """Build a FastAPI dependency that enforces a per-user ROLE on a mutating endpoint.

    Three postures, by configuration:
      * RBAC on  (THOR_USERS set): resolve the bearer token to a user; 401 if no user matches, 403 if the
        user's role rank is below `min_role`. Returns the user dict (so handlers can audit WHO acted).
      * single-token (THOR_API_TOKEN set, no THOR_USERS): the legacy posture — a valid token is full access
        (treated as commander). 401 if the token is missing/invalid.
      * open (neither set): dev/test/CI — no gate (so `make qa`/`make prove`, which send no token, pass).
    The transport role is the COARSE gate; minting a merge still needs a COMMANDER Ed25519 signature that no
    token can produce (authority is enforced separately in the Manager)."""
    import rbac

    def _dep(authorization: str | None = Header(default=None)):
        if rbac.rbac_enabled():
            user = rbac.user_for_token(authorization)
            if user is None:
                raise HTTPException(status_code=401, detail="missing or invalid API token")
            if not rbac.role_at_least(user["role"], min_role):
                raise HTTPException(status_code=403,
                                    detail=f"role '{user['role']}' may not perform this action "
                                           f"(requires {min_role})")
            return user
        if not is_authorized(authorization):       # legacy single-token / open posture
            raise HTTPException(status_code=401, detail="missing or invalid API token")
        return None

    return _dep
