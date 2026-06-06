"""
The DashboardService — the read-and-sign logic of the PM Surface (sub-modules 8.2/8.3/8.4/8.8/8.9).

A WINDOW, NOT A BRAIN (FR-8): its ONLY state is a reference to the Manager. Every read is a projection
from the Manager; every write is either direction (add/ready a feature) or a signature, and every
write is recorded as an event by the Manager (FR-15). On disconnect it refuses to sign (never against
a stale picture — FR-16). It exposes NO way to reach into a room (FR-4 — watching is not touching).
"""
from __future__ import annotations

import uuid

from . import audit, cost, kanban, legible


class DashboardService:
    def __init__(self, manager, budget_cap: int | None = None, scheduler_factory=None) -> None:
        self.manager = manager                 # the ONLY reference; no authoritative local store
        self.budget_cap = budget_cap
        self.scheduler_factory = scheduler_factory
        self._disconnected = False             # set when the Manager is unreachable (FR-16)

    # ---- connection state (a window over the one truth) ----
    def set_disconnected(self, value: bool) -> None:
        self._disconnected = value

    def connected(self) -> bool:
        if self._disconnected:
            return False
        try:
            with self.manager.conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    # ---- reads (projections) ----
    def state_summary(self) -> dict:
        if not self.connected():
            return {"connected": False, "message": "disconnected — data may be out of date"}
        return {"connected": True, "features": self.manager.list_features(),
                "rooms": list(self.manager.state_summary()["rooms"].values()),
                "open_cards": self.cards(), "health": self.health_system()}

    def kanban(self) -> dict:
        return kanban.project(self.manager.list_features())

    def rooms_live(self) -> list[dict]:
        rooms = self.manager.state_summary()["rooms"]
        return [{"room_id": rid, "feature_id": r["feature_id"], "stage": r["task_type"],
                 "status": r["status"], "cost_so_far": 0} for rid, r in rooms.items()]

    def room_logs(self, room_id: str) -> dict:
        # READ-ONLY (FR-4). There is deliberately NO method to modify or reach into a room.
        return {"room_id": room_id, "log_lines": ["(read-only log stream)"], "writable": False}

    def cards(self) -> list[dict]:
        with self.manager.conn.cursor() as cur:
            cur.execute("SELECT card_id,type,feature_id,payload,status FROM cards "
                        "WHERE status IN ('open','held') ORDER BY created_at")
            import json
            out = []
            for r in cur.fetchall():
                payload = json.loads(r[3]) if r[3] else {}
                reason = payload.get("reason") or r[1]
                out.append({"card_id": r[0], "type": r[1], "feature_id": r[2],
                            "legible_reason": legible.render(str(reason), r[2]), "status": r[4]})
            return out

    def audit_feed(self, feature_id: str | None = None) -> list[dict]:
        return audit.feed(self.manager.eventlog.all_events(), feature_id)

    def audit_export(self, fmt: str = "json") -> str:
        return audit.export(self.manager.eventlog.all_events(), fmt)

    def cost(self) -> dict:
        features = self.manager.list_features()
        spent = {f["feature_id"]: (f.get("est_tokens", 0) if f.get("status") not in (None, "backlog", "ready")
                                   else 0) for f in features}
        return cost.report(features, spent, self.budget_cap)

    def findings(self) -> list[dict]:
        return self.manager.list_checker_findings()

    def health_system(self) -> dict:
        # Sentinel (M10) + Self-Audit meta-trust (M11) are stubbed until those modules land.
        return {"sentinel": {"alive": True, "fail_closed": True}, "self_audit_meta_trust": 0.97}

    # ---- writes: direction + signatures only (each recorded as an operator action, FR-15) ----
    def _action(self, action: str, detail: dict) -> None:
        self.manager.eventlog.append("dashboard.action", {"action": action, **detail}, actor="operator")

    def add_feature(self, title: str, context: str = "", priority: int = 3, est_tokens: int = 1000) -> str:
        fid = "F" + uuid.uuid4().hex[:4].upper()
        self.manager.add_feature(fid, title, context, priority, est_tokens)
        self._action("add_feature", {"feature_id": fid})
        return fid

    def mark_ready(self, feature_id: str) -> None:
        self.manager.set_feature_status(feature_id, "ready")
        self._action("mark_ready", {"feature_id": feature_id})

    def approve(self, card_id: str, signature_b64: str, signer_pub_b64: str) -> dict:
        if not self.connected():
            return {"verified": False, "reason": "disconnected — cannot sign against a stale picture"}
        result = self.manager.approve(card_id, signature_b64, signer_pub_b64)
        self._action("approve", {"card_id": card_id, "verified": result["verified"]})
        if result["verified"]:
            # a verified merge-card signature drives the real merge (Signature 3 → merge).
            card = self.manager._get_card(card_id)
            if card and card["type"] == "merge":
                fid = card["feature_id"]
                self.manager.eventlog.append("feature.merged", {"feature_id": fid}, feature_id=fid)
                self.manager.set_feature_status(fid, "done")
        return result

    def reject(self, card_id: str, signature_b64: str, signer_pub_b64: str, reason: str = "") -> dict:
        if not self.connected():
            return {"verified": False, "reason": "disconnected — cannot sign against a stale picture"}
        card = self.manager._get_card(card_id)
        verified = bool(card) and _verify(self.manager, card_id, card, signer_pub_b64, signature_b64)
        self._action("reject", {"card_id": card_id, "reason": reason})
        return {"verified": verified}

    def dry_run(self) -> dict:
        if self.scheduler_factory is None:
            return {"waves": [], "cost_estimate": 0, "provisioned": 0}
        ready = [f for f in self.manager.list_features() if f.get("status") == "ready"]
        sched = self.scheduler_factory(ready)
        return sched.dry_run()


def _verify(manager, card_id, card, pub, sig) -> bool:
    from manager.core import _verify_sig
    return _verify_sig(pub, sig, manager.card_material(card_id, card["payload"]))
