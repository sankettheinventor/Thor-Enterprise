"""
Sub-module 4.1 — Graph Loader. Build the task DAG from the catalog and validate it (FR-2):
reject cycles and missing dependencies; compute deterministic dependency levels for wave planning.

A tiny custom DAG (no networkx) — the PRD §4 explicitly permits "a small custom structure".
"""
from __future__ import annotations

from dataclasses import dataclass, field


class GraphError(ValueError):
    """Raised on a cyclic or dependency-incomplete catalog (rejected at load — AC-11)."""


@dataclass
class Task:
    feature_id: str
    depends_on: tuple[str, ...] = ()
    task_type: str = "build"        # build | genesis | checker | qa
    est_tokens: int = 1000          # cost estimate (advisory — FR-10/D4)
    status: str = "pending"         # pending | running | done | failed
    ready: bool = True              # operator/auto-ready flag (FR-3)


@dataclass
class TaskGraph:
    tasks: dict[str, Task]
    levels: dict[str, int] = field(default_factory=dict)

    def deps(self, fid: str) -> tuple[str, ...]:
        return self.tasks[fid].depends_on


def build_graph(tasks: list[Task]) -> TaskGraph:
    index = {t.feature_id: t for t in tasks}
    if len(index) != len(tasks):
        raise GraphError("duplicate feature_id in catalog")

    # missing-dependency check (FR-2)
    for t in tasks:
        for d in t.depends_on:
            if d not in index:
                raise GraphError(f"missing dependency: {t.feature_id} -> {d}")

    # cycle detection (DFS colouring) — surfaces the cycle (AC-11)
    WHITE, GREY, BLACK = 0, 1, 2
    color = {fid: WHITE for fid in index}
    stack: list[str] = []

    def visit(fid: str):
        color[fid] = GREY
        stack.append(fid)
        for d in sorted(index[fid].depends_on):  # sorted → deterministic cycle report
            if color[d] == GREY:
                cycle = stack[stack.index(d):] + [d]
                raise GraphError("cycle detected: " + " -> ".join(cycle))
            if color[d] == WHITE:
                visit(d)
        stack.pop()
        color[fid] = BLACK

    for fid in sorted(index):
        if color[fid] == WHITE:
            visit(fid)

    # dependency levels: level = 0 if no deps else 1 + max(dep levels)
    levels: dict[str, int] = {}

    def level_of(fid: str) -> int:
        if fid in levels:
            return levels[fid]
        t = index[fid]
        lvl = 0 if not t.depends_on else 1 + max(level_of(d) for d in t.depends_on)
        levels[fid] = lvl
        return lvl

    for fid in sorted(index):
        level_of(fid)

    return TaskGraph(tasks=index, levels=levels)
