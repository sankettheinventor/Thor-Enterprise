"""
Sub-module 1.6 — Identity Stamper.

Stamps each room with a verifiable identity token so ThorManager can confirm a room belongs
to THIS THOR instance before trusting it (FR-10, AC-10). Defends against stale/sibling rooms
(the original THOR's F103 lesson).

Day-one implementation: a MINIMAL LOCAL Ed25519 signer (per PRD §14 — "reuse from AGT/Mesh,
or a minimal local signer for v1" and Rule 5 — stub externals). The real AGT/Mesh identity
wiring is Module 12, behind adapters/.
"""
from __future__ import annotations

import json
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

DEFAULT_KEY_PATH = os.environ.get("THOR_SIGNING_KEY", ".thor/room_signing_key.pem")


def _b64(b: bytes) -> str:
    return urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return urlsafe_b64decode(s + pad)


class IdentityStamper:
    """Control-plane-side signer. One signing key per THOR instance, persisted on disk."""

    def __init__(self, key_path: str = DEFAULT_KEY_PATH) -> None:
        self.key_path = key_path
        self._private = self._load_or_create_key()
        self._public = self._private.public_key()

    def _load_or_create_key(self) -> Ed25519PrivateKey:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                return load_pem_private_key(f.read(), password=None)
        key = Ed25519PrivateKey.generate()
        os.makedirs(os.path.dirname(self.key_path) or ".", exist_ok=True)
        with open(self.key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
                )
            )
        os.chmod(self.key_path, 0o600)
        return key

    def public_key_b64(self) -> str:
        raw = self._public.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return _b64(raw)

    def sign_blob(self, data: bytes) -> str:
        """Sign arbitrary bytes (used by the Leash's Decision Recorder to sign EventLog entries)."""
        return _b64(self._private.sign(data))

    def verify_blob(self, data: bytes, sig_b64: str) -> bool:
        try:
            self._public.verify(_unb64(sig_b64), data)
            return True
        except (InvalidSignature, ValueError):
            return False

    def stamp(self, room_id: str, task_type: str) -> str:
        """Produce a signed room token: `<payload_b64>.<signature_b64>`."""
        payload = json.dumps(
            {"room_id": room_id, "task_type": task_type, "iss": "thor-wall"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        sig = self._private.sign(payload)
        return f"{_b64(payload)}.{_b64(sig)}"

    def verify(self, token: str, expect_room_id: str | None = None) -> bool:
        """
        Verify a token was signed by THIS instance and (optionally) matches the expected room.
        Returns False for forged/stale/garbled tokens (AC-10 negative test).
        """
        try:
            payload_b64, sig_b64 = token.split(".", 1)
            payload = _unb64(payload_b64)
            self._public.verify(_unb64(sig_b64), payload)
            if expect_room_id is not None:
                data = json.loads(payload)
                return data.get("room_id") == expect_room_id
            return True
        except (InvalidSignature, ValueError, KeyError, json.JSONDecodeError):
            return False


def verify_with_public_key(public_key_b64: str, token: str) -> bool:
    """Stateless verify given only a published public key (how a remote ThorManager checks)."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(_unb64(public_key_b64))
        payload_b64, sig_b64 = token.split(".", 1)
        pub.verify(_unb64(sig_b64), _unb64(payload_b64))
        return True
    except (InvalidSignature, ValueError):
        return False
