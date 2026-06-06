"""
Scheduler REST surface (PRD §6.1) — thin wrappers over the deterministic core, on :7110.

Run with:  uvicorn scheduler.api:app --host 127.0.0.1 --port 7110
The smoke drives the core in-process; this is the service shape for the real control plane.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core import Scheduler
from .graph import GraphError, Task

app = FastAPI(title="THOR Scheduler", version="0.1.0")


class TaskIn(BaseModel):
    feature_id: str
    depends_on: list[str] = []
    task_type: str = "build"
    est_tokens: int = 1000
    status: str = "pending"
    ready: bool = True


class PlanReq(BaseModel):
    catalog: list[TaskIn]
    capacity: int = 3
    budget_cap: int | None = None
    plan_approved: bool = True


def _sched(req: PlanReq) -> Scheduler:
    tasks = [Task(t.feature_id, tuple(t.depends_on), t.task_type, t.est_tokens, t.status, t.ready)
             for t in req.catalog]
    try:
        return Scheduler(tasks, req.capacity, req.budget_cap, req.plan_approved)
    except GraphError as e:
        raise HTTPException(400, str(e))


@app.post("/schedule/plan")
def plan(req: PlanReq):
    s = _sched(req)
    return {"waves": s.plan().waves, "levels": s.graph.levels}


@app.post("/schedule/dry_run")
def dry_run(req: PlanReq):
    return _sched(req).dry_run()


@app.get("/health")
def health():
    return {"alive": True, "responsive": True, "dag_loaded": True}
