# Module 10 — The Sentinel (Meta-Governance / Self-Verifying Governance)

The governor of the governor (P9). Continuously proves THOR is **alive AND responsive, loaded,
connected, untampered, and STILL CATCHING** — and **fail-closes + halts** the moment it can't, so the
governor is never *silently* broken. The mechanical reflexes of the three-layer health model. Spec:
[`../docs/PRD-Module-10-Sentinel.md`](../docs/PRD-Module-10-Sentinel.md).

**Decision (Rule 9 / Rule 5):** AGT SRE + Runtime (kill-switch) stay **stubbed until M12**; the
THOR-specific efficacy — the **canary**, integrity crawler, loadedness, reconcile, boot self-test, and
the **silent-heartbeat base case** — are built for real (that's the meta-governance moat).

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `core.py` | 10.1/10.2/10.3/10.6/10.7/10.9 | probes, halt, boot self-test, alarm, maintenance, heartbeat |
| `integrity.py` | 10.4 Integrity Crawler | hash governance rules; CRAWLER_ALARM on tamper |
| `canary.py` | 10.5 Canary Engine | fire must-fail actions at the real detectors (pass = broken) |
| `reconcile.py` | 10.8 Reconciler | registry vs actual containers; orphans + shadow agents |

## The five verifications + the canary's double duty
liveness (alive AND responsive) · loadedness · connectivity · integrity · **efficacy (canary)**. The
canary is both an **efficacy check** (a planted must-fail action that proves the detector still detects)
and the **regress-stopper** (a heartbeat whose *silence* is itself the alarm — the elegant base case).

## Milestone (smoke `tools/smoke_sentinel.py`)
**AC-1 + AC-2 + AC-7** — a dead governor is caught and fail-closed, a broken detector is caught by a
passing canary, and the Sentinel's own death is caught by its silent heartbeat. THOR cannot be silently
broken, all the way down to the watcher itself.

## Smoke (NOT run until asked)
```bash
python tools/smoke_sentinel.py   # Postgres + Manager + real Leash/Engine canaries + a real shadow room
```
`tests/sentinel/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
