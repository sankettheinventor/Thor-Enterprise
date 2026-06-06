"""
Sub-module 11.1 Inspector Loop + 11.5 Anomaly Detector (the observe step).

Reads the EventLog (read-only) and reduces it to SYSTEM-level observations — verdict outcomes,
divergence count, QA failures, component alarms — that the model assesses for correctness drift.
Observational, not a heavy batch job; bounded (FR-16).
"""
from __future__ import annotations

import json


def observe(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    verdict_total = verdict_escalate = not_done = done = divergence = qa = alarms = 0
    for e in events:
        et = e["event_type"]
        counts[et] = counts.get(et, 0) + 1
        if et == "verdict.computed":
            verdict_total += 1
            v = json.loads(e["payload"]).get("verdict")
            if v == "escalate":
                verdict_escalate += 1
            elif v == "not_done":
                not_done += 1
            elif v == "done":
                done += 1
        elif et == "divergence.detected":
            divergence += 1
        elif et == "qa.finding":
            qa += 1
        elif et == "sentinel.alarm":
            alarms += 1
    return {"counts": counts, "verdict_total": verdict_total, "verdict_escalate": verdict_escalate,
            "not_done": not_done, "done": done, "divergence": divergence, "qa_findings": qa,
            "alarms": alarms, "events_scanned": len(events)}
