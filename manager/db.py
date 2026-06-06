"""
[ThorDB] schema. The EventLog is the append-only signed SOURCE of truth; rooms/cards/features
are PROJECTIONS derived from it (rebuilt by replay on recovery — FR-13).
"""
from __future__ import annotations

import psycopg

from .pg import DSN

SCHEMA = """
CREATE TABLE IF NOT EXISTS eventlog (
    seq        BIGINT PRIMARY KEY,
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL,
    signature  TEXT NOT NULL,
    ts         DOUBLE PRECISION NOT NULL,
    actor      TEXT NOT NULL,
    event_type TEXT NOT NULL,
    room_id    TEXT,
    feature_id TEXT,
    payload    TEXT NOT NULL,          -- canonical JSON (exact bytes that were hashed)
    client_id  TEXT UNIQUE             -- idempotency key (FR/AC-12)
);
CREATE TABLE IF NOT EXISTS rooms (
    room_id        TEXT PRIMARY KEY,
    container      TEXT,
    task_type      TEXT,
    feature_id     TEXT,
    branch         TEXT,
    status         TEXT,
    address        TEXT,
    identity_token TEXT,
    created_at     DOUBLE PRECISION,
    destroyed_at   DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS cards (
    card_id    TEXT PRIMARY KEY,
    type       TEXT,
    feature_id TEXT,
    payload    TEXT,
    status     TEXT,
    decided_by TEXT,
    signature  TEXT,
    created_at DOUBLE PRECISION,
    decided_at DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS features (
    feature_id TEXT PRIMARY KEY,
    title      TEXT,
    context    TEXT,
    priority   INTEGER,
    status     TEXT,
    branch     TEXT,
    est_tokens INTEGER
);
CREATE TABLE IF NOT EXISTS bugs (
    bug_id      TEXT PRIMARY KEY,
    feature_id  TEXT,
    severity    TEXT,
    description TEXT,
    source      TEXT,          -- 'qa' | 'checker'
    status      TEXT,
    found_at    DOUBLE PRECISION
);
"""


def connect():
    # autocommit=True: every statement commits immediately, so read-only SELECTs never leave a
    # transaction open holding locks. (Without this, a lingering read-txn blocks TRUNCATE during
    # replay recovery — a real deadlock. The single-writer chain is serialized in-process by a lock.)
    return psycopg.connect(DSN, autocommit=True)


def init_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
