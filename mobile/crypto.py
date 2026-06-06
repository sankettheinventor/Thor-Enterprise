"""
Sub-module 9.2 — End-to-end encryption (FR-2). Real sealed-box-style E2EE using the `cryptography`
library: X25519 ECDH → HKDF → ChaCha20-Poly1305 AEAD. Keys live ONLY on the device and the control
plane; the relay transports ciphertext only. AEAD authentication means a tampered or forged blob
fails to open — the relay can neither read nor forge (AC-2).
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from wall.identity_stamper import _b64, _unb64


def gen_keypair() -> tuple[X25519PrivateKey, str]:
    """Return (private_key, public_key_b64). The private key never leaves its owner."""
    priv = X25519PrivateKey.generate()
    pub_b64 = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub_b64


def _derive(priv: X25519PrivateKey, peer_pub_b64: str) -> bytes:
    peer = X25519PublicKey.from_public_bytes(_unb64(peer_pub_b64))
    shared = priv.exchange(peer)
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"thor-e2ee").derive(shared)


def seal(plaintext: bytes, sender_priv: X25519PrivateKey, recipient_pub_b64: str) -> dict:
    """Encrypt for the recipient. The returned blob is what the relay sees — ciphertext only."""
    key = _derive(sender_priv, recipient_pub_b64)
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)
    sender_pub = _b64(sender_priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return {"nonce": _b64(nonce), "ct": _b64(ct), "sender_pub": sender_pub}


def open_(blob: dict, recipient_priv: X25519PrivateKey) -> bytes:
    """Decrypt + authenticate. Raises on a tampered/forged blob (AEAD) — the relay can forge nothing."""
    key = _derive(recipient_priv, blob["sender_pub"])
    return ChaCha20Poly1305(key).decrypt(_unb64(blob["nonce"]), _unb64(blob["ct"]), None)
