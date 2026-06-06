"""
The GovernanceEngine — orchestrator (6.1 Probe Runner) + 6.9 Verdict Recorder + canary + freshness.

run_verdict() computes a verdict from reality, deterministically (FR-10) and read-only (FR-4), and
FAILS CLOSED (FR-15): any inability to read reality → `escalate`, never a false `done`. It returns
the verdict to the Manager and records it as a signed event (AC-11). The engine never merges, never
writes code, never marks anything done itself — it only judges.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from . import divergence as div_mod
from . import panel
from . import probes as probes_mod
from . import reality

# Changes to these are stakes-tiered "high" → human signature even if all probes pass (FR-9).
DEP_MANIFESTS = ("package.json", "package-lock.json", "requirements.txt", "pyproject.toml",
                 "go.mod", "Cargo.toml", "Gemfile", "pom.xml")


@dataclass
class VerdictContext:
    feature_id: str
    branch: str
    repo: str
    contract: dict
    claim: dict = field(default_factory=dict)        # the agent's UNTRUSTED self-report
    manager: object | None = None
    base_branch: str = "main"
    commit_window: tuple | None = None
    skill_results_ok: bool = True                    # R1 (CTO skills) — stubbed input until CTO module


def _stakes(contract: dict, changed: set[str]) -> str:
    protected = set(contract.get("protected_files", []))
    for f in changed:
        if f in protected or f.rsplit("/", 1)[-1] in DEP_MANIFESTS:
            return "high"
    return "normal"


class GovernanceEngine:
    def __init__(self, manager=None) -> None:
        self.manager = manager

    def run_verdict(self, ctx: VerdictContext) -> dict:
        ctx.manager = ctx.manager or self.manager
        try:                                          # fail-closed wrapper (FR-15 / AC-8)
            probe_results = probes_mod.run_all(ctx)
            changed = reality.changed_files(ctx.repo, ctx.branch, ctx.base_branch)
            m1_pass = next(x for x in probe_results if x.name == "M1").passed
            gate_hits = len(reality.gate_hits(ctx.manager, ctx.commit_window))
            d = div_mod.detect(ctx.claim, changed, m1_pass, gate_hits)
            stakes = _stakes(ctx.contract, changed)
            verdict = panel.adjudicate(probe_results, d, stakes)
            snapshot = reality.head_sha(ctx.repo, ctx.branch)
        except reality.RealityError as e:
            verdict = panel.adjudicate([], None, "normal", errors=[f"reality unreadable: {e}"])
            probe_results, d, snapshot = [], None, None

        result = self._format(ctx, verdict, probe_results, d, snapshot)
        self._record(ctx, result)                     # 6.9 Verdict Recorder
        return result

    def _format(self, ctx, v, probe_results, d, snapshot) -> dict:
        probes_map = {p.name: {"pass": p.passed, "evidence": p.evidence} for p in probe_results}
        deterministic_hash = hashlib.sha256(json.dumps({          # FR-10 — pure function of reality
            "verdict": v.verdict,
            "probes": {k: probes_map[k]["pass"] for k in sorted(probes_map)},
            "blockers": sorted(b[0] for b in v.blockers) if v.blockers else [],
            "divergence": sorted(d.signals) if (d and d.found) else [],
            "stakes": v.stakes,
        }, sort_keys=True).encode()).hexdigest()
        return {
            "feature_id": ctx.feature_id, "branch": ctx.branch, "verdict": v.verdict,
            "probes": probes_map,
            "blockers": [{"probe": b[0], "detail": b[1]} for b in v.blockers],
            "divergence": {"found": bool(d and d.found), "signals": (d.signals if d else [])},
            "stakes": v.stakes, "reason": v.reason,
            "snapshot_sha": snapshot, "deterministic_hash": deterministic_hash,
        }

    def _record(self, ctx, result) -> None:           # AC-11 — verdict + divergence are signed events
        if ctx.manager is None:
            return
        ctx.manager.eventlog.append("verdict.computed", {
            "feature_id": result["feature_id"], "verdict": result["verdict"],
            "blockers": result["blockers"], "deterministic_hash": result["deterministic_hash"]},
            actor="govengine", feature_id=ctx.feature_id)
        if result["divergence"]["found"]:
            ctx.manager.eventlog.append("divergence.detected", {
                "feature_id": result["feature_id"], "signals": result["divergence"]["signals"]},
                actor="govengine", feature_id=ctx.feature_id)

    def is_fresh(self, prior_result: dict, ctx: VerdictContext) -> bool:   # FR-11 / AC-7
        """A verdict is stale if the branch HEAD moved since it was computed."""
        try:
            return prior_result.get("snapshot_sha") == reality.head_sha(ctx.repo, ctx.branch)
        except reality.RealityError:
            return False

    def canary_status(self, canary_ctx: VerdictContext) -> dict:           # FR-14 / AC-9
        """The canary is deliberately incomplete; its verdict MUST be not_done, proving detection."""
        r = self.run_verdict(canary_ctx)
        return {"canary_feature": canary_ctx.feature_id, "expected": "not_done",
                "actual": r["verdict"], "healthy": r["verdict"] == "not_done"}
