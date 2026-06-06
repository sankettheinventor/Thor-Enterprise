# Module 8 — The PM Surface (Kanban, Approval Cards, Audit, Signatures)

The cockpit the accountable human sits in: **Direct → Watch → Decide → Audit**, plus legible refusal
and cost visibility. A **window, not a brain** — reads projections from the Manager (M3) and writes
back only direction + signatures; holds no competing truth; shows "disconnected" rather than
stale-as-live. Spec: [`../docs/PRD-Module-8-PMSurface.md`](../docs/PRD-Module-8-PMSurface.md).

**Decision (flagged Rule 9):** the PRD specifies a JS/TS React frontend. This env has no Node and a SPA
isn't smoke-testable, so the substantive build is the **Python DashboardAPI + cockpit logic** (testable)
+ a **minimal static `cockpit.html`** (evolves ceo.html). The full React presentation layer is deferred —
it's pure UI over this same API contract.

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `legible.py` | 8.6 Legible Refusal | reason-code → plain language (+ safe fallback) |
| `kanban.py` | 8.1 Kanban | feature states → stage columns |
| `cost.py` | 8.7 Cost & Budget | per-feature/total spend, caps, alerts |
| `audit.py` | 8.5 Audit Feed | EventLog projection + CSV/JSON export |
| `service.py` | 8.2/8.3/8.4/8.8/8.9 | the read-and-sign service (window, not a brain) |
| `dashboard_api.py` | — | the DashboardAPI (`:7080`) FastAPI wrapper |
| `cockpit.html` | — | minimal static cockpit (full React UI deferred) |

## Milestone (smoke `tools/smoke_pmsurface.py`)
**AC-2 + AC-3 + AC-6** — a verified Ed25519 signature drives a real merge, governance blocks are
explained in plain language, and the cockpit never lets the operator sign against a stale picture.

## Smoke (NOT run until asked)
```bash
python tools/smoke_pmsurface.py   # Postgres + real Manager/Scheduler/Checker; exercises the service + logic
```
`tests/dashboard/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
