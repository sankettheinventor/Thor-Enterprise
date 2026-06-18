"""
RBAC — multiple users on one host, three roles (the single-commander residual, closed).

THOR keeps authN and authZ separate (security invariant #2), and RBAC extends BOTH layers without blurring
them:

  * TRANSPORT (authN + coarse authZ): each user carries a per-user API token. The token proves WHO is
    calling and gates the mutating surface by ROLE — a Viewer cannot mutate, an Operator can run the build
    flow but cannot approve a merge. Enforced at the HTTP edge (`thor_http_auth.require_role`).
  * AUTHORITY (the real authZ): a merge is still minted ONLY by an Ed25519 signature, and now ONLY a
    COMMANDER's registered key may sign one. A token — any token, even a Commander's — can NEVER mint a
    merge; that takes the offline signing key. Enforced in the Manager (`authorized_signers` = commanders).

Roles (rank-ordered; higher includes lower):
  viewer    — read-only (dashboards, audit, health).
  operator  — viewer + run the SDLC flow: queue/stop features, run commands, prioritise/assign.
  commander — operator + the authority surface: approve/reject cards (sign merges), register users.

Config (env-driven, like THOR_API_TOKEN): THOR_USERS is a JSON array of
  [{"id": "...", "role": "viewer|operator|commander", "token": "...", "pubkey": "<ed25519 b64, optional>"}]
Tokens are secrets and live in the environment only, never in source (invariant #1). When THOR_USERS is
unset the per-user layer is OFF and the legacy single-token posture (THOR_API_TOKEN) applies — so dev/test
and `make qa`/`make prove` (which send no token) keep passing unchanged.
"""
from __future__ import annotations

import hmac
import json
import os

VIEWER, OPERATOR, COMMANDER = "viewer", "operator", "commander"
ROLE_RANK = {VIEWER: 1, OPERATOR: 2, COMMANDER: 3}


def _valid_role(role: str) -> bool:
    return role in ROLE_RANK


def load_users() -> list[dict]:
    """Parse THOR_USERS (JSON). Returns [] when unset/empty/malformed — the caller then falls back to the
    legacy single-token posture. Re-read each call so a deployment (or a test) can change the roster live.
    A user with an unknown role is dropped (fail-closed: an unparseable role grants nothing)."""
    raw = os.environ.get("THOR_USERS", "").strip()
    if not raw:
        return []
    try:
        users = json.loads(raw)
    except (ValueError, TypeError):
        return []
    out = []
    for u in users if isinstance(users, list) else []:
        if isinstance(u, dict) and u.get("id") and _valid_role(u.get("role", "")) and u.get("token"):
            out.append({"id": u["id"], "role": u["role"], "token": u["token"], "pubkey": u.get("pubkey", "")})
    return out


def rbac_enabled() -> bool:
    return bool(load_users())


def user_for_token(authorization: str | None) -> dict | None:
    """Resolve an `Authorization: Bearer <token>` header to its user, or None. Constant-time compare against
    every user's token (no early return) so response timing cannot reveal which user a guessed token nearly
    matched (AUD-token-timing)."""
    provided = authorization or ""
    match = None
    for u in load_users():
        if hmac.compare_digest(provided, f"Bearer {u['token']}"):
            match = u            # keep scanning all users — uniform work regardless of match position
    return match


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(minimum, 99)
