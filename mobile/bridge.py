"""
Sub-module 9.1 — PhoneBridge (control-plane side) + device registry/revocation.

Takes Manager cards/state → seals → pushes to the phone (via the relay); receives sealed, signed
actions back → opens → checks the allowlist → verifies the device is trusted (revocable) → dispatches
through the SAME DashboardService path as the desktop (M8). It holds NO inbound port (it dials out to
the relay, FR-5/AC-3); every action it lets through is recorded as an event identically to desktop
(FR-12/AC-10).
"""
from __future__ import annotations

import json

from . import allowlist, crypto


class PhoneBridge:
    def __init__(self, manager, service, relay, cp_priv) -> None:
        self.manager = manager
        self.service = service           # the M8 DashboardService — same verify/record/dedupe path
        self.relay = relay
        self.cp_priv = cp_priv           # control-plane E2EE private key (never leaves the control plane)
        self.inbound_port = None         # NO inbound port — the control plane dials OUT (AC-3)
        self._devices: dict[str, dict] = {}   # device_id -> {e2ee_pub, signing_pub} (revocable, FR-14)

    # ---- device registry + revocation (AC-9) ----
    def register_device(self, device_id: str, e2ee_pub: str, signing_pub: str) -> None:
        self._devices[device_id] = {"e2ee_pub": e2ee_pub, "signing_pub": signing_pub}

    def revoke_device(self, device_id: str) -> None:
        self._devices.pop(device_id, None)
        self.manager._record("device.revoked", {"device_id": device_id}, actor="control-plane")

    # ---- control plane -> phone (push, ciphertext) ----
    def push_card(self, card: dict, device_id: str) -> None:
        pub = self._devices[device_id]["e2ee_pub"]
        self.relay.cp_send(crypto.seal(json.dumps(card).encode(), self.cp_priv, pub))

    # ---- phone -> control plane (signed, ciphertext) ----
    def process_inbound(self) -> dict:
        blob = self.relay.cp_recv()
        if blob is None:
            return {"status": "no_message"}
        try:
            msg = json.loads(crypto.open_(blob, self.cp_priv))     # AEAD: a forged/tampered blob fails here
        except Exception:  # noqa: BLE001
            return {"status": "rejected", "reason": "cannot decrypt (forged/tampered) — relay forges nothing"}

        cmd = msg.get("command")
        if not allowlist.allowed(cmd):                              # FR-4 / AC-4 / AC-11
            self.manager._record("security.rejected",
                                 {"command": cmd, "reason": "not allowlisted"}, actor="phone")
            return {"status": "rejected", "reason": f"command {cmd!r} is not allowlisted"}

        device = self._devices.get(msg.get("device_id"))
        if device is None:                                          # FR-14 / AC-9 (revoked/unknown device)
            return {"status": "rejected", "reason": "device revoked or unknown — signature not trusted"}
        signing_pub = device["signing_pub"]

        # dispatch through the SAME DashboardService path as desktop (consistency + audit + dedupe)
        if cmd == "approve":
            return {"status": "ok", **self.service.approve(msg["card_id"], msg["signature"], signing_pub)}
        if cmd == "reject":
            return {"status": "ok", **self.service.reject(msg["card_id"], msg["signature"], signing_pub,
                                                          msg.get("reason", ""))}
        if cmd == "mark_ready":
            self.service.mark_ready(msg["feature_id"])
            return {"status": "ok"}
        if cmd == "add_feature":
            fid = self.service.add_feature(msg["title"], msg.get("context", ""), msg.get("priority", 3))
            return {"status": "ok", "feature_id": fid}
        return {"status": "ok", "note": "view/prioritize handled as read"}
