# Module 11 — The Self-Audit Model (Zero-Cost Qwen Inspector)

The "understanding eyes" of the three-layer health model. Where the Sentinel (M10) asks *"are you
alive?"*, the Self-Audit Model asks *"are you doing your job correctly?"* — a cheap, always-on,
**read-only** inspector that writes correctness reports + the system **meta-trust score** to the DB at
near-zero cost, and **escalates URGENT to the Sentinel** but **never enforces directly** (broad eyes,
no hands). The v1 of Toras. Spec: [`../docs/PRD-Module-11-SelfAudit.md`](../docs/PRD-Module-11-SelfAudit.md).

**Decisions (Rule 9):** the local Qwen model is a **deterministic stand-in** behind a clean Toras-ready
`InspectionModel` seam (no Ollama in this env; not smoke-testable) — zero frontier calls (AC-1). Read-only
is enforced **for real by Postgres permissions** (a `selfaudit` role that physically can't write the
EventLog — AC-3).

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `db.py` | 11.8 Read-Only Guard | Postgres `selfaudit` role: SELECT system tables, INSERT only own tables |
| `model_host.py` | 11.2 Local Model Host | the Toras-ready `InspectionModel` seam; v1 deterministic analyzer |
| `inspector.py` | 11.1/11.5 | read EventLog → system observations (anomaly detection) |
| `metatrust.py` | 11.4 Meta-Trust Scorer | system reliability score (system-trust, NOT agent-trust) |
| `escalate.py` | 11.6 URGENT Escalator | severe → Sentinel; advisory, never halts |
| `core.py` | the service | inspect/report/score/escalate/retro/benchmark + health |

## Milestone (smoke `tools/smoke_selfaudit.py`)
**AC-1 + AC-3 + AC-4** — a continuous, zero-cost, read-only inspector that catches a real correctness
anomaly and escalates it to the Sentinel **without ever being able to act on the system itself**.

## Smoke (NOT run until asked)
```bash
python tools/smoke_selfaudit.py   # Postgres (real read-only role) + Manager EventLog + the real Sentinel
```
`tests/selfaudit/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
