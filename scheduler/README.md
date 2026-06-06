# Module 4 — The Scheduler

Deterministic, zero-LLM task-graph executor. Reads a feature catalog (Kind C), builds a dependency
DAG, runs tasks in capacity-capped **waves**, gates on **budget**, and instructs the **Manager (M3)**
to provision — making **no LLM calls** (the one planning call lives in the CTO). Spec:
[`../docs/PRD-Module-4-Scheduler.md`](../docs/PRD-Module-4-Scheduler.md).

**Bootstrap choices (PRD-permitted):** a tiny custom DAG (no `networkx`) and a stubbed CTO
(`cto_stub.py` — the only place a planning call happens; the Scheduler never makes one).

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `graph.py` | 4.1 Graph Loader | DAG build + cycle/missing-dep validation + levels |
| `core.py` | 4.2–4.8 | readiness, wave planner, capacity governor, dispatcher, cost/budget, replay, restart |
| `cto_stub.py` | 4.5 (upstream) | the one planning call (stub; zero real LLM) |
| `api.py` | — | REST surface (§6.1) on `:7110` |

## Milestone (smoke `tools/smoke_scheduler.py`)
**AC-1 + AC-2** — a deterministic schedule with zero LLM calls in the loop, reproducible on replay.
Part A (pure logic) covers AC-1/2/3/4/5/6/7/8/9/11/12; Part B drives the **real Manager** (Postgres +
Wall) for **AC-10** (restart without double-dispatch) + the real Scheduler→CTO→Manager→Wall handoff.

## Smoke (NOT run until asked)
```bash
python tools/smoke_scheduler.py   # Part A is instant; Part B starts Postgres + 2 rooms, then tears down
```
`tests/scheduler/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
