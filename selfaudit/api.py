"""
Self-Audit REST surface (PRD §6.1) — thin, on :7150.

Run with:  uvicorn selfaudit.api:app --host 127.0.0.1 --port 7150
The smoke drives the SelfAudit in-process; this is the service shape for the real control plane.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI

from thor_http_auth import require_token

app = FastAPI(title="THOR Self-Audit", version="0.1.0")
_sa = None


def bind(sa) -> None:
    global _sa
    _sa = sa


@app.get("/selfaudit/reports")
def reports():
    return {"reports": _sa.reports()}


@app.get("/selfaudit/meta_trust")
def meta_trust():
    return _sa.meta_trust()


@app.post("/selfaudit/benchmark/run")
def benchmark(_: None = Depends(require_token)):
    return _sa.run_benchmark()


@app.get("/health")
def health():
    return _sa.health()
