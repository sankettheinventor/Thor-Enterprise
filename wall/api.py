"""
Wall provisioning REST API (PRD §6.1). The small control interface ThorManager consumes.

It exposes nothing to the cook (the cook only sees its mounts and its one door). Run with:
    uvicorn wall.api:app --host 127.0.0.1 --port 7180

Built UNGOVERNED (P7): there is no policy/gate here. The gate is stubbed "always approve"
during bootstrap; real governance (the Leash / Manager) wraps this from Module 2 onward.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import config, provisioner
from .lifecycle import LifecycleController

app = FastAPI(title="THOR Wall", version="0.1.0")
_lifecycle = LifecycleController()

# Keep mount plans by room so destroy can clean temp dirs (process-local; rooms are ephemeral).
_mount_plans: dict = {}


class Limits(BaseModel):
    cpu: float = config.DEFAULT_CPU
    mem: str = config.DEFAULT_MEM
    disk: str = config.DEFAULT_DISK


class ProvisionRequest(BaseModel):
    task_type: str = Field(..., description="genesis | checker | build | qa")
    feature_slice: dict | None = None
    worktree_host_path: str | None = None
    rules_host_path: str | None = None
    codebase_host_path: str | None = None
    limits: Limits = Field(default_factory=Limits)


@app.post("/wall/provision")
def provision(req: ProvisionRequest) -> dict:
    if req.task_type not in config.VALID_TASK_TYPES:
        raise HTTPException(400, f"invalid task_type; expected {config.VALID_TASK_TYPES}")
    room = provisioner.provision_room(
        task_type=req.task_type,
        feature_slice=req.feature_slice,
        worktree_host_path=req.worktree_host_path,
        rules_host_path=req.rules_host_path,
        codebase_host_path=req.codebase_host_path,
        cpu=req.limits.cpu,
        mem=req.limits.mem,
    )
    _mount_plans[room["room_id"]] = room.pop("_mount_plan", None)
    return room


@app.get("/wall/rooms/{room_id}/health")
def health(room_id: str) -> dict:
    h = _lifecycle.health(room_id)
    return h.__dict__


@app.post("/wall/rooms/{room_id}/pause")
def pause(room_id: str) -> dict:
    return _lifecycle.pause(room_id)


@app.post("/wall/rooms/{room_id}/destroy")
def destroy(room_id: str) -> dict:
    result = provisioner.destroy_room(room_id, _mount_plans.pop(room_id, None))
    return result


@app.get("/wall/rooms")
def rooms() -> dict:
    return {"rooms": _lifecycle.list_rooms()}
