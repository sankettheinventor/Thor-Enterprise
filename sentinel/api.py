"""
Sentinel REST surface (PRD §6.1) — thin, on :7140.

Run with:  uvicorn sentinel.api:app --host 127.0.0.1 --port 7140
The smoke drives the Sentinel in-process; this is the service shape for the real control plane.
"""
from __future__ import annotations

from fastapi import FastAPI

from .core import Sentinel

app = FastAPI(title="THOR Sentinel", version="0.1.0")
_sentinel = Sentinel()


def bind(sentinel: Sentinel) -> None:
    global _sentinel
    _sentinel = sentinel


@app.get("/sentinel/status")
def status():
    return _sentinel.status()


@app.get("/health")
def health():
    # the canary base case — the heartbeat; its absence is itself the alarm
    return {"self_test": _sentinel.accepts_work, "heartbeat": _sentinel.heartbeat()}
