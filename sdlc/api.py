"""
Stage orchestration REST surface (PRD §6.1) — thin; stages run as rooms (Wall), not their own ports.
The real coordination is event-driven via the Manager; this is the control-plane orchestration shape.

Run with:  uvicorn sdlc.api:app --host 127.0.0.1 --port 7140
"""
from __future__ import annotations

from fastapi import Depends, FastAPI

from rbac import OPERATOR
from thor_http_auth import require_role
from pydantic import BaseModel

from . import skills

app = FastAPI(title="THOR SDLC Stages", version="0.1.0")


class ComposeReq(BaseModel):
    task_type: str
    capability_tags: list[str] = []


@app.post("/stage/compose_skills")
def compose_skills(req: ComposeReq, _user=Depends(require_role(OPERATOR))):
    b = skills.compose(req.task_type, req.capability_tags)
    return {"floor": list(b.floor), "specialty": list(b.specialty), "bundle": list(b.all_skills)}


@app.get("/health")
def health():
    return {"alive": True, "responsive": True}
