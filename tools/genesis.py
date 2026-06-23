"""
genesis — THOR's planning brain (Bible §10). An IDEA becomes the COMPLETE feature catalog: features ->
tasks -> QA cases -> P0/P1/P2 -> dependency order, produced by the real planner (your Claude, reusing your
existing login — no API cost), written to the catalog through the ONE Manager (sole writer), and gated
behind Signature 1 (the human approves the plan before anything builds).

  python tools/genesis.py "<your project idea>"

The plan is generated inside a sealed one-door room (the planner only reaches the model host; the Leash
governs its writes). It writes plan.json; THOR reads it, writes the catalog, and raises the Sig-1 plan card.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid

_SCHEMA = ('{"vision": "<one paragraph>", "features": [{"title": "<short name>", "summary": "<one line>", '
           '"priority": "P0|P1|P2", "acceptance_criteria": ["<testable criterion>", ...], '
           '"tasks": ["<task>", ...], "qa_cases": ["<QA test case>", ...], '
           '"depends_on": ["<other feature title>", ...]}]}')


def genesis_prompt(idea: str) -> str:
    return (
        "You are THOR's planning brain — PM + CTO + UX strategy combined. Plan this project COMPLETELY.\n\n"
        f"PROJECT IDEA:\n{idea}\n\n"
        "Write the plan ONLY to the file plan.json (write nothing else). Exact JSON schema:\n" + _SCHEMA + "\n\n"
        "Rules: break the project into the RIGHT set of features (not too coarse, not too fine). "
        "P0 = must-have to launch, P1 = important, P2 = nice-to-have. Every feature gets concrete TESTABLE "
        "acceptance_criteria, a task breakdown, QA test cases, and depends_on (other feature titles, for the "
        "build order/timeline). Be realistic and specific to the idea. Output ONLY valid JSON to plan.json.")


# A planning runtime: Claude in the room, but the command is the planning prompt (not a build task).
def _genesis_runtime():
    from cook.runtime import ClaudeCodeRuntime

    class GenesisRuntime(ClaudeCodeRuntime):
        name = "genesis"

        def command(self, feature_slice: dict) -> list[str]:
            idea = (feature_slice.get("acceptance_criteria") or [""])[0]
            return ["claude", "-p", genesis_prompt(idea), "--permission-mode", "acceptEdits", "--output-format", "json"]

    return GenesisRuntime()


def plan_project(idea: str, image: str | None = None) -> tuple[dict, str]:
    """Run the planner in a sealed one-door room; return (plan, worktree). plan.json is read from the room."""
    from cook.runner import CookRunner
    repo = tempfile.mkdtemp(prefix="thor-genesis-")
    os.chmod(repo, 0o777)
    subprocess.run(["git", "init", "-q", repo], check=True)
    # GenesisRuntime is passed explicitly (no THOR_COOK env mutation — safe to call IN the control-plane
    # process); its image defaults to thor-room-claude and it auto-discovers your Claude login.
    if image:
        os.environ.setdefault("THOR_COOK_IMAGE", image)
    slice_ = {"feature_id": "GENESIS", "scope_files": ["plan.json"], "acceptance_criteria": [idea]}
    CookRunner(runtime=_genesis_runtime()).run(slice_, worktree_host_path=repo)
    path = os.path.join(repo, "plan.json")
    if not os.path.exists(path):
        raise SystemExit("Genesis produced no plan.json — the planner failed (check the room / your Claude login).")
    raw = open(path, encoding="utf-8").read().strip()
    if raw.startswith("```"):                       # tolerate a fenced block if the model wrapped it
        raw = raw.split("```", 2)[1].lstrip("json").strip() if "```" in raw[3:] else raw.strip("`")
    plan = json.loads(raw)
    if not isinstance(plan.get("features"), list) or not plan["features"]:
        raise SystemExit("Genesis plan.json had no features — re-run or refine the idea.")
    return plan, repo


_PR = {"P0": 0, "P1": 2, "P2": 3}


def _ctx_for(f: dict, vision: str) -> str:
    ctx = json.dumps({"summary": f.get("summary", ""), "acceptance_criteria": f.get("acceptance_criteria", []),
                      "tasks": f.get("tasks", []), "qa_cases": f.get("qa_cases", []),
                      "depends_on": f.get("depends_on", []), "vision": vision})
    return ctx[:4000]                                     # the /features API caps context at 4000


def apply_via_api(base: str, plan: dict, token: str | None = None) -> list:
    """Write the catalog through the CONTROL PLANE's API — so the one Manager is the sole writer and the
    features appear LIVE in the cockpit/board with their real tasks + QA. (This is why Genesis must not run
    its own Manager against the live ledger — single-writer, the H6 rule.)"""
    import urllib.request
    feats = []
    for f in plan["features"]:
        body = json.dumps({"title": f.get("title", "feature"), "context": _ctx_for(f, plan.get("vision", "")),
                           "priority": _PR.get(f.get("priority"), 3)}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/features", body, {"Content-Type": "application/json"})
        if token:
            req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=10) as r:
            fid = json.loads(r.read()).get("feature_id")
        feats.append({"feature_id": fid, "title": f.get("title"), "priority": f.get("priority", "P2")})
    return feats


def _control_plane_up(base: str) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(base.rstrip("/") + "/health/system", timeout=3)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(idea: str) -> int:
    base = os.environ.get("THOR_DASHBOARD", "http://127.0.0.1:7080")
    token = os.environ.get("THOR_API_TOKEN")
    print(f"[genesis] planning: {idea[:100]}\n[genesis] the planner (your Claude) is working in a sealed room ...")
    plan, _repo = plan_project(idea)
    print(f"[genesis] vision: {plan.get('vision', '')[:160]}")
    if not _control_plane_up(base):
        sys.exit(f"[genesis] the control plane isn't running at {base} — start it (python tools/start_thor.py) so "
                 "Genesis writes the catalog through the ONE Manager (sole writer), then re-run.")
    feats = apply_via_api(base, plan, token)
    print(f"[genesis] {len(feats)} features written to the catalog (live in the cockpit board):")
    for f in feats:
        print(f"   [{f['priority']}] {f['feature_id']}  {f['title']}")
    print(f"[genesis] ✅ Open the cockpit → Board: review the plan, set priorities, then Mark ready to build.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('usage: python tools/genesis.py "<your project idea>"')
    sys.exit(main(sys.argv[1]))
