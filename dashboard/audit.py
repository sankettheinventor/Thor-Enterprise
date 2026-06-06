"""
Sub-module 8.5 — Audit Feed & Log (FR-9 / AC-9).

The activity stream is a projection of the Manager's EventLog: every decision, verdict, signature,
and lifecycle event. Filterable and exportable (CSV/JSON) for a defensible compliance record.
"""
from __future__ import annotations

import csv
import io
import json


def feed(events: list[dict], feature_id: str | None = None, limit: int = 500) -> list[dict]:
    out = [{"seq": e["seq"], "ts": e["ts"], "actor": e["actor"], "event_type": e["event_type"],
            "feature_id": e.get("feature_id")} for e in events
           if feature_id is None or e.get("feature_id") == feature_id]
    return out[-limit:]


def export(events: list[dict], fmt: str = "json") -> str:
    rows = feed(events, limit=10**9)
    if fmt == "json":
        return json.dumps(rows, separators=(",", ":"))
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["seq", "ts", "actor", "event_type", "feature_id"])
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()
    raise ValueError(f"unknown export format: {fmt}")
