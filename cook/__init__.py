"""
THOR Module — the Cook (the AI builder). The cook proposes; the Leash disposes.

The invariant: the cook NEVER touches governance — every action it wants to take is gated by the Leash.

The PRODUCTION cook is **Claude Code running inside the sealed room**, governed by the Leash via a
PreToolUse hook (`leash.claude_code_hook`) wired through managed settings — see the Claude Code room
image (`wall/image/Dockerfile.claude`) and DEPLOYMENT.md. This module keeps the IN-PROCESS governance
seam used by tests/demo: `ScriptedCook` (a deterministic cook) whose every action is routed through the
Leash proxy by `run_through_leash` — the same invariant, exercised without an LLM.
"""
from .agent import CookAgent, ScriptedCook, run_through_leash
from .runtime import (ClaudeCodeRuntime, CookRuntime, GenericCommandRuntime, known_runtimes,
                      register_runtime, select_runtime)

__all__ = [
    "CookAgent", "ScriptedCook", "run_through_leash",
    "CookRuntime", "ClaudeCodeRuntime", "GenericCommandRuntime",
    "select_runtime", "register_runtime", "known_runtimes",
]
