"""
Manager REST surface (PRD §6.1) — thin wrappers over ThorManager. Internal, on :7100.

Run with:  uvicorn manager.api:app --host 127.0.0.1 --port 7100
(The smoke drives ThorManager in-process; this is the service shape for when the control plane
runs for real.)
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from rbac import COMMANDER, OPERATOR
from thor_http_auth import require_role

from . import db
from .core import FailClosed, ThorManager
from .pg import DSN  # noqa: F401  (documents the DSN the Manager binds to)

app = FastAPI(title="THOR Manager", version="0.1.0")
_manager: ThorManager | None = None

# RBAC role gates (AUD-rbac-failopen): the Manager surface is served on :7100, so its mutating endpoints
# must enforce the SAME roles as the dashboard — provisioning/destroying rooms is operational (operator+);
# writing a raw ledger event is an authority-grade action (commander, the same tier as signing a merge).
# When THOR_USERS is unset these fall back to the legacy single-token / open posture (dev/test unchanged).
_operator = require_role(OPERATOR)
_commander = require_role(COMMANDER)


def manager() -> ThorManager:
    global _manager
    if _manager is None:
        conn = db.connect()
        db.init_schema(conn)
        _manager = ThorManager(conn)
    return _manager


class ProvisionReq(BaseModel):
    feature_id: str
    task_type: str = "build"
    base_branch: str = "main"
    network_mode: str = "sealed"


class EventReq(BaseModel):
    event_type: str
    payload: dict
    actor: str = "manager"
    room_id: str | None = None
    feature_id: str | None = None
    client_id: str | None = None


@app.post("/rooms/provision")
def provision(req: ProvisionReq, _user=Depends(_operator)):
    try:
        room = manager().provision_room(req.feature_id, req.task_type, network_mode=req.network_mode)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"room_id": room["room_id"], "status": "working"}


@app.post("/rooms/{room_id}/destroy")
def destroy(room_id: str, _user=Depends(_operator)):
    return manager().destroy_room(room_id)


@app.post("/events/append")
def append_event(req: EventReq, _user=Depends(_commander)):
    try:
        return manager()._record(req.event_type, req.payload, actor=req.actor,
                                 room_id=req.room_id, feature_id=req.feature_id, client_id=req.client_id)
    except FailClosed as e:
        raise HTTPException(503, str(e))


@app.get("/rooms")
def rooms():
    return {"rooms": manager().state_summary()["rooms"]}


@app.get("/state/summary")
def state_summary():
    return manager().state_summary()


@app.get("/health")
def health():
    return manager().health()
