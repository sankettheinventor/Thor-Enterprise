"""
THOR Module 4 — the Scheduler (deterministic, zero-LLM task-graph executor).

The conductor: reads a feature catalog (Kind C), builds a dependency DAG, and decides what runs
when — in deterministic waves, capped by capacity, gated on budget — instructing the Manager (M3)
to provision. It makes NO LLM calls (FR-1); the single planning call lives upstream in the CTO.

Bootstrap choices (PRD §4/§14 permit both): a tiny CUSTOM DAG (no networkx dependency) and a
STUBBED CTO (cto_stub.py) — the Scheduler triggers the planning call but never makes it.

Files → PRD §2 sub-modules:
    graph.py    4.1 Graph Loader (DAG build + cycle/missing-dep validation + levels)
    core.py     4.2 Readiness · 4.3 Wave Planner · 4.4 Concurrency Governor · 4.5 Dispatcher
                4.6 Completion Listener · 4.7 Cost+Budget · 4.8 Replay
    cto_stub.py the upstream planning call (stub; the ONLY place a planning call happens)
    api.py      REST surface (§6.1)
"""
