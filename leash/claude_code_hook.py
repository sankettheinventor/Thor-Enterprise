#!/usr/bin/env python3
"""
THOR Leash ↔ Claude Code bridge — a PreToolUse hook.

Claude Code is the COOK: it runs INSIDE the sealed room and writes the feature. THOR's invariant is
that the cook never bypasses governance — so Claude Code is configured (room `.claude/settings.json`)
to call this hook BEFORE every Write / Edit / MultiEdit / NotebookEdit / Bash. The hook maps the tool
call to a THOR action and evaluates it against the room's frozen policy using the SAME `leash.policy`
engine as FLOW B (so it inherits the path-traversal guard, BUG-1). Decision:

  * ALLOW  → exit 0 (silent; Claude Code proceeds).
  * BLOCK  → print the reason to stderr and exit 2 — Claude Code feeds that reason back to the model as a
             tool error, so the cook learns WHY and adjusts. (exit-2 is the most version-stable block
             mechanism; the JSON `permissionDecision:"deny"` form is equivalent.)

Fail-CLOSED: any unreadable input / missing policy / unexpected error → BLOCK. The cook gets no
unaudited, ungoverned action.

Wiring (room settings.json):
  "hooks": {"PreToolUse": [{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
            "hooks": [{"type": "command", "command": "python3 -m leash.claude_code_hook"}]}]}
"""
from __future__ import annotations

import json
import os
import sys

# Forbidden everywhere inside a room (defence in depth, independent of scope): infra, secrets, the .git
# internals, and dependency manifests are governed by the policy engine's manifest/forbidden rules.
DEFAULT_FORBIDDEN = ("infra/", "**/secrets*", ".git/", "**/.env", "**/id_rsa*")


def _block(reason: str) -> None:
    print(f"THOR Leash DENY: {reason}", file=sys.stderr)
    sys.exit(2)


def _load_scope() -> tuple[str, ...] | None:
    """Scope comes from the task slice the Wall mounts read-only into the room (FR-6)."""
    slice_path = os.environ.get("THOR_TASK_SLICE", "/task/feature.json")
    try:
        with open(slice_path, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:  # noqa: BLE001 — no slice → cannot know scope → fail closed (caller blocks)
        return None
    scope = s.get("scope_files") or (s.get("scope") or {}).get("files") or []
    return tuple(scope)


# Tools that WRITE the filesystem. If one is matched but no path can be extracted, fail CLOSED (deny) —
# an unparsed write must never slip through ungoverned (AUD-hook-failopen).
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Create", "Update", "Patch"}
_PATH_KEYS = ("file_path", "notebook_path", "path", "filePath", "target_file")


def _target_paths(tool_name: str, tool_input: dict) -> list[str]:
    """The file path(s) a tool would write. Robust to field-name variation across tools/versions —
    `file_path`, `notebook_path` (NotebookEdit), `path`, etc., at top level or per-edit."""
    paths: list[str] = []
    for key in _PATH_KEYS:
        if isinstance(tool_input.get(key), str):
            paths.append(tool_input[key])
    for e in tool_input.get("edits", []) or []:
        if isinstance(e, dict):
            for key in _PATH_KEYS:
                if isinstance(e.get(key), str):
                    paths.append(e[key])
    return paths


def evaluate_event(event: dict) -> tuple[bool, str]:
    """Pure decision (testable): (allowed, reason). Reused by the CLI entrypoint and the tests."""
    from leash.policy import FrozenPolicy, evaluate

    scope = _load_scope()
    if scope is None:
        return False, "no room policy/task slice found — fail closed"
    policy = FrozenPolicy(
        room_id=os.environ.get("THOR_ROOM_ID", "room"),
        scope_files=scope, forbidden_patterns=DEFAULT_FORBIDDEN,
        language_lock="", frozen_at=0.0,
    )
    worktree = os.path.realpath(os.environ.get("THOR_WORKTREE", "/work"))
    tool = event.get("tool_name", "")
    ti = event.get("tool_input", {}) or {}

    paths = _target_paths(tool, ti)
    if not paths:
        if tool in _WRITE_TOOLS:                   # a write tool we could not parse → fail CLOSED
            return False, f"{tool}: write tool with no parseable path → fail closed (AUD-hook-failopen)"
        if tool != "Bash":
            return True, "no file path to govern"  # a genuine non-write tool (Read, Glob, …) — allow

    for p in paths:
        # the policy is path-based and worktree-relative; computing relpath turns an absolute or
        # `..`-laden path into the form the scope check (and BUG-1 traversal guard) reasons about.
        rel = os.path.relpath(os.path.realpath(os.path.join(worktree, p)), worktree)
        v = evaluate(policy, {"type": "tool_call", "name": "write_file", "target": rel,
                              "room_id": "r", "args": {}})
        if v.decision != "allow":
            return False, f"{p} → {v.reason}"
    # Bash: a sealed room limits blast radius (worktree is the only writable mount, egress is one-door),
    # but command-level governance (parsing redirects/egress) is a named follow-up — allowed for v1.
    return True, "within approved scope"


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw or "{}")
    except Exception as e:  # noqa: BLE001
        _block(f"unreadable hook input ({e}) — fail closed")
    try:
        allowed, reason = evaluate_event(event)
    except Exception as e:  # noqa: BLE001 — never fail OPEN
        _block(f"governor error ({e}) — fail closed")
    if not allowed:
        _block(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
