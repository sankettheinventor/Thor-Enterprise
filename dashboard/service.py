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
    def __init__(self, manager, budget_cap: int | None = None, scheduler_factory=None,
                 selfaudit=None) -> None:
        self.manager = manager                 # the ONLY reference; no authoritative local store
        self.budget_cap = budget_cap
        self.scheduler_factory = scheduler_factory
        self.selfaudit = selfaudit             # read-only eyes — surfaced on the cockpit governance panel
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
        # GDPR Art.17: redact erased subjects from anything served (the raw chained rows are untouched).
        from compliance import erasure
        return audit.feed(erasure.redact_events(self.manager.eventlog.all_events()), feature_id)

    def audit_export(self, fmt: str = "json") -> str:
        from compliance import erasure
        return audit.export(erasure.redact_events(self.manager.eventlog.all_events()), fmt)

    def cost(self) -> dict:
        features = self.manager.list_features()
        spent = {f["feature_id"]: (f.get("est_tokens", 0) if f.get("status") not in (None, "backlog", "ready")
                                   else 0) for f in features}
        return cost.report(features, spent, self.budget_cap)

    def findings(self) -> list[dict]:
        return self.manager.list_checker_findings()

    def room_activity(self) -> dict:
        """Per-room LIVE file activity — which file each room's cook is writing (allow) or was denied,
        from the Leash's `action.decided` records. READ-ONLY; the cockpit can watch, never reach in."""
        import json
        by_room: dict[str, list] = {}
        for e in self.manager.eventlog.all_events():
            if e["event_type"] != "action.decided":
                continue
            p = json.loads(e["payload"])
            act = p.get("action") or {}
            by_room.setdefault(p.get("room_id") or "unknown", []).append(
                {"seq": e["seq"], "file": act.get("target"), "tool": act.get("name") or act.get("type"),
                 "decision": p.get("decision"), "reason": p.get("reason")})
        return {rid: items[-12:][::-1] for rid, items in by_room.items()}   # most-recent 12 per room

    # progress ladder (event-sourced status): where each feature sits in the SDLC
    _LADDER = ("backlog", "ready", "building", "in_qa", "awaiting_signature", "done")

    def feature_progress(self) -> list[dict]:
        """Task / SDLC / feature progress — where each feature sits on the line, from the projected
        status (not a cook's claim), with its open-bug count."""
        out = []
        for f in self.manager.list_features():
            status = f.get("status") or "backlog"
            idx = self._LADDER.index(status) if status in self._LADDER else 0
            open_bugs = sum(1 for b in self.manager.list_bugs(f["feature_id"]) if b.get("status") == "open")
            row = {"feature_id": f["feature_id"], "title": f.get("title") or f["feature_id"],
                   "status": status, "stage": idx, "stages": list(self._LADDER),
                   "priority": f.get("priority") if f.get("priority") is not None else 3,
                   "progress": round(100 * idx / (len(self._LADDER) - 1)), "open_bugs": open_bugs}
            for k in ("summary", "acceptance_criteria", "tasks", "qa_cases", "depends_on"):  # Genesis plan data
                if f.get(k):
                    row[k] = f[k]
            out.append(row)
        return sorted(out, key=lambda x: (-x["progress"], x["feature_id"]))

    def bugs(self) -> list[dict]:
        """Every bug found across the line — the 'new bugs found' feed (QA + checker)."""
        return self.manager.all_bugs()

    def commands(self) -> dict:
        """What the PHONE is allowed to do — the bounded command allowlist (Module 9.5). Anything else
        (reach into a room, change rules, bypass governance) is rejected by design."""
        from mobile.allowlist import ALLOWED
        return {"allowed": sorted(ALLOWED)}

    def lies_caught(self) -> dict:
        """The cockpit's honesty meter: every caught lie (dishonesty.caught), grouped by container."""
        import json
        by_container: dict[str, int] = {}
        recent: list[dict] = []
        for e in self.manager.eventlog.all_events():
            if e["event_type"] == "dishonesty.caught":
                p = json.loads(e["payload"])
                c = p.get("container") or p.get("room_id") or "unknown"
                by_container[c] = by_container.get(c, 0) + 1
                recent.append({"container": c, "feature_id": p.get("feature_id"),
                               "signals": p.get("signals", [])})
        return {"total": sum(by_container.values()), "by_container": by_container,
                "recent": recent[-10:]}

    def health_system(self) -> dict:
        """Live governance health for the cockpit: Sentinel (halt state, alarms) + Self-Audit (its local
        model, ZERO frontier calls, meta-trust). Real now — no longer hardcoded."""
        s = getattr(self.manager, "sentinel", None)
        sentinel = {"alive": True, "fail_closed": True,
                    "halted": bool(getattr(s, "halted", False)),
                    "alarms": len(s.alarms) if s is not None else 0}
        sa, mt = {}, 0.97
        if self.selfaudit is not None:
            try:
                h = self.selfaudit.health()
                sa = {"model": h.get("model"), "frontier_calls": h.get("frontier_calls", 0),
                      "loaded": h.get("model_loaded")}
                m = self.selfaudit.meta_trust()
                if m:
                    mt = m["score"]
            except Exception:  # noqa: BLE001 — Self-Audit is advisory; never break the cockpit
                pass
        return {"sentinel": sentinel, "self_audit_meta_trust": mt, "self_audit": sa}

    # ---- writes: direction + signatures only (each recorded as an operator action, FR-15) ----
    def _action(self, action: str, detail: dict) -> None:
        self.manager._record("dashboard.action", {"action": action, **detail}, actor="operator")

    def add_feature(self, title: str, context: str = "", priority: int = 3, est_tokens: int = 1000) -> str:
        fid = "F" + uuid.uuid4().hex[:4].upper()
        self.manager.add_feature(fid, title, context, priority, est_tokens)
        self._action("add_feature", {"feature_id": fid})
        return fid

    def genesis(self, idea: str) -> dict:
        """Genesis (Bible §10) — a CORE capability for ANY project: the real planner turns an idea into the
        feature catalog (features → tasks → QA → P0/P1/P2 → dependencies), written through THIS Manager (the
        sole ledger writer). Long-running (a real planning agent in a sealed room) — call in a background
        thread; the features appear on the board as they land."""
        from tools.genesis import _PR, _ctx_for, plan_project
        plan, _repo = plan_project(idea)
        feats = []
        for f in plan.get("features", []):
            fid = self.add_feature(f.get("title", "feature"), _ctx_for(f, plan.get("vision", "")),
                                   _PR.get(f.get("priority"), 3))
            feats.append({"feature_id": fid, "title": f.get("title"), "priority": f.get("priority")})
        self.manager._record("genesis.planned", {"vision": plan.get("vision", "")[:500], "feature_count": len(feats)})
        return {"vision": plan.get("vision", ""), "features": feats}

    def mark_ready(self, feature_id: str) -> None:
        self.manager.set_feature_status(feature_id, "ready")
        self._action("mark_ready", {"feature_id": feature_id})

    def approve(self, card_id: str, signature_b64: str, signer_pub_b64: str,
                nonce: str | None = None) -> dict:
        if not self.connected():
            return {"verified": False, "reason": "disconnected — cannot sign against a stale picture"}
        result = self.manager.approve(card_id, signature_b64, signer_pub_b64, nonce=nonce)
        self._action("approve", {"card_id": card_id, "verified": result["verified"]})
        if result["verified"]:
            card = self.manager._get_card(card_id)
            if card and card["type"] == "merge":   # a verified Signature 3 drives the REAL merge (T6)
                result["merge"] = self._drive_merge(card)
        return result

    def _drive_merge(self, card: dict) -> dict:
        """Signature 3 verified → the real merge via T6's direct_merge, but ONLY if the verdict is
        still FRESH (R9 — the branch HEAD hasn't moved since the verdict). Else refuse, card stays done."""
        p = card.get("payload", {})
        repo, branch, snap = p.get("repo"), p.get("branch"), p.get("snapshot_sha")
        if not (repo and branch):
            return {"merged": False, "reason": "merge card has no repo/branch context"}
        from govengine import reality
        try:
            fresh = snap is None or reality.head_sha(repo, branch) == snap
        except reality.RealityError:
            fresh = False
        if not fresh:
            return {"merged": False, "reason": "verdict stale (branch moved) — re-run before merge (R9)"}
        return self.manager.direct_merge(repo, branch, card["feature_id"], signature_ref=card["card_id"])

    def reject(self, card_id: str, signature_b64: str, signer_pub_b64: str,
               nonce: str | None = None, reason: str = "") -> dict:
        if not self.connected():
            return {"verified": False, "reason": "disconnected — cannot sign against a stale picture"}
        result = self.manager.reject_card(card_id, signature_b64, signer_pub_b64, nonce=nonce, reason=reason)
        self._action("reject", {"card_id": card_id, "verified": result["verified"]})
        return result

    def stop_feature(self, feature_id: str) -> dict:
        """Stop work on a task: destroy any active room for the feature (physical halt) and move it back
        to 'ready'. The branch + ledger are preserved; only the running container goes."""
        # Halt EVERY live room for the feature, whatever its status string — a build room mid-exec may not
        # read literally "working", and leaving it alive while the feature is re-scheduled would let a NEW
        # cook run against the SAME worktree (git corruption) (AUD-stop-status). Only flip to 'ready' if
        # the halt actually succeeded; otherwise surface that nothing was stopped (fail-loud, not silent).
        stopped, failed = [], []
        for rid, r in self.manager.state_summary()["rooms"].items():
            if r.get("feature_id") == feature_id and r.get("status") != "destroyed":
                try:
                    self.manager.destroy_room(rid)
                    stopped.append(rid)
                except Exception:  # noqa: BLE001 — record the failure; do NOT re-schedule over a live room
                    failed.append(rid)
        if not failed:
            self.manager.set_feature_status(feature_id, "ready")
        self._action("stop", {"feature_id": feature_id, "rooms": stopped, "failed": failed})
        return {"ok": not failed, "stopped": stopped, "failed": failed}

    def threats(self) -> dict:
        """Live attack-signal scan (READ-ONLY) for the cockpit's 'attacks detected' panel — names + scores
        the current denial/forgery/tamper signatures. The recording+escalating run is the Sentinel's."""
        from sentinel.threat_detector import ThreatDetector
        return {"threats": ThreatDetector(self.manager).scan()}

    def metrics(self) -> str:
        """Prometheus text-format metrics for observability (scrape `/metrics`). Aggregate operational
        counters only — no per-cook payloads — so it is safe to expose to a scraper. Every metric is
        computed defensively: a faulty source contributes nothing rather than breaking the scrape."""
        lines: list[str] = []

        def g(name: str, help_: str, value, labels: str = "") -> None:
            lines.append(f"# HELP {name} {help_}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{{{labels}}} {value}" if labels else f"{name} {value}")

        def safe(fn, default=0):
            try:
                return fn()
            except Exception:  # noqa: BLE001 — one bad source must not break the whole scrape
                return default

        g("thor_connected", "1 if the control plane is connected to its ledger",
          int(bool(safe(lambda: self.connected(), False))))
        g("thor_ledger_events_total", "rows in the tamper-evident event ledger",
          safe(lambda: self.manager.eventlog.count()))
        g("thor_rooms_active", "live (non-destroyed) rooms", safe(lambda: len(self.rooms_live())))
        feats = safe(lambda: self.manager.list_features(), [])
        g("thor_features_total", "features in the catalog", len(feats))
        by_status: dict[str, int] = {}
        for f in feats:
            by_status[f.get("status") or "backlog"] = by_status.get(f.get("status") or "backlog", 0) + 1
        for st, n in sorted(by_status.items()):
            g("thor_features_by_status", "features by SDLC status", n, labels=f'status="{st}"')
        g("thor_lies_caught_total", "caught dishonest-cook events", safe(lambda: self.lies_caught()["total"]))
        g("thor_threats_active", "current named attack signatures over the window",
          safe(lambda: len(self.threats()["threats"])))
        g("thor_bugs_total", "bugs found across the line (QA + checker)", safe(lambda: len(self.bugs())))
        health = safe(lambda: self.health_system(), {})
        g("thor_sentinel_halted", "1 if the Sentinel has halted the plane",
          int(bool((health.get("sentinel") or {}).get("halted"))))
        g("thor_frontier_calls_total", "frontier-model API calls (MUST stay 0 — zero token cost)",
          safe(lambda: (health.get("self_audit") or {}).get("frontier_calls", 0)))
        return "\n".join(lines) + "\n"

    def dry_run(self) -> dict:
        if self.scheduler_factory is None:
            return {"waves": [], "cost_estimate": 0, "provisioned": 0}
        ready = [f for f in self.manager.list_features() if f.get("status") == "ready"]
        sched = self.scheduler_factory(ready)
        return sched.dry_run()


def _verify(manager, card_id, card, pub, sig) -> bool:
    from manager.core import _verify_sig
    return _verify_sig(pub, sig, manager.card_material(card_id, card["payload"]))
