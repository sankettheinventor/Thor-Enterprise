"""
Module 9 — native Web Push (VAPID). The phone gets a THOR-styled OS notification the moment a card needs
the CEO's signature (or a lie is caught) — even with the app closed. Standard Web Push: the payload is
END-TO-END encrypted to the device's own keys (aes128gcm), and the push service (FCM/APNs) only relays
ciphertext — it can't read the alert. The VAPID private key stays on the SERVER, never in a room.

Same principle as the rest of THOR: the most-exposed surface carries the least secret.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush

_KEY = Path(os.environ.get("THOR_VAPID_KEY", ".thor/vapid_key.pem"))
_SUBS = Path(os.environ.get("THOR_PUSH_SUBS", ".thor/push_subs.json"))
_CONTACT = os.environ.get("THOR_VAPID_CONTACT", "mailto:ops@thor.local")


def _vapid() -> Vapid01:
    v = Vapid01()
    if _KEY.exists():
        v.from_file(str(_KEY))
    else:
        v.generate_keys()
        _KEY.parent.mkdir(parents=True, exist_ok=True)
        v.save_key(str(_KEY))
    return v


def public_key() -> str:
    """The applicationServerKey the browser uses to subscribe (uncompressed P-256 point, base64url)."""
    v = _vapid()
    return b64urlencode(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))


def _load() -> list[dict]:
    try:
        return json.loads(_SUBS.read_text()) if _SUBS.exists() else []
    except Exception:  # noqa: BLE001 — corrupt/absent store: start empty, never crash the plane
        return []


def _save(subs: list[dict]) -> None:
    _SUBS.parent.mkdir(parents=True, exist_ok=True)
    _SUBS.write_text(json.dumps(subs))


def subscribe(sub: dict) -> int:
    """Store a device's push subscription (endpoint + p256dh + auth). Returns the subscriber count."""
    subs = _load()
    if sub.get("endpoint") and sub not in subs:
        subs.append(sub)
        _save(subs)
    return len(subs)


def send(title: str, body: str, url: str = "/app/") -> dict:
    """Send a THOR-styled notification to every subscribed device; prune dead subscriptions (404/410)."""
    _vapid()  # ensure the key exists
    payload = json.dumps({"title": title, "body": body, "url": url, "icon": "/app/icon.svg", "tag": "thor"})
    subs = _load()
    sent, alive, dropped = 0, [], 0
    for sub in subs:
        try:
            webpush(subscription_info=sub, data=payload, vapid_private_key=str(_KEY),
                    vapid_claims={"sub": _CONTACT})
            sent += 1
            alive.append(sub)
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):       # the subscription is gone — drop it
                dropped += 1
            else:                        # transient — keep it for next time
                alive.append(sub)
    if dropped:
        _save(alive)
    return {"sent": sent, "subscribers": len(subs), "dropped": dropped}
