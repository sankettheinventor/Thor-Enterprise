"""
THOR Module — the Cook (the AI builder). The cook proposes; the Leash disposes.

The invariant: the cook NEVER touches governance. Every action it wants to take is submitted through
the Leash proxy and only happens if the governor allows it. Two cooks live behind one interface:
ScriptedCook (deterministic, for tests/demo) and ClaudeCook (a real Anthropic LLM builder).
"""
from .agent import ClaudeCook, CookAgent, ScriptedCook, run_through_leash

__all__ = ["CookAgent", "ScriptedCook", "ClaudeCook", "run_through_leash"]
