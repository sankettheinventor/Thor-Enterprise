"""
THOR Module 11 — the Self-Audit Model (zero-cost Qwen inspector).

Where the Sentinel (M10) asks "are you ALIVE?", the Self-Audit Model asks "are you doing your job
CORRECTLY?" — it brings UNDERSTANDING to health-watching without bringing COST. A small, always-on,
read-only local model that continuously inspects the EventLog/outcomes, writes correctness reports +
the system meta-trust score to the DB, and escalates anything severe URGENT to the Sentinel — but
NEVER enforces directly (broad eyes, no hands). The v1 of Toras.

Files → PRD §2 sub-modules:
    db.py         11.8 Read-Only Guard — a Postgres `selfaudit` role: SELECT on system tables,
                  INSERT only on its own report/score tables (physically can't write elsewhere, AC-3)
    model_host.py 11.2 Local Model Host — the Toras-ready InspectionModel seam (observe→assess→emit);
                  v1 = a zero-cost DETERMINISTIC analyzer (a real Qwen/Ollama plugs in at v2)
    inspector.py  11.1 Inspector Loop + 11.3 Report Generator + 11.5 Anomaly Detector
    metatrust.py  11.4 Meta-Trust Scorer (system-trust, NOT agent-trust)
    escalate.py   11.6 URGENT Escalator (severe → Sentinel; advisory only, never halts)
    core.py       the SelfAudit service: inspect/report/score/escalate/retro/benchmark + health

Decisions (Rule 9): the local Qwen model is a DETERMINISTIC stand-in (no Ollama in this env; not
smoke-testable) behind a clean Toras-ready seam (FR-13/AC-12) — zero frontier calls (AC-1). Read-only
is enforced for real by Postgres permissions (AC-3).
"""
