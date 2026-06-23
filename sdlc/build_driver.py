"""
Sub-module 7.10 — the LIVE build driver + loop (Integration PRD FLOW A, in the control plane).

This is the keystone that makes the control plane DRIVE builds itself — the single-writer way. A feature
the human marked `ready` flows through FLOW A entirely through the ONE Manager:

    ready -> building -> (cook builds in a sealed room) -> in_qa -> verdict-from-reality
          -> done? raise a MERGE card (Signature 3 pending) + awaiting_signature   [human signs in the cockpit
                                                                                    -> service.approve merges]
          -> not done? back to ready (honest — THOR never merges unproven work)

Run as a background loop inside start_thor when THOR_PROJECT_REPO points at the project's git worktree.
The cook + the verdict are language-agnostic (THOR_COOK / THOR_VERIFY_IMAGE). The loop never writes the
ledger directly — every state change goes through the Manager (so the chain stays single-writer/intact).
"""
from __future__ import annotations

import re
import threading


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (s or "feature").lower())).strip("-")[:40] or "feature"


def _slice_for(feature: dict) -> dict:
    """Turn a catalog feature (title + Genesis acceptance_criteria/tasks) into a buildable slice with a
    per-feature file scope (the Leash freezes the cook to exactly these paths)."""
    fid = feature["feature_id"]
    slug = _slug(feature.get("title", fid))
    code = f"src/features/{slug}.js"
    test = f"src/features/{slug}.test.mjs"
    crit = feature.get("acceptance_criteria") or [feature.get("summary") or feature.get("title") or fid]
    desc = (f"{feature.get('title', fid)}. Acceptance: " + " ".join(crit[:4]) +
            f" Put the implementation in {code} (ESM named exports) and a runnable test in {test} that imports "
            f"it and asserts the behaviour. The test is executed as `node {test}` (NOT a framework) — its "
            f"assertions must RUN at module level and print 'ok' at the end.")
    return {"feature_id": fid, "task_type": "build", "acceptance_criteria": [desc],
            "scope_files": [code, test], "planned_test": test, "regression_file": test, "code_file": code}


def run_feature(manager, feature: dict, repo: str) -> str:
    """Drive ONE feature through FLOW A via the Manager. Returns the verdict ('done'|'not_done'|'error')."""
    fid = feature["feature_id"]
    from contract.seam import Seam
    from contract.slice_builder import build_slice
    from contract.transport import InProcessTransport
    from sdlc.stages import BuildStage
    slice_ = _slice_for(feature)
    try:
        # PM/Contract: record the TRUSTED task slice (scope + test_file) the verdict judges against. The
        # actor never supplies this — the Coordinator reads it back from this signed assign_task event.
        seam = Seam(InProcessTransport(), manager=manager)
        seam.manager_send("assign_task", {"room_id": f"room-assign-{fid}",
                          "feature_slice": build_slice(slice_, {"scope_files": slice_["scope_files"]}).model_dump()})
        manager.set_feature_status(fid, "building")
        out = BuildStage().execute(feature=slice_, repo=repo, manager=manager)
        if not out.get("_edge_ok", True):                  # no branch / no claim_done — nothing to judge
            manager.set_feature_status(fid, "ready")
            return "not_done"
        branch = out["branch"]
        manager.set_feature_status(fid, "in_qa")
        result = manager.run_verdict(fid, branch, repo)
        verdict = result.get("verdict")
        if verdict == "done":
            # raise the Signature-3 merge card carrying repo/branch/snapshot — the cockpit Sign drives the
            # real, freshness-checked merge (service._drive_merge). THOR decides; the human signs; Gitea executes.
            manager.raise_card("merge", fid, {"feature_id": fid, "repo": repo, "branch": branch,
                                              "snapshot_sha": result.get("snapshot_sha")})
            manager.set_feature_status(fid, "awaiting_signature")
        else:
            manager.set_feature_status(fid, "ready")   # honest: unproven work returns to the queue
        return verdict or "not_done"
    except Exception as e:  # noqa: BLE001 — a build failure must not kill the loop; it returns to ready
        try:
            manager._record("build.error", {"feature_id": fid, "error": str(e)[:300]}, feature_id=fid)
            manager.set_feature_status(fid, "ready")
        except Exception:  # noqa: BLE001
            pass
        return "error"


class BuildLoop:
    """The deterministic dispatch loop (Scheduler doctrine: zero-LLM sequencing). Picks `ready` features and
    drives each through FLOW A, one capacity-slot at a time, on the control plane's single Manager."""

    def __init__(self, manager, repo: str, capacity: int = 1, interval: float = 5.0) -> None:
        self.manager, self.repo, self.capacity, self.interval = manager, repo, capacity, interval
        self._stop = threading.Event()
        self._running: set[str] = set()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="thor-build-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if len(self._running) < self.capacity:
                    ready = [f for f in self.manager.list_features() if f.get("status") == "ready"]
                    for f in ready[: self.capacity - len(self._running)]:
                        self._dispatch(f)
            except Exception:  # noqa: BLE001 — never let a transient error kill the loop
                pass
            self._stop.wait(self.interval)

    def _dispatch(self, feature: dict) -> None:
        fid = feature["feature_id"]
        self._running.add(fid)

        def _work():
            try:
                run_feature(self.manager, feature, self.repo)
            finally:
                self._running.discard(fid)

        threading.Thread(target=_work, name=f"thor-build-{fid}", daemon=True).start()


_LOOP: BuildLoop | None = None


def start_build_loop(manager, repo: str, capacity: int = 1) -> BuildLoop:
    """Start the singleton build loop (idempotent)."""
    global _LOOP
    if _LOOP is None:
        _LOOP = BuildLoop(manager, repo, capacity=capacity)
        _LOOP.start()
    return _LOOP
