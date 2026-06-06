"""
Sub-module 1.4 — Mount Manager.

Owns WHAT is mounted and with WHICH permissions. The read-only guarantees live here
(FR-6 task slice ro, FR-7 rules ro, FR-8 worktree rw, FR-9 checker codebase ro).

The cook can only ever see these mounts (PRD §6 — "the cook only sees its mounts and its
one door"). Nothing sensitive is mounted (D3 credential isolation): creds live in the AGT
adapter, never in the room.
"""
from __future__ import annotations

import json
import os
import tempfile

import docker

from . import config


class MountPlan:
    """The mounts for one room plus any temp dirs that must be cleaned on destroy."""

    def __init__(self) -> None:
        self.mounts: list[docker.types.Mount] = []
        self.temp_dirs: list[str] = []

    def _add(self, target: str, source: str, read_only: bool) -> None:
        self.mounts.append(
            docker.types.Mount(target, source, type="bind", read_only=read_only)
        )


def build_mounts(spec: config.RoomSpec) -> MountPlan:
    """
    Translate a RoomSpec into a concrete, permission-correct mount plan.

    Read-only is enforced by the mount itself (`read_only=True`) — a write attempt fails at
    the kernel/FS layer, not by convention. That is the trust guarantee behind AC-5/AC-6.
    """
    profile = config.profile_for(spec.task_type)
    plan = MountPlan()

    # FR-6: feature slice — read-only at /task/feature.json. The cook cannot edit its own scope.
    if spec.feature_slice is not None:
        slice_dir = tempfile.mkdtemp(prefix=f"{spec.room_id}-task-")
        with open(os.path.join(slice_dir, "feature.json"), "w") as f:
            json.dump(spec.feature_slice, f, indent=2)
        plan.temp_dirs.append(slice_dir)
        # mount the dir read-only; the file lands at /task/feature.json
        plan._add("/task", slice_dir, read_only=True)

    # FR-7: governance rules — read-only; editable only host-side.
    if spec.rules_host_path:
        plan._add(config.RULES_TARGET, spec.rules_host_path, read_only=True)

    # FR-8: worktree — read-write (the cook needs to build). build/genesis/qa.
    if profile.worktree_rw and spec.worktree_host_path:
        plan._add(config.WORKTREE_TARGET, spec.worktree_host_path, read_only=False)

    # FR-9: checker (and qa read-access) — codebase mounted READ-ONLY. Changes nothing.
    if profile.codebase_ro and spec.codebase_host_path:
        plan._add(config.CODEBASE_TARGET, spec.codebase_host_path, read_only=True)

    return plan


def cleanup(plan: MountPlan) -> None:
    """Remove temp dirs created for ephemeral mounts (called on room destroy)."""
    import shutil

    for d in plan.temp_dirs:
        shutil.rmtree(d, ignore_errors=True)
