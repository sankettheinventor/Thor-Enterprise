"""
Sub-module 9.2 — the Cloudflare relay model: a DUMB, ZERO-KNOWLEDGE pipe (FR-2, FR-5).

It only matches two encrypted endpoints (the control plane behind no inbound port, and the phone on
the internet) and moves ciphertext blobs between them. It NEVER holds keys, NEVER decrypts, NEVER
sees a card's contents or a signature's meaning. A fully-compromised relay can at most drop/delay
messages (a liveness issue) — it cannot read or forge anything (AC-2). The control plane DIALS OUT to
the relay; nothing listens for inbound connections on the control plane (AC-3).
"""
from __future__ import annotations


class Relay:
    def __init__(self) -> None:
        self._to_phone: list[dict] = []   # ciphertext blobs control-plane → phone
        self._to_cp: list[dict] = []      # ciphertext blobs phone → control-plane

    # the control plane dials OUT (no inbound port on the control plane)
    def cp_send(self, blob: dict) -> None:
        self._to_phone.append(blob)

    def cp_recv(self) -> dict | None:
        return self._to_cp.pop(0) if self._to_cp else None

    # the phone connects out to the relay
    def phone_send(self, blob: dict) -> None:
        self._to_cp.append(blob)

    def phone_recv(self) -> dict | None:
        return self._to_phone.pop(0) if self._to_phone else None

    # what a compromised relay can inspect: ONLY the ciphertext blobs (no plaintext, no keys).
    def all_ciphertext(self) -> list[dict]:
        return list(self._to_phone) + list(self._to_cp)
