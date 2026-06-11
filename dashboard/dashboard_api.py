"""
The DashboardAPI (PRD §6) — the Manager's externally-reachable read/sign surface on :7080. A thin
FastAPI wrapper over DashboardService; the only externally-exposed surface (behind TLS in production).

Run with:  uvicorn dashboard.dashboard_api:app --host 127.0.0.1 --port 7080
"""
from __future__ import annotations

import asyncio
import json

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse, StreamingResponse
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


@app.get("/rooms/activity")
def rooms_activity():
    """Per-room LIVE file activity — which file each room's cook is writing/was denied (from the Leash)."""
    return _service.room_activity()


@app.get("/progress")
def progress():
    """Task / SDLC / feature progress — where every feature sits on the line, event-sourced."""
    return {"features": _service.feature_progress()}


@app.get("/bugs")
def bugs():
    """Every bug found across the line (QA + checker) — the 'new bugs found' feed."""
    return {"bugs": _service.bugs()}


@app.get("/commands")
def commands():
    """What the phone is ALLOWED to do — the bounded command allowlist (Module 9.5)."""
    return _service.commands()


@app.get("/stream")
async def stream():
    """Real-time sync (Module 9: every head is a REMOTE HEAD on the same Manager truth). Server-Sent
    Events push a tick whenever the ledger advances (a new signed event), so the laptop AND the phone
    re-sync instantly off the ONE ledger — no second state, no drift. Read-only; reads are public."""
    async def gen():
        yield "event: hello\ndata: {}\n\n"        # connected
        last = -1
        while True:
            try:
                seq = _service.manager.eventlog.count()
            except Exception:                      # noqa: BLE001 — transient DB blip: hold last, keep stream alive
                seq = last
            if seq != last:
                last = seq
                yield f"data: {json.dumps({'seq': seq})}\n\n"
            else:
                yield ": keep-alive\n\n"           # comment frame so proxies don't time the stream out
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@app.post("/features")
def add_feature(f: FeatureIn, _: None = Depends(require_token)):
    return {"feature_id": _service.add_feature(f.title, f.context, f.priority)}


@app.delete("/features/{feature_id}")
def remove_feature(feature_id: str, _: None = Depends(require_token)):
    """Remove a feature from the catalog (event-sourced; the ledger keeps the history)."""
    _service.manager.remove_feature(feature_id)
    return {"ok": True, "removed": feature_id}


@app.post("/features/{feature_id}/stop")
def stop_feature(feature_id: str, _: None = Depends(require_token)):
    """Stop work on a task: destroy its active room and move it back to 'ready' (branch + ledger kept)."""
    return _service.stop_feature(feature_id)


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
    return _service.reject(s.card_id, s.signature, s.signer_pub, s.nonce, s.reason)


class CmdIn(BaseModel):
    feature_id: str
    priority: int | None = None


@app.post("/commands/{command}")
def run_command(command: str, c: CmdIn, _: None = Depends(require_token)):
    """Phone command parity — but ONLY the bounded allowlist (Module 9.5: the most-exposed device gets
    the least catastrophic power). Anything outside the allowlist is refused; reaching into a room or
    bypassing governance is impossible from here by design."""
    from mobile.allowlist import allowed
    if not allowed(command):
        return {"ok": False, "reason": f"'{command}' is not in the phone allowlist"}
    if command == "mark_ready":
        _service.mark_ready(c.feature_id)
        return {"ok": True, "command": command, "feature_id": c.feature_id}
    if command == "prioritize":
        _service.manager.set_feature_priority(c.feature_id, c.priority if c.priority is not None else 1)
        return {"ok": True, "command": command, "feature_id": c.feature_id, "priority": c.priority}
    # add_feature/approve/reject have dedicated, signature-gated endpoints
    return {"ok": False, "reason": f"use the dedicated endpoint for '{command}'"}


class PushSub(BaseModel):
    endpoint: str
    keys: dict


@app.get("/push/vapid")
def push_vapid():
    """The application server key the phone uses to subscribe to native push (Web Push / VAPID)."""
    from dashboard import push
    return {"key": push.public_key()}


@app.post("/push/subscribe")
def push_subscribe(sub: PushSub):
    """Store a device's push subscription so THOR can alert it when a card needs a signature."""
    from dashboard import push
    return {"ok": True, "subscribers": push.subscribe(sub.model_dump())}


@app.post("/push/test")
def push_test(_: None = Depends(require_token)):
    """Send a THOR-styled test notification to all subscribed devices."""
    from dashboard import push
    return push.send("THOR", "Your cockpit is connected — notifications are on.", "/app/")
