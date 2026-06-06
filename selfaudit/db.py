"""
Sub-module 11.8 — Read-Only Guard, enforced by Postgres permissions (FR-3 / AC-3).

A dedicated `selfaudit` DB role with SELECT on the system tables (it inspects everything) and
INSERT only on its OWN report/score tables. It has NO write grant on eventlog/rooms/cards/features —
so a write there is PHYSICALLY DENIED by Postgres. Broad eyes, no hands: a compromised or
hallucinating inspector can write wrong reports, but can never alter code/state/rules/the EventLog.
"""
from __future__ import annotations

import psycopg

RO_DSN = "postgresql://selfaudit:selfaudit@localhost:55432/thor"

_OWN_TABLES = """
CREATE TABLE IF NOT EXISTS selfaudit_reports (
    report_id  TEXT PRIMARY KEY,
    ts         DOUBLE PRECISION,
    scope      TEXT,
    findings   TEXT,
    assessment TEXT
);
CREATE TABLE IF NOT EXISTS meta_trust (
    ts      DOUBLE PRECISION,
    score   DOUBLE PRECISION,
    signals TEXT
);
"""


def setup(admin_conn) -> None:
    """Run as the DB owner (the Manager's connection): create the role + its tables + grants."""
    with admin_conn.cursor() as cur:
        cur.execute(_OWN_TABLES)
        cur.execute(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='selfaudit') "
            "THEN CREATE ROLE selfaudit LOGIN PASSWORD 'selfaudit'; END IF; END $$;")
        # READ everything (broad eyes) ...
        cur.execute("GRANT SELECT ON eventlog, rooms, cards, features, bugs TO selfaudit")
        # ... WRITE only its own tables (no hands anywhere else)
        cur.execute("GRANT SELECT, INSERT ON selfaudit_reports, meta_trust TO selfaudit")
    admin_conn.commit()


def connect_readonly():
    """Connect as the read-only `selfaudit` role (physically cannot write outside its own tables)."""
    return psycopg.connect(RO_DSN, autocommit=True)
