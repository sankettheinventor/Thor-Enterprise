"""
Sub-module 5.4 — Transport Adapter. The SAME six messages over different transports (FR-10).

  InProcessTransport — the v1.1 "REST-style" stand-in: in-memory request/reply (no container).
  DockerExecTransport — the v1 transport: carries messages into a REAL room via `docker exec`;
                        the slice is read from the read-only `/task/feature.json` mount (Wall M1).

Both expose the identical interface, so the seam logic is byte-for-byte the same across them —
that is the transport-swappability proof (AC-5/AC-12): switching the adapter changes nothing else.
"""
from __future__ import annotations

import base64
import json
import re
from abc import ABC, abstractmethod


class Transport(ABC):
    name: str

    @abstractmethod
    def deliver(self, direction: str, room_id: str, msg_type: str, payload: dict) -> bool: ...

    @abstractmethod
    def read_slice(self, room_id: str) -> dict | None: ...

    @abstractmethod
    def attempt_write_slice(self, room_id: str, content: str = "x") -> bool: ...


class InProcessTransport(Transport):
    """v1.1 REST-style: messages are carried in-memory. The slice is held immutably (read-only)."""
    name = "in-process"

    def __init__(self) -> None:
        self.log: list[tuple[str, str, dict]] = []
        self._slices: dict[str, dict] = {}

    def deliver(self, direction, room_id, msg_type, payload) -> bool:
        self.log.append((direction, msg_type, payload))
        if msg_type == "assign_task":
            self._slices[room_id] = payload["feature_slice"]
        return True

    def read_slice(self, room_id):
        return self._slices.get(room_id)

    def attempt_write_slice(self, room_id, content="x") -> bool:
        return False   # the slice is read-only by contract; the real FS guarantee is the Wall's (AC-3)


class DockerExecTransport(Transport):
    """v1 docker-exec: carries messages into a real room; reads the read-only slice mount."""
    name = "docker-exec"

    def __init__(self, container) -> None:
        self.container = container
        self.log: list[tuple[str, str, dict]] = []

    def deliver(self, direction, room_id, msg_type, payload) -> bool:
        # Carry the message as a file into the room. BASE64 the JSON so no shell metacharacter in the
        # payload can break the quoting or corrupt the message (output encoding per context — invariant #8);
        # sanitise msg_type to an allow-list; run as the unprivileged cook (least privilege).
        b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        safe_type = re.sub(r"[^A-Za-z0-9_]", "", msg_type) or "msg"
        r = self.container.exec_run(
            ["sh", "-c", f"echo {b64} | base64 -d > /tmp/msg_{safe_type}.json"], user="cook")
        self.log.append((direction, msg_type, payload))
        return r.exit_code == 0

    def read_slice(self, room_id):
        r = self.container.exec_run(["cat", "/task/feature.json"])
        if r.exit_code != 0:
            return None
        return json.loads(r.output.decode())

    def attempt_write_slice(self, room_id, content="x") -> bool:
        # Try to modify the read-only slice from inside the room — must FAIL (Wall read-only mount).
        r = self.container.exec_run(["sh", "-c", f"echo {content} > /task/feature.json"], user="cook")
        return r.exit_code == 0   # True would mean the write succeeded (bad)
