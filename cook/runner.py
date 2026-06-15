"""
CookRunner — launch the SELECTED cook (any agent) inside a THOR room and collect the result.

THOR provides the room (the walls); the CookRuntime says how to launch the agent; the GovEngine verdict
judges the OUTPUT. The runner is the seam between them. `plan()` is the docker-free description (auditable
before anything runs — testable); `run()` does the live provision + exec.

Egress (C1): `run()` AUTO-SELECTS the network mode from the cook's `egress_allowlist()`. A cook that
declares model/auth hosts (Claude Code → api.anthropic.com, …) gets a real `one_door` room — internal net
only, with the governed leash gateway started as its ONE forwarder, allowlisting exactly those hosts and
denying all else. A cook with no allowlist runs fully `sealed`. The cook carries its OWN credential in its
env (COOK.md); THOR injects no model-host secret — the token rides inside TLS, the gateway only tunnels
the allowlisted host.
"""
from __future__ import annotations

import os
import tempfile
import uuid

from .runtime import CookRuntime, select_runtime

# Parallel cooks (no lock): every request already carries a room_id/feature_id, so each one-door build gets
# its OWN gateway + its OWN internal room-net keyed by that id (thor-leash-gateway-<id> on thor-room-net-<id>).
# Two cooks therefore NEVER share a gateway or a net — each is behind its own door with EXACTLY its own
# allowlist, fully isolated, with no global singleton to swap out from under it. True parallel by isolation,
# not by serialization. (Replaces the former _ONE_DOOR_LOCK.)


class CookRunner:
    def __init__(self, runtime: CookRuntime | None = None, provisioner=None) -> None:
        self.runtime = runtime or select_runtime()
        self._prov = provisioner            # wall.provisioner (injectable for tests)

    def plan(self, feature_slice: dict) -> dict:
        """Docker-free: the room image + command + env-keys this run WILL use (auditable before launch)."""
        allowlist = self.runtime.egress_allowlist()
        return {"runtime": self.runtime.name, "network_mode": "one_door" if allowlist else "sealed",
                **self.runtime.describe(feature_slice)}

    def run(self, feature_slice: dict, *, worktree_host_path: str,
            network_mode: str | None = None, timeout: int = 1800) -> dict:
        """Provision a room with the agent's image, run the agent in it as the unprivileged cook, and
        return {room_id, exit_code, network_mode, output, _mount_plan}. The caller then runs the GovEngine
        verdict on the branch (the agnostic enforcement). The network mode is AUTO-SELECTED from the cook's
        egress allowlist (one_door when it needs its model, else sealed); pass `network_mode` to override."""
        allowlist = self.runtime.egress_allowlist()
        if network_mode is None:
            network_mode = "one_door" if allowlist else "sealed"   # C1: a cook that needs its model gets one door
        if network_mode == "one_door":
            suffix = self._suffix(feature_slice)     # per-cook gateway+net key (room_id/feature_id from the request)
            self._start_gateway(allowlist, suffix)
            try:
                return self._provision_and_exec(feature_slice, worktree_host_path, network_mode, suffix)
            finally:
                self._teardown_gateway(suffix)       # tears down ONLY this cook's door + net; peers untouched
        return self._provision_and_exec(feature_slice, worktree_host_path, network_mode)

    @staticmethod
    def _suffix(feature_slice: dict) -> str:
        """Per-cook isolation key: the feature_id from the request (every request has one). Fall back to a
        fresh unique id so even an id-less slice gets its own door rather than colliding on the default."""
        fid = (feature_slice or {}).get("feature_id")
        return str(fid) if fid else uuid.uuid4().hex[:12]

    def _provision_and_exec(self, feature_slice: dict, worktree_host_path: str, network_mode: str,
                            suffix: str = "") -> dict:
        prov = self._prov or _provisioner()
        room = prov.provision_room(
            task_type="build", feature_slice=feature_slice, worktree_host_path=worktree_host_path,
            network_mode=network_mode, extra_env=self.runtime.env(), image=self.runtime.image(),
            net_suffix=suffix)
        container = _docker().containers.get(room["room_id"])
        res = container.exec_run(self.runtime.command(feature_slice), user="cook", workdir="/work")
        out = (res.output or b"")
        return {"room_id": room["room_id"], "exit_code": res.exit_code, "network_mode": network_mode,
                "output": out.decode("utf-8", "replace")[-4000:], "_mount_plan": room.get("_mount_plan")}

    def _start_gateway(self, allowlist, suffix: str = "") -> None:
        """Start THIS cook's governed one-door gateway allowlisting exactly its model hosts. THOR injects no
        model-host secret — the cook's OWN credential (its env, COOK.md) rides inside TLS; the gateway only
        do_CONNECT-tunnels the allowlisted host. Keyed by `suffix` so parallel cooks never collide."""
        from leash import gateway
        leash_host_path = os.path.dirname(os.path.abspath(gateway.__file__))
        gateway.start_gateway(_docker(), leash_host_path=leash_host_path,
                              decision_log_dir=os.path.join(tempfile.gettempdir(), "thor-leash"),
                              allowlist=tuple(allowlist), suffix=suffix)

    def _teardown_gateway(self, suffix: str = "") -> None:
        try:
            from leash import gateway
            gateway.teardown(_docker(), suffix=suffix)
        except Exception:  # noqa: BLE001 — best-effort teardown; never mask the build result
            pass


def _provisioner():
    from wall import provisioner
    return provisioner


def _docker():
    import docker
    return docker.from_env()
