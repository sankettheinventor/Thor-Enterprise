"""
Sub-module 11.8 — Read-Only Guard, enforced by Postgres permissions (FR-3 / AC-3).

A dedicated `selfaudit` DB role with SELECT on the system tables (it inspects everything) and
INSERT only on its OWN report/score tables. It has NO write grant on eventlog/rooms/cards/features —
so a write there is PHYSICALLY DENIED by Postgres. Broad eyes, no hands: a compromised or
hallucinating inspector can write wrong reports, but can never alter code/state/rules/the EventLog.
"""
from __future__ import annotations

import os

import psycopg
from psycopg import sql

from manager.pg import PG_DB, PG_HOST_PORT

# Production-configurable (no hardcoded host/password). Full override via THOR_SELFAUDIT_DSN; otherwise
# derive from the same Postgres the Manager uses (PG_HOST_PORT/PG_DB) with the read-only `selfaudit`
# role + a configurable password. Defaults match the dev bootstrap, so make prove/qa are unchanged.
SELFAUDIT_PASSWORD = os.environ.get("THOR_SELFAUDIT_PASSWORD", "selfaudit")
RO_DSN = os.environ.get("THOR_SELFAUDIT_DSN") or \
    f"postgresql://selfaudit:{SELFAUDIT_PASSWORD}@localhost:{PG_HOST_PORT}/{PG_DB}"

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
        # sql.Literal safely quotes the password into the DO-block body (a bind param cannot be typed
        # inside a DO block → IndeterminateDatatype). Literal handles quoting/escaping (no injection).
        cur.execute(sql.SQL(
            "DO $do$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='selfaudit') "
            "THEN CREATE ROLE selfaudit LOGIN PASSWORD {pw}; END IF; END $do$;"
        ).format(pw=sql.Literal(SELFAUDIT_PASSWORD)))
        # READ everything (broad eyes) ...
        cur.execute("GRANT SELECT ON eventlog, rooms, cards, features, bugs TO selfaudit")
        # ... WRITE only its own tables (no hands anywhere else)
        cur.execute("GRANT SELECT, INSERT ON selfaudit_reports, meta_trust TO selfaudit")
    admin_conn.commit()


def connect_readonly():
    """Connect as the read-only `selfaudit` role (physically cannot write outside its own tables)."""
    return psycopg.connect(RO_DSN, autocommit=True)
