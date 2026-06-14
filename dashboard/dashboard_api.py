"""
The DashboardAPI (PRD §6) — the Manager's externally-reachable read/sign surface on :7080. A thin
FastAPI wrapper over DashboardService; the only externally-exposed surface (behind TLS in production).

Run with:  uvicorn dashboard.dashboard_api:app --host 127.0.0.1 --port 7080
"""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from thor_http_auth import rate_limit, require_token

app = FastAPI(title="THOR DashboardAPI", version="0.1.0")


# Security response headers. frame-ancestors/X-Frame-Options:DENY stop the cockpit (esp. the Sign button —
# the operator signature is the ultimate authority) from being framed for CLICKJACKING; the CSP contains any
# XSS (defense-in-depth on top of React's escaping); nosniff/Referrer-Policy are standard hardening. The CSP
# allows exactly what the cockpit needs (self bundle, inline styles, Google Fonts, same-origin SSE).
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; object-src 'none'; form-action 'self'")
_SEC_HEADERS = {"X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "Content-Security-Policy": _CSP,
                "Permissions-Policy": "geolocation=(), microphone=(), camera=()"}


def _harden(resp):
    for k, v in _SEC_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    """Per-client rate limit on the MUTATING surface + security response headers on EVERY response."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        try:
            rate_limit(request)
        except HTTPException as exc:
            return _harden(JSONResponse({"detail": exc.detail}, status_code=exc.status_code))
    return _harden(await call_next(request))

# Allow-list for any client-supplied identifier (feature_id / command). Positive validation (invariant #7):
# blocks path traversal, shell metacharacters, refspec tricks, and unbounded-input DoS at the edge.
_IDPAT = r"^[A-Za-z0-9_-]{1,64}$"
_service = None   # set via dashboard.dashboard_api.bind(service) when the control plane boots


def bind(service) -> None:
    global _service
    _service = service


class FeatureIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=4000)
    priority: int = Field(default=3, ge=0, le=3)


class Sig(BaseModel):
    card_id: str
    signature: str
    signer_pub: str
    nonce: str | None = None   # T7: the one-time challenge bound to the card (replay defence)
    reason: str = ""


class OperatorKey(BaseModel):
    signer_pub: str
    cosign: str | None = None   # Ed25519 sig over signer_pub by an existing operator (required post-bootstrap)
    by_pub: str | None = None   # the existing operator's pubkey that produced `cosign`


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


@app.get("/threats")
def threats():
    """Live attack-detection feed — named, scored, STRIDE-tagged signatures over the recent window."""
    return _service.threats()


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


_MAX_STREAMS = int(os.environ.get("THOR_MAX_STREAMS", "128"))
_active_streams = 0


@app.get("/stream")
async def stream():
    """Real-time sync (Module 9: every head is a REMOTE HEAD on the same Manager truth). Server-Sent
    Events push a tick whenever the ledger advances (a new signed event), so the laptop AND the phone
    re-sync instantly off the ONE ledger — no second state, no drift. Read-only; reads are public.
    Concurrent streams are capped (THOR_MAX_STREAMS) so a flood of held-open connections can't exhaust the
    plane (503 when full)."""
    global _active_streams
    if _active_streams >= _MAX_STREAMS:
        return JSONResponse({"detail": "too many concurrent streams"}, status_code=503)

    async def gen():
        global _active_streams
        _active_streams += 1
        try:
            yield "event: hello\ndata: {}\n\n"        # connected
            last = -1
            while True:
                try:
                    seq = _service.manager.eventlog.count()
                except Exception:                  # noqa: BLE001 — transient DB blip: hold last, keep alive
                    seq = last
                if seq != last:
                    last = seq
                    yield f"data: {json.dumps({'seq': seq})}\n\n"
                else:
                    yield ": keep-alive\n\n"        # comment frame so proxies don't time the stream out
                await asyncio.sleep(1)
        finally:
            _active_streams -= 1

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@app.post("/features")
def add_feature(f: FeatureIn, _: None = Depends(require_token)):
    return {"feature_id": _service.add_feature(f.title, f.context, f.priority)}


@app.delete("/features/{feature_id}")
def remove_feature(feature_id: str = Path(pattern=_IDPAT), _: None = Depends(require_token)):
    """Remove a feature from the catalog (event-sourced; the ledger keeps the history)."""
    _service.manager.remove_feature(feature_id)
    return {"ok": True, "removed": feature_id}


@app.post("/features/{feature_id}/stop")
def stop_feature(feature_id: str = Path(pattern=_IDPAT), _: None = Depends(require_token)):
    """Stop work on a task: destroy its active room and move it back to 'ready' (branch + ledger kept)."""
    return _service.stop_feature(feature_id)


@app.post("/operator/register")
def register_operator(k: OperatorKey, _: None = Depends(require_token)):
    """Register an authorized signer. The transport token alone must NOT mint signing authority
    (AUD-register-authority): the FIRST operator is a token-gated trust-on-first-use bootstrap; every
    operator after that must be CO-SIGNED by an existing operator (Ed25519 over the new key)."""
    mgr = _service.manager
    if k.signer_pub in mgr.authorized_signers:
        return {"registered": True, "already": True}
    if not mgr.authorized_signers:
        mgr.register_operator(k.signer_pub)
        return {"registered": True, "bootstrap": True}
    if not (k.cosign and k.by_pub):
        return {"registered": False, "reason": "operators exist — a new key must be co-signed by an existing operator"}
    return mgr.register_operator_signed(k.signer_pub, k.cosign, k.by_pub)


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
    feature_id: str = Field(pattern=_IDPAT)
    priority: int | None = Field(default=None, ge=0, le=3)


@app.post("/commands/{command}")
def run_command(command: str = Path(pattern=r"^[a-z_]{1,32}$"), c: CmdIn = ...,
                _: None = Depends(require_token)):
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
