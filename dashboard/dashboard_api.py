"""
The DashboardAPI (PRD §6) — the Manager's externally-reachable read/sign surface on :7080. A thin
FastAPI wrapper over DashboardService; the only externally-exposed surface (behind TLS in production).

Run with:  uvicorn dashboard.dashboard_api:app --host 127.0.0.1 --port 7080
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from thor_http_auth import require_token

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
    nonce: str | None = None   # T7: the one-time challenge bound to the card (replay defence)
    reason: str = ""


class OperatorKey(BaseModel):
    signer_pub: str


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


@app.get("/lies")
def lies():
    return _service.lies_caught()


@app.get("/health/system")
def health_system():
    return _service.health_system()


@app.post("/features")
def add_feature(f: FeatureIn, _: None = Depends(require_token)):
    return {"feature_id": _service.add_feature(f.title, f.context, f.priority)}


@app.post("/operator/register")
def register_operator(k: OperatorKey, _: None = Depends(require_token)):
    """Register an authorized signer (the CEO's operator key) — only registered keys may sign."""
    _service.manager.register_operator(k.signer_pub)
    return {"registered": True}


@app.get("/cards/{card_id}/challenge")
def challenge(card_id: str):
    """Issue a one-time nonce + the EXACT material to sign (card-id|payload-hash|nonce), so the cockpit
    signs the precise string the Manager will verify. The nonce is consumed on use → replay-proof."""
    card = _service.manager._get_card(card_id)
    if not card:
        return {"error": "unknown card"}
    nonce = _service.manager.issue_challenge(card_id)
    return {"card_id": card_id, "nonce": nonce,
            "material": _service.manager.card_material(card_id, card["payload"], nonce)}


@app.post("/approve")
def approve(s: Sig, _: None = Depends(require_token)):
    return _service.approve(s.card_id, s.signature, s.signer_pub, s.nonce)


@app.post("/reject")
def reject(s: Sig, _: None = Depends(require_token)):
    return _service.reject(s.card_id, s.signature, s.signer_pub, s.reason)
