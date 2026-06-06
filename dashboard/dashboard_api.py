"""
The DashboardAPI (PRD §6) — the Manager's externally-reachable read/sign surface on :7080. A thin
FastAPI wrapper over DashboardService; the only externally-exposed surface (behind TLS in production).

Run with:  uvicorn dashboard.dashboard_api:app --host 127.0.0.1 --port 7080
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

app = FastAPI(title="THOR DashboardAPI", version="0.1.0")
_service = None   # set via dashboard.dashboard_api.bind(service) when the control plane boots


def bind(service) -> None:
    global _service
    _service = service


class FeatureIn(BaseModel):
    title: str
    context: str = ""
    priority: int = 3


class Sig(BaseModel):
    card_id: str
    signature: str
    signer_pub: str
    reason: str = ""


@app.get("/state/summary")
def state_summary():
    return _service.state_summary()


@app.get("/kanban")
def kanban():
    return _service.kanban()


@app.get("/rooms/live")
def rooms_live():
    return {"active": _service.rooms_live()}


@app.get("/cards")
def cards():
    return {"cards": _service.cards()}


@app.get("/audit/feed")
def audit_feed(feature_id: str | None = None):
    return {"events": _service.audit_feed(feature_id)}


@app.get("/audit/export", response_class=PlainTextResponse)
def audit_export(fmt: str = "json"):
    return _service.audit_export(fmt)


@app.get("/cost")
def cost():
    return _service.cost()


@app.get("/findings")
def findings():
    return {"checker_findings": _service.findings()}


@app.get("/health/system")
def health_system():
    return _service.health_system()


@app.post("/features")
def add_feature(f: FeatureIn):
    return {"feature_id": _service.add_feature(f.title, f.context, f.priority)}


@app.post("/approve")
def approve(s: Sig):
    return _service.approve(s.card_id, s.signature, s.signer_pub)


@app.post("/reject")
def reject(s: Sig):
    return _service.reject(s.card_id, s.signature, s.signer_pub, s.reason)
