"""
Sub-module 1.2 — Provisioner. The day-one artifact.

Creates ONE sealed room by composing the other sub-modules in the order of PRD §5.2:
    Mount Manager (1.4) -> Image (1.1) -> Network Enforcer (1.3) -> Identity Stamper (1.6)
    -> Lifecycle Controller (1.5 start) -> report {room_id, address, status:"ready"}.

Big ideas held constant (the approved starter, hardened):
    - network sealed shut on day one (network_disabled=True; one-door :8001 arrives at M2),
    - task slice mounted READ-ONLY at /task/feature.json (FR-6),
    - worktree mounted READ-WRITE at /work (FR-8),
    - unprivileged cook, all capabilities dropped, no-new-privileges (D2),
    - CPU/RAM caps (FR-11), thor.* labels for the registry view.

Built UNGOVERNED (P7). Smoke-check ("does it run"); full AC-1..AC-12 PROVING is deferred (Rule 2).

Requires: pip install docker
"""
from __future__ import annotations

import uuid

import docker

from . import config, identity_stamper, mount_manager, network_enforcer
from .lifecycle import LifecycleController

# FINDING-A: the Docker client is created LAZILY (on first provisioning), never at import. Importing
# this module (and therefore ThorManager) must not require a running Docker daemon — only actually
# provisioning/destroying a room does. _stamper is pure Ed25519 keygen, so it stays module-level.
client = None
_stamper = identity_stamper.IdentityStamper()
_lifecycle = None


def _ensure_client() -> "docker.DockerClient":
    """Connect to Docker on first real use (fail here, when a room is actually needed — not at import)."""
    global client, _lifecycle
    if client is None:
        client = docker.from_env()
        _lifecycle = LifecycleController(client)
    return client


def build_image() -> str:
    """Build the room OCI image from wall/image/ (1.1 Image Builder, day-one single-arch)."""
    _ensure_client()
    img, _ = client.images.build(path="wall/image", tag=config.ROOM_IMAGE, rm=True)
    return img.id


def provision_room(
    task_type: str = "build",
    feature_slice: dict | None = None,
    worktree_host_path: str | None = None,
    rules_host_path: str | None = None,
    codebase_host_path: str | None = None,
    cpu: float = config.DEFAULT_CPU,
    mem: str = config.DEFAULT_MEM,
    network_mode: str = "sealed",
    extra_env: dict | None = None,
) -> dict:
    """
    Create one room and return its descriptor (PRD §6.1 provision response shape).

    network_mode:
        "sealed"   — Module 1 day-one form: network_disabled=True (no network at all).
        "one_door" — Module 2 Phase 2b: attached only to the internal room-net; the leash gateway
                     is the sole reachable forwarder. (Caller must have started the gateway.)

    NOTE: this BUILDS and RUNS a container. It is invoked only when asked — never on import.
    """
    _ensure_client()               # FINDING-A: connect to Docker now (on real use), not at import
    config.profile_for(task_type)  # validates task_type (FR-15)
    room_id = f"room-{uuid.uuid4().hex[:8]}"

    spec = config.RoomSpec(
        room_id=room_id,
        task_type=task_type,
        feature_slice=feature_slice,
        worktree_host_path=worktree_host_path,
        rules_host_path=rules_host_path,
        codebase_host_path=codebase_host_path,
        cpu=cpu,
        mem=mem,
    )

    # 1.4 Mount Manager — permission-correct mounts (ro/rw per FR-6..FR-9).
    plan = mount_manager.build_mounts(spec)

    # 1.6 Identity Stamper — signed room token, injected as an env var the cook cannot forge.
    token = _stamper.stamp(room_id, task_type)

    # 1.3 Network Enforcer — sealed shut (M1) or one-door internal net (M2 Phase 2b).
    if network_mode == "one_door":
        network_enforcer.ensure_networks(client)
        net_kwargs = network_enforcer.one_door_room_kwargs()
    else:
        net_kwargs = network_enforcer.network_kwargs(room_id)

    env = {"THOR_ROOM_TOKEN": token, "THOR_ROOM_ID": room_id}
    if extra_env:
        env.update(extra_env)

    container = client.containers.run(
        config.ROOM_IMAGE,
        # ENTRYPOINT is /bin/bash, so pass `-c "sleep infinity"` to keep the room alive
        # (a bare "sleep infinity" would be read by bash as a filename and exit). Placeholder
        # until the cook's agent-server becomes the entrypoint (M2).
        command=["-c", "sleep infinity"],
        name=room_id,
        detach=True,
        mounts=plan.mounts,
        environment=env,
        mem_limit=mem,
        nano_cpus=int(cpu * 1e9),
        user="cook",                       # unprivileged (D2)
        cap_drop=["ALL"],                  # drop Linux capabilities (D2)
        security_opt=["no-new-privileges"],
        read_only=False,                   # /work needs rw; root FS hardening tightened later (D2)
        labels={
            "thor.room": "1",
            "thor.task_type": task_type,
            "thor.room_id": room_id,
        },
        **net_kwargs,
    )

    # Defence-in-depth: confirm from Docker ground-truth that the room is really locked down.
    if network_mode == "one_door":
        locked = network_enforcer.assert_no_internet(container)   # on internal net only (AC-5)
    else:
        locked = network_enforcer.assert_sealed(container)        # no network at all (AC-2)

    return {
        "room_id": room_id,
        "container": container.id,
        "task_type": task_type,
        "network_mode": network_mode,
        "status": "ready" if locked else "error",
        "sealed": locked,
        "identity_token": token,
        "agent_port": config.AGENT_PORT,
        "_mount_plan": plan,   # kept so destroy can clean temp dirs
    }


def destroy_room(room_id: str, mount_plan: mount_manager.MountPlan | None = None) -> dict:
    """Tear down the container (FR-12); the branch in git persists, the container does not."""
    _ensure_client()               # FINDING-A: lazy Docker connect (not at import)
    result = _lifecycle.destroy(room_id)
    if mount_plan is not None:
        mount_manager.cleanup(mount_plan)
    return result


if __name__ == "__main__":
    # Day-one smoke check (run ONLY when invoked, never on import): build, provision, destroy.
    # This is a smoke-check, not the AC proving suite (Rule 2). It writes nothing fake.
    build_image()
    room = provision_room(
        task_type="build",
        feature_slice={"feature_id": "F001", "goals": ["hello"]},
    )
    print("provisioned:", {k: v for k, v in room.items() if not k.startswith("_")})
    print("destroyed:", destroy_room(room["room_id"], room.get("_mount_plan")))
