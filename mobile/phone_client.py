"""
Sub-modules 9.3/9.4/9.7/9.8 — the phone-side client (a Python stand-in for the mobile app).

Holds the device's E2EE keypair and its Ed25519 signing identity (in a real app: the device
keystore/secure enclave). Receives sealed cards, renders legible refusal for the small screen, signs
the three signature points, and refuses to sign while disconnected (stale-safety, FR-10/AC-7).
"""
from __future__ import annotations

import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from dashboard import legible
from manager.core import ThorManager
from wall.identity_stamper import _b64

from . import crypto


class PhoneClient:
    def __init__(self, device_id: str, relay, cp_e2ee_pub: str) -> None:
        self.device_id = device_id
        self.relay = relay
        self.cp_pub = cp_e2ee_pub                       # control-plane E2EE public key (to seal up to it)
        self.e2ee_priv, self.e2ee_pub = crypto.gen_keypair()
        self._signing = Ed25519PrivateKey.generate()    # the operator's signing identity, on-device
        self.signing_pub = _b64(self._signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        self.connected = True

    def set_connected(self, value: bool) -> None:
        self.connected = value

    # ---- receive a pushed card (decrypt on-device) ----
    def receive(self) -> dict | None:
        blob = self.relay.phone_recv()
        return json.loads(crypto.open_(blob, self.e2ee_priv)) if blob else None

    def legible(self, reason: str, feature_id: str | None = None) -> str:
        # one-sentence plain-language "why", tuned for the small screen (shared renderer with M8)
        return legible.render(reason, feature_id)

    # ---- sign a card (the three signature points), refusing if disconnected ----
    def approve(self, card: dict) -> dict:
        if not self.connected:                          # FR-10 / AC-7 — never sign against a stale picture
            return {"sent": False, "reason": "disconnected — cannot sign against a possibly stale state"}
        material = ThorManager.card_material(card["card_id"], card["payload"])
        sig = _b64(self._signing.sign(material.encode()))
        self._send({"command": "approve", "card_id": card["card_id"], "signature": sig,
                    "device_id": self.device_id})
        return {"sent": True, "signature": sig}

    def sign_for(self, card_id: str, payload: dict) -> str:
        """Produce a signature for a specific card+payload (bound; not replayable across cards, AC-8)."""
        return _b64(self._signing.sign(ThorManager.card_material(card_id, payload).encode()))

    def send_command(self, command: str, **fields) -> None:
        self._send({"command": command, "device_id": self.device_id, **fields})

    def _send(self, msg: dict) -> None:
        self.relay.phone_send(crypto.seal(json.dumps(msg).encode(), self.e2ee_priv, self.cp_pub))
