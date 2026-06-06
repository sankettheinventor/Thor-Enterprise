"""
Sub-module 10.8 — Reconciler (FR-8 / AC-10).

Reconciles the Manager's room registry against ACTUAL running containers (Docker ground-truth):
  - orphan: the registry says a room exists, but no container is running → reap it.
  - shadow: a container is running with no registry entry → an unregistered agent → alarm (could be a
            leftover, or an attack — Shadow-AI discovery).
"""
from __future__ import annotations


class Reconciler:
    def __init__(self, client) -> None:
        self.client = client

    def _actual_room_ids(self) -> set[str]:
        ids = set()
        for c in self.client.containers.list(all=True, filters={"label": "thor.room=1"}):
            rid = (c.labels or {}).get("thor.room_id")
            if rid and c.status == "running":
                ids.add(rid)
        return ids

    def reconcile(self, registry_room_ids: set[str]) -> dict:
        actual = self._actual_room_ids()
        return {"orphans": sorted(registry_room_ids - actual),   # registered but no container
                "shadows": sorted(actual - registry_room_ids)}   # running but unregistered

    def reap(self, room_id: str) -> None:
        for c in self.client.containers.list(all=True, filters={"label": f"thor.room_id={room_id}"}):
            c.remove(force=True)
