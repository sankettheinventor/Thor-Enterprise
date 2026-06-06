# Module 5 — The Task Handoff Contract

The frozen six-message seam between the Manager and rooms, plus the read-only one-feature slice.
EXACTLY six messages cross; the room can knock (`claim_done`) but has **no protocol field to
self-certify** — only the Manager's `result_decision` is "done" (P5, structural). Spec:
[`../docs/PRD-Module-5-Contract.md`](../docs/PRD-Module-5-Contract.md).

**Choices (PRD-permitted):** Pydantic schemas (`extra="forbid"`) + two transports (docker-exec v1 +
in-process/REST v1.1) so transport-swappability is actually demonstrated.

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `messages.py` | 5.1 Schema + 5.5 Validator | the six Pydantic messages, directions, version |
| `slice_builder.py` | 5.2 Feature-Slice Builder | one feature, whitelisted fields, no catalog leak |
| `transport.py` | 5.4 Transport Adapter | DockerExec (v1) + InProcess/REST (v1.1) |
| `seam.py` | 5.3/5.6/5.7 | mount/claim/amend handlers, idempotency, version, event recording |

## Milestone (smoke `tools/smoke_contract.py`)
**AC-2 + AC-4** — a room briefed with only its one feature, read-only, with structurally no way to
declare itself done. Part A (pure logic) covers AC-1/4/5/6/7/8/9/10/12; Part B drives the **real
Manager + a real room** for AC-2 (one-feature slice via `docker exec cat`), AC-3 (write fails),
AC-5 (docker-exec conformance), AC-11 (messages in the EventLog).

## Smoke (NOT run until asked)
```bash
python tools/smoke_contract.py   # Part A instant; Part B starts Postgres + a room, then tears down
```
`tests/contract/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
