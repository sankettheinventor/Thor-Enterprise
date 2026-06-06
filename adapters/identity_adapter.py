"""
Sub-module 12.3 Identity Adapter (the AGT-Mesh seam) + 12.4 Signature Verifier.

THOR vocabulary over cryptographic identity: mint/verify room identities (Ed25519/DID) and verify
human signatures for the three signature points, bound to payload+nonce (anti-replay, P6). Today the
backend is the real M1 IdentityStamper + Ed25519; real AGT Agent Mesh swaps in behind this file.

Identity is for VERIFICATION + system-trust ONLY — never per-agent trust-scoring (FR-7/AC-12,
Bible §11.4). There is deliberately no scoring API here.
"""
from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wall.identity_stamper import IdentityStamper, _unb64

from .contract import IdentityPort

_REVOKED: set[str] = set()   # revoked room/device identities (e.g. a lost mobile, M9)


class MeshIdentity(IdentityPort):
    def __init__(self, stamper: IdentityStamper | None = None) -> None:
        self.stamper = stamper or IdentityStamper()

    def mint_room_identity(self, room_id: str, task_type: str = "build") -> dict:
        return {"identity_token": self.stamper.stamp(room_id, task_type), "room_id": room_id}

    def verify_identity(self, token: str, room_id: str | None = None) -> dict:
        # fail-closed: a revoked, forged, or stale token is NOT trusted (FR-13/AC-10)
        valid = token not in _REVOKED and self.stamper.verify(token, room_id)
        return {"valid": valid, "room_id": room_id}

    def verify_signature(self, public_key_b64: str, material: str, signature_b64: str) -> dict:
        """Verify a human signature bound to material (card+payload+nonce). Rejects replays/forgeries."""
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(public_key_b64)).verify(
                _unb64(signature_b64), material.encode())
            return {"valid": True, "signer": public_key_b64[:12]}
        except (InvalidSignature, ValueError):
            return {"valid": False, "signer": None}


def revoke_identity(identity: str) -> dict:
    _REVOKED.add(identity)
    return {"revoked": True, "identity": identity}
