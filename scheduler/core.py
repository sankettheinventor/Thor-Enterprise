"""
Sub-modules 4.2–4.8 — the deterministic Scheduler core.

Pure code, zero LLM (FR-1). The schedule is a pure function of (catalog, readiness, capacity),
so it is deterministic (FR-7) and replayable (FR-13). The Scheduler instructs the Manager via a
dispatch callback; it never provisions directly (FR-8) and never calls an LLM (the CTO does).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .graph import Task, build_graph


@dataclass
class Schedule:
    waves: list[list[str]]   # ordered waves; within a wave, (level, feature_id) order

    def flatten(self) -> list[str]:
        return [f for w in self.waves for f in w]

    def to_json(self) -> str:
        return json.dumps(self.waves, separators=(",", ":"))   # byte-identical compare (AC-1/12)


class Scheduler:
    def __init__(self, tasks: list[Task], capacity: int, budget_cap: int | None = None,
                 plan_approved: bool = True) -> None:
        self.graph = build_graph(tasks)        # validates: cycles / missing deps (AC-11)
        self.capacity = capacity
        self.budget_cap = budget_cap
        self.plan_approved = plan_approved

    # ---- 4.2 Readiness Evaluator (pure boolean) ----
    def _schedulable(self, t: Task) -> bool:
        if t.task_type == "build" and not self.plan_approved:
            return False                       # Genesis-first (FR-15 / AC-9)
        return True

    # ---- 4.3 Wave Planner + 4.4 Concurrency Governor (deterministic) ----
    def plan(self) -> Schedule:
        tasks, levels = self.graph.tasks, self.graph.levels
        done = {fid for fid, t in tasks.items() if t.status == "done"}
        dispatched: set[str] = set()
        waves: list[list[str]] = []
        while True:
            ready = [t for fid, t in tasks.items()
                     if fid not in done and fid not in dispatched
                     and t.status not in ("done", "running")           # not already running (FR-3/D2)
                     and t.ready and self._schedulable(t)
                     and all(d in done for d in t.depends_on)]          # FR-3 deps done
            ready.sort(key=lambda t: (levels[t.feature_id], t.feature_id))  # stable order (D1)
            if not ready:
                break
            wave = ready[:self.capacity]                                # cap to capacity (FR-5)
            waves.append([t.feature_id for t in wave])
            for t in wave:                                              # simulate completion → next wave
                dispatched.add(t.feature_id)
                done.add(t.feature_id)
        return Schedule(waves=waves)

    # ---- 4.7 Cost Estimator + Budget Guard ----
    def cost_estimate(self, schedule: Schedule | None = None) -> int:
        schedule = schedule or self.plan()
        return sum(self.graph.tasks[f].est_tokens for f in schedule.flatten())

    def dry_run(self) -> dict:                                          # FR-12 / AC-5: no side effects
        schedule = self.plan()
        return {"waves": schedule.waves, "cost_estimate": self.cost_estimate(schedule),
                "provisioned": 0}

    # ---- 4.5 Provision Dispatcher (→ CTO → Manager; never direct) ----
    def run(self, dispatch_fn) -> dict:
        """Dispatch the immediately-runnable wave, after the budget gate. Idempotent (D2)."""
        schedule = self.plan()
        if not schedule.waves:
            return {"status": "nothing_ready", "dispatched": [], "queued": []}
        wave = schedule.waves[0]
        wave_cost = sum(self.graph.tasks[f].est_tokens for f in wave)
        if self.budget_cap is not None and wave_cost > self.budget_cap:   # FR-11 / AC-6
            return {"status": "halted_budget", "dispatched": [], "queued": wave,
                    "wave_cost": wave_cost, "cap": self.budget_cap}
        dispatched = []
        for fid in wave:
            if self.graph.tasks[fid].status == "running":               # already running → skip (AC-10)
                continue
            dispatch_fn(fid, self.graph.tasks[fid].task_type)           # → CTO plan → Manager provision
            self.graph.tasks[fid].status = "running"
            dispatched.append(fid)
        queued = schedule.flatten()[len(wave):]
        return {"status": "dispatched", "dispatched": dispatched, "queued": queued}

    # ---- 4.6 Completion Listener / state transitions ----
    def mark_ready(self, fid: str) -> None:
        self.graph.tasks[fid].ready = True
        self.graph.tasks[fid].status = "pending"

    def mark_done(self, fid: str) -> None:
        self.graph.tasks[fid].status = "done"

    def mark_rework(self, fid: str) -> None:                            # FR-14 / AC-8
        # re-enter the failed feature as ready; its done dependencies are left untouched.
        self.graph.tasks[fid].status = "pending"
        self.graph.tasks[fid].ready = True

    # ---- 4.8 / FR-17 restart: rebuild running-state from the Manager's registry ----
    def rebuild_from_manager(self, manager) -> None:
        rooms = manager.state_summary()["rooms"]
        running = {r["feature_id"] for r in rooms.values() if r["status"] == "working"}
        for fid, t in self.graph.tasks.items():
            if fid in running:
                t.status = "running"

    # ---- FR-16 Dashboard state ----
    def state(self) -> dict:
        out = {"running": [], "queued": [], "blocked": [], "done": []}
        sched = self.plan()
        queued = set(sched.flatten())
        for fid, t in sorted(self.graph.tasks.items()):
            if t.status == "running":
                out["running"].append(fid)
            elif t.status == "done":
                out["done"].append(fid)
            elif fid in queued:
                out["queued"].append(fid)
            else:
                out["blocked"].append(fid)
        return out
