"""
Sub-module 8.1 — Kanban projection. Maps the Manager's feature states to the cockpit columns
(FR-1). A pure projection — no truth of its own.
"""
from __future__ import annotations

COLUMNS = ("backlog", "ready", "building", "in_qa", "awaiting_signature", "done")

# feature.status value -> kanban column
_STATUS_TO_COLUMN = {
    "backlog": "backlog", "ready": "ready", "building": "building", "working": "building",
    "in_qa": "in_qa", "qa": "in_qa", "awaiting_signature": "awaiting_signature",
    "merge_pending": "awaiting_signature", "done": "done", "merged": "done",
}


def project(features: list[dict]) -> dict:
    columns: dict[str, list] = {c: [] for c in COLUMNS}
    for f in features:
        col = _STATUS_TO_COLUMN.get(f.get("status", "backlog"), "backlog")
        columns[col].append({"feature_id": f["feature_id"], "title": f.get("title"),
                             "priority": f.get("priority")})
    return {"columns": columns}
