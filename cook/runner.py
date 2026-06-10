"""
CookRunner — launch the SELECTED cook (any agent) inside a THOR room and collect the result.

THOR provides the room (the walls); the CookRuntime says how to launch the agent; the GovEngine verdict
judges the OUTPUT. The runner is the seam between them. `plan()` is the docker-free description (auditable
before anything runs — testable); `run()` does the live provision + exec.

Note: an agent that needs its model (Claude Code, etc.) requires `network_mode="one_door"` egress to its
model hosts — that egress (`wall/network_enforcer.one_door_room_kwargs`) is the named prerequisite and is
not built yet, so `run()` defaults to "sealed" (works for agents that need no network).
"""
from __future__ import annotations

from .runtime import CookRuntime, select_runtime


class CookRunner:
    def __init__(self, runtime: CookRuntime | None = None, provisioner=None) -> None:
        self.runtime = runtime or select_runtime()
        self._prov = provisioner            # wall.provisioner (injectable for tests)

    def plan(self, feature_slice: dict) -> dict:
        """Docker-free: the room image + command + env-keys this run WILL use (auditable before launch)."""
        return {"runtime": self.runtime.name, **self.runtime.describe(feature_slice)}

    def run(self, feature_slice: dict, *, worktree_host_path: str,
            network_mode: str = "sealed", timeout: int = 1800) -> dict:
        """Provision a room with the agent's image, run the agent in it as the unprivileged cook, and
        return {room_id, exit_code, output, _mount_plan}. The caller then runs the GovEngine verdict on
        the branch (the agnostic enforcement). Sealed by default; an LLM agent needs network_mode='one_door'."""
        prov = self._prov or _provisioner()
        room = prov.provision_room(
            task_type="build", feature_slice=feature_slice, worktree_host_path=worktree_host_path,
            network_mode=network_mode, extra_env=self.runtime.env(), image=self.runtime.image())
        container = _docker().containers.get(room["room_id"])
        res = container.exec_run(self.runtime.command(feature_slice), user="cook", workdir="/work")
        out = (res.output or b"")
        return {"room_id": room["room_id"], "exit_code": res.exit_code,
                "output": out.decode("utf-8", "replace")[-4000:], "_mount_plan": room.get("_mount_plan")}


def _provisioner():
    from wall import provisioner
    return provisioner


def _docker():
    import docker
    return docker.from_env()
