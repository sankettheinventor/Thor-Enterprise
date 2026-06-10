"""
Sub-module 11.8 — Read-Only Guard, enforced by Postgres permissions (FR-3 / AC-3).

A dedicated `selfaudit` DB role with SELECT on the system tables (it inspects everything) and
INSERT only on its OWN report/score tables. It has NO write grant on eventlog/rooms/cards/features —
so a write there is PHYSICALLY DENIED by Postgres. Broad eyes, no hands: a compromised or
hallucinating inspector can write wrong reports, but can never alter code/state/rules/the EventLog.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

from manager import pg

# Production-configurable (no hardcoded host/password). Full override via THOR_SELFAUDIT_DSN; otherwise
# derive the read-only `selfaudit` DSN from the SAME Postgres the Manager binds to (host/port/db come
# from manager.pg.DSN — which already honors THOR_PG_DSN/THOR_PG_*), swapping in the selfaudit role +
# a configurable password. This keeps ONE source of truth for the DB host (the localhost-hardcode bug
# crashed the containerized control plane: the Manager reached the external DB but Self-Audit did not).
SELFAUDIT_PASSWORD = os.environ.get("THOR_SELFAUDIT_PASSWORD", "selfaudit")


def _derive_ro_dsn() -> str:
    override = os.environ.get("THOR_SELFAUDIT_DSN")
    if override:
        return override
    u = urlsplit(pg.DSN)                                   # same host/port/db the Manager uses
    netloc = f"selfaudit:{SELFAUDIT_PASSWORD}@{u.hostname}" + (f":{u.port}" if u.port else "")
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))


RO_DSN = _derive_ro_dsn()

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
