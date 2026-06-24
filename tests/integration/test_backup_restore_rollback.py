"""
Audit blocker #4 (DR half) — the rollback / disaster-recovery DATA path, TESTED not just documented.
Backs up the tamper-evident ledger, wipes it (simulating host/data loss), restores it, and proves the
hash-chain is intact afterward with no lost/extra rows. A restore is only 'done' when verify_chain holds —
the chain makes a torn/tampered restore fail closed instead of silently shipping corruption.

Deferred (live: needs Postgres).
"""
import pytest

pytestmark = pytest.mark.deferred

N = 25


def test_ledger_backup_restore_preserves_chain(fresh_ledger):
    from manager.core import ThorManager
    from manager.eventlog import EventLogWriter

    conn = fresh_ledger
    w = EventLogWriter(conn)
    for i in range(N):
        w.append("dr.tick", {"i": i}, actor="manager")

    before = ThorManager(conn)
    assert before.eventlog.verify_chain(), "precondition: chain valid before backup"
    n_before = len([e for e in before.eventlog.all_events() if e["event_type"] == "dr.tick"])
    assert n_before == N

    # 1) BACKUP — logical dump of the ledger table (what pgbackup's pg_dump does, in-process)
    dump = bytearray()
    with conn.cursor().copy("COPY eventlog TO STDOUT") as cp:
        for chunk in cp:
            dump += chunk
    assert dump, "backup produced no data"

    # 2) DISASTER — the ledger is lost
    with conn.cursor() as cur:
        cur.execute("TRUNCATE eventlog")
    conn.commit()
    assert not [e for e in ThorManager(conn).eventlog.all_events() if e["event_type"] == "dr.tick"], \
        "ledger should be empty after the simulated loss"

    # 3) RESTORE — from the dump
    with conn.cursor().copy("COPY eventlog FROM STDIN") as cp:
        cp.write(bytes(dump))
    conn.commit()

    # 4) VERIFY — never trust a restore blindly: the chain must verify AND the rows must match
    after = ThorManager(conn)
    assert after.eventlog.verify_chain(), "hash-chain did NOT verify after restore — restore is corrupt"
    n_after = len([e for e in after.eventlog.all_events() if e["event_type"] == "dr.tick"])
    assert n_after == n_before, f"row count changed across restore: {n_after} != {n_before}"
