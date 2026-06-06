"""
THOR Module 3 — the THOR Manager (governance brain + room lifecycle authority).

The spine: the single EventLog writer, the authoritative room registry, the rules custodian, the
three signature points, and event-sourcing crash recovery. A COORDINATOR, not a doer (P8) —
it routes, records, owns state, verifies signatures; everything heavy is delegated.

Persistence (decision 2026-06-06): REAL Postgres ([ThorDB] + the signed hash-chained EventLog
table), per the user's choice. Files:
    pg.py        — Postgres container lifecycle + DSN
    db.py        — schema (eventlog + rooms/cards/features projections)
    eventlog.py  — EventLogWriter: single writer, Ed25519-signed, hash-chained, idempotent (FR-2/8)
    core.py      — ThorManager: registry, lifecycle (drives the Wall), cards & signatures,
                   state projector (replay recovery), health, fail-closed
    api.py       — REST surface (§6.1), thin wrappers over core

Stubbed pending later modules: Verdict Coordinator (drives GovernanceEngine, M6) and the full
Gitea Director merge (real Gitea, M12). The Leash (M2) now records THROUGH the Manager (FR-2).
"""
