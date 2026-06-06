"""
Sub-module 1.5 — Lifecycle Controller.

create / health-check / pause / destroy, and a registry VIEW. Tracks container state and
reports to ThorManager / Sentinel (FR-12, FR-16, AC-7, AC-12).

Design note (Rule 7 — single source of truth): the Wall keeps NO competing persisted state
store. The registry is *derived from Docker labels* (`thor.room_id`) — i.e. read back from
reality, not a second copy that can drift. The authoritative room registry is ThorManager's.
"""
from __future__ import annotations

from dataclasses import dataclass

import docker


@dataclass
class RoomHealth:
    room_id: str
    alive: bool          # container exists and is running
    responsive: bool     # agent-server answered (distinct from "process up" — FR-16)
    agent_server: bool
    leash_proxy: bool


class LifecycleController:
    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self.client = client or docker.from_env()

    # --- create is performed by provisioner.provision_room (it composes mounts/network/identity) ---

    def _by_room_id(self, room_id: str):
        cs = self.client.containers.list(
            all=True, filters={"label": f"thor.room_id={room_id}"}
        )
        return cs[0] if cs else None

    def health(self, room_id: str) -> RoomHealth:
        """
        Report alive AND responsive (FR-16). On day one the room has no network
        (sealed shut), so responsiveness is checked via container exec/state rather than an
        HTTP probe to :8000; the HTTP responsiveness probe lands with the agent-server.
        """
        c = self._by_room_id(room_id)
        if c is None:
            return RoomHealth(room_id, False, False, False, False)
        c.reload()
        alive = c.status == "running"
        # Day-one responsiveness: can we exec a trivial command? (true responsiveness, not just status)
        responsive = False
        if alive:
            try:
                rc = c.exec_run("true")
                responsive = rc.exit_code == 0
            except docker.errors.APIError:
                responsive = False
        # agent_server / leash_proxy come online with their modules; report presence honestly.
        return RoomHealth(room_id, alive, responsive, agent_server=False, leash_proxy=False)

    def pause(self, room_id: str) -> dict:
        c = self._by_room_id(room_id)
        if c is None:
            return {"room_id": room_id, "status": "error", "reason": "not_found"}
        c.pause()
        return {"room_id": room_id, "status": "paused"}

    def destroy(self, room_id: str) -> dict:
        """
        Fully remove the container + ephemeral state (FR-12). The branch persists in git;
        the container does not. Never leave an unlocked zombie (PRD §10).
        """
        c = self._by_room_id(room_id)
        if c is None:
            return {"room_id": room_id, "status": "already_gone", "branch_preserved": True}
        try:
            c.remove(force=True)
        except docker.errors.APIError as e:
            return {"room_id": room_id, "status": "error", "reason": str(e)}
        return {"room_id": room_id, "status": "destroyed", "branch_preserved": True}

    def list_rooms(self) -> list[dict]:
        """Registry VIEW, derived from Docker labels (not a competing store)."""
        rooms = []
        for c in self.client.containers.list(all=True, filters={"label": "thor.room=1"}):
            labels = c.labels or {}
            rooms.append(
                {
                    "room_id": labels.get("thor.room_id"),
                    "task_type": labels.get("thor.task_type"),
                    "status": c.status,
                    "address": None,  # populated when the agent-server is reachable
                }
            )
        return rooms

    def reap_orphans(self, known_room_ids: set[str]) -> list[str]:
        """
        D5 — clean teardown at scale. Reconcile Docker reality vs the set ThorManager still
        considers live; force-remove THOR rooms nobody owns anymore. Returns reaped ids.
        """
        reaped = []
        for c in self.client.containers.list(all=True, filters={"label": "thor.room=1"}):
            rid = (c.labels or {}).get("thor.room_id")
            if rid and rid not in known_room_ids:
                try:
                    c.remove(force=True)
                    reaped.append(rid)
                except docker.errors.APIError:
                    pass
        return reaped
