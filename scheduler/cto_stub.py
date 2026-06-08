"""
The CTO — the upstream planning call (PRD §5.4). STUB for now (PRD §14 permits stubbing the CTO).

This is the ONLY place a per-task planning "LLM call" happens. It is stubbed: it returns fixed
skills/scope and makes NO real model call. The Scheduler triggers this on dispatch but never
calls it during scheduling (readiness/wave/cost) — that is what preserves the zero-LLM property
(FR-1 / AC-2). `PLAN_CALLS` lets a test assert the Scheduler made zero planning calls while it
was only scheduling.
"""
from __future__ import annotations

# Incremented ONLY here — used to prove the scheduling loop triggers no planning calls (AC-2).
PLAN_CALLS = 0

# Always-forbidden paths (deny-precedence), independent of a feature's scope. The cook can never
# write secrets/infra/governance — even if a careless plan put them in scope (defence-in-depth).
STANDARD_FORBIDDEN = ("**/secrets*", "**/*secret*", "infra/", ".git/", ".thor/")


def plan_task(feature_id: str, task_type: str = "build", feature: dict | None = None) -> dict:
    """The one (would-be LLM) planning call: decide skills + the room's FROZEN scope. Stubbed (no
    LLM). Scope is PLAN-OWNED (cto.js `getScopeFilesForFeature` doctrine): the feature's DECLARED
    `scope_files`, NEVER derived from the cook's writes. Undeclared → empty scope → deny-all
    (fail-closed applied to scope: an unplanned feature can write nothing until the plan declares it)."""
    global PLAN_CALLS
    PLAN_CALLS += 1
    skills = {"build": ("build", "code-reviewer"), "qa": ("qa",),
              "checker": ("analysis",), "genesis": ("pm", "cto", "ux-strategy")}.get(task_type, ("build",))
    scope_files = tuple((feature or {}).get("scope_files", ()) or ())
    return {"feature_id": feature_id, "skills": list(skills),
            "scope": {"files": list(scope_files)},      # back-compat key
            "scope_files": scope_files,                 # the FrozenPolicy scope the room is sealed with
            "forbidden_patterns": STANDARD_FORBIDDEN,
            "capability_tags": [task_type]}


def reset_counter() -> None:
    global PLAN_CALLS
    PLAN_CALLS = 0
