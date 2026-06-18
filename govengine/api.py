"""
GovernanceEngine REST surface (PRD §6.1) — thin wrappers over the engine, on :7130.

Run with:  uvicorn govengine.api:app --host 127.0.0.1 --port 7130
The smoke drives the engine in-process; this is the service shape for the real control plane.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI

from rbac import OPERATOR
from thor_http_auth import require_role
from pydantic import BaseModel

from .engine import GovernanceEngine, VerdictContext

app = FastAPI(title="THOR GovernanceEngine", version="0.1.0")
_engine = GovernanceEngine()


class VerdictReq(BaseModel):
    feature_id: str
    branch: str
    repo: str
    contract: dict
    claim: dict = {}
    base_branch: str = "main"
    skill_results_ok: bool = True


@app.post("/verdict")
def verdict(req: VerdictReq, _user=Depends(require_role(OPERATOR))):
    ctx = VerdictContext(req.feature_id, req.branch, req.repo, req.contract, req.claim,
                         base_branch=req.base_branch, skill_results_ok=req.skill_results_ok)
    return _engine.run_verdict(ctx)


@app.get("/health")
def health():
    return {"alive": True, "responsive": True, "can_read_git": True,
            "can_read_ci": True, "can_read_audit": True}
