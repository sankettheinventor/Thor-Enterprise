# Module 3 — The THOR Manager

The spine: single governance brain + room lifecycle authority. The **only** EventLog writer, the
authoritative room registry, the rules custodian, the three signature points, and event-sourcing
crash recovery. A **coordinator, not a doer** (P8). Spec:
[`../docs/PRD-Module-3-Manager.md`](../docs/PRD-Module-3-Manager.md).

**Decision (2026-06-06):** REAL Postgres for [ThorDB] + the EventLog (per the user). The Leash (M2)
now records **through** the Manager (FR-2 single writer).

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `pg.py` | — | Postgres container lifecycle + DSN |
| `db.py` | — | schema: `eventlog` (source) + `rooms`/`cards`/`features` (projections) |
| `eventlog.py` | 3.3 EventLog Writer | single writer, Ed25519-signed, hash-chained, idempotent |
| `core.py` | 3.1/3.2/3.4/3.5/3.8/3.9 | registry, lifecycle (drives Wall), cards & signatures, projector, health, fail-closed |
| `api.py` | — | REST surface (§6.1) on `:7100` |

Stubbed pending later modules: **3.6 Verdict Coordinator** (GovernanceEngine, M6) and the real
**3.7 Gitea Director** merge (M12) — both raise `NotImplementedError` with a pointer.

## Milestone (smoke `tools/smoke_manager.py`)
**AC-2 + AC-3** — a tamper-evident signed log the Manager replays to rebuild exact state after a
crash. Also demonstrates AC-1/4/5/7/8/9/10/11/12. AC-6 needs Module 6 (deferred).

## Smoke (NOT run until asked)
```bash
python tools/smoke_manager.py   # in the WSL venv; starts Postgres, provisions real rooms, tears down
```
`tests/manager/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
