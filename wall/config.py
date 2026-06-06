"""
Wall configuration — the task-type table (FR-15) and shared constants.

One OCI image, four behaviors. `task_type` selects which mounts/permissions/skills apply
(PRD §5.3). This is *configuration*, not separate code paths — keeps the Wall uniform.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# --- Image / ports (PRD §4, System Design §3) ---
ROOM_IMAGE = os.environ.get("THOR_ROOM_IMAGE", "thor-room:dev")
AGENT_PORT = int(os.environ.get("THOR_AGENT_PORT", "8000"))   # inbound: ThorManager -> agent-server
LEASH_PORT = int(os.environ.get("THOR_LEASH_PORT", "8001"))   # the ONLY outbound route (lands with M2)

# --- Default resource caps (FR-11) ---
DEFAULT_CPU = float(os.environ.get("THOR_DEFAULT_CPU", "1.0"))
DEFAULT_MEM = os.environ.get("THOR_DEFAULT_MEM", "1g")
DEFAULT_DISK = os.environ.get("THOR_DEFAULT_DISK", "2g")

# In-container mount targets (the cook only ever sees these — PRD §6).
TASK_SLICE_TARGET = "/task/feature.json"   # read-only feature slice (FR-6)
RULES_TARGET = "/rules"                     # read-only governance rules (FR-7)
WORKTREE_TARGET = "/work"                   # read-write worktree (FR-8)
CODEBASE_TARGET = "/codebase"               # checker: read-only codebase (FR-9)

VALID_TASK_TYPES = ("genesis", "checker", "build", "qa")


@dataclass(frozen=True)
class TaskTypeProfile:
    """How one task_type configures a room (PRD §5.3)."""
    name: str
    worktree_rw: bool          # is a read-write worktree mounted? (build/qa yes)
    codebase_ro: bool          # is the existing codebase mounted read-only? (checker yes)
    skills: tuple[str, ...]    # which skills the skill-loader should load
    note: str


# FR-15: genesis | checker | build | qa  ->  mounts, permissions, skills.
TASK_TYPES: dict[str, TaskTypeProfile] = {
    "genesis": TaskTypeProfile(
        name="genesis", worktree_rw=True, codebase_ro=False,
        skills=("pm", "cto", "ux-strategy"),
        note="Planning workspace; no source repo yet. Produces the feature catalog (sig 1).",
    ),
    "checker": TaskTypeProfile(
        name="checker", worktree_rw=False, codebase_ro=True,
        skills=("analysis",),
        note="Existing codebase mounted READ-ONLY; emits findings only — changes nothing (FR-9).",
    ),
    "build": TaskTypeProfile(
        name="build", worktree_rw=True, codebase_ro=False,
        skills=("build",),
        note="Fresh worktree rw; normal governed build (gate stubbed during bootstrap).",
    ),
    "qa": TaskTypeProfile(
        name="qa", worktree_rw=True, codebase_ro=True,
        skills=("qa",),
        note="Build branch + read access to code; adversarial test (independent of the builder).",
    ),
}


def profile_for(task_type: str) -> TaskTypeProfile:
    if task_type not in TASK_TYPES:
        raise ValueError(
            f"unknown task_type {task_type!r}; expected one of {VALID_TASK_TYPES}"
        )
    return TASK_TYPES[task_type]


@dataclass
class RoomSpec:
    """Everything needed to provision one room (mirrors PRD §6.1 provision request)."""
    room_id: str
    task_type: str
    feature_slice: dict | None = None
    worktree_host_path: str | None = None
    rules_host_path: str | None = None
    codebase_host_path: str | None = None
    cpu: float = DEFAULT_CPU
    mem: str = DEFAULT_MEM
    skills: tuple[str, ...] = field(default_factory=tuple)
