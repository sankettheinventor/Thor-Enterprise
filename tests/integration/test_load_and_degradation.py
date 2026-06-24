"""
Audit blocker #3 — performance-under-load + failure-injection (the SRE 'what happens when load is real /
a dependency fails' gap the audit flagged).

  - test_ledger_append_p95_under_concurrent_load: the ledger append is THE hot path (every governed action
    writes one signed, hash-chained row, serialized by a Postgres advisory lock). This drives it under
    concurrent writers, measures p95 latency against a budget, and proves the chain stays perfect under
    contention (no lost/dup/forked seqs).
  - test_locked_conn_self_heals_a_dropped_db_link: failure injection — drop the live DB connection mid-run
    and prove the plane's _LockedConn transparently reconnects (graceful degradation + recovery, not a
    wedged process that 500s every read until restart).

Deferred (live: needs Postgres).
"""
import time

import pytest

pytestmark = pytest.mark.deferred

WRITERS = 8
PER_WRITER = 40
P95_BUDGET_MS = 300.0     # per-append, under 8-way advisory-lock contention (generous; flags real regressions)


def test_ledger_append_p95_under_concurrent_load(fresh_ledger):
    import threading
    from manager import db
    from manager.core import ThorManager
    from manager.eventlog import EventLogWriter

    latencies, errors = [], []
    lat_lock = threading.Lock()

    def worker(wid):
        try:
            conn = db.connect()
            w = EventLogWriter(conn)
            local = []
            for i in range(PER_WRITER):
                t0 = time.perf_counter()
                w.append("load.tick", {"w": wid, "i": i}, actor="manager")
                local.append((time.perf_counter() - t0) * 1000.0)
            conn.close()
            with lat_lock:
                latencies.extend(local)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(WRITERS)]
    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t_start

    assert not errors, f"writers errored under load: {errors[:3]}"
    total = WRITERS * PER_WRITER
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    tput = total / wall
    print(f"\n[load] {total} appends, {WRITERS} writers: p50={p50:.1f}ms p95={p95:.1f}ms "
          f"throughput={tput:.0f}/s wall={wall:.2f}s")

    # chain integrity under concurrency — the guarantee that matters most
    mgr = ThorManager(db.connect())
    seqs = sorted(e["seq"] for e in mgr.eventlog.all_events() if "load.tick" == e["event_type"])
    assert len(seqs) == total, f"lost/extra rows under load: {len(seqs)} != {total}"
    assert len(set(seqs)) == len(seqs), "duplicate seq — the chain forked under load"
    assert mgr.eventlog.verify_chain(), "hash-chain broke under concurrent load"
    # performance budget — a measured number, not a vibe
    assert p95 < P95_BUDGET_MS, f"append p95 {p95:.1f}ms exceeds budget {P95_BUDGET_MS}ms under load"


def test_locked_conn_self_heals_a_dropped_db_link(fresh_ledger):
    """Failure injection: the live DB link drops (idle timeout / restart / network blip). The plane's
    _LockedConn must reconnect on next use, not stay wedged. (Regression guard for the connection-wedge
    bug fixed earlier this session.)"""
    from manager import db
    from tools.start_thor import _LockedConn

    lc = _LockedConn(db.connect(), reconnect=db.connect)
    with lc.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    lc._conn.close()                              # inject the failure: the link is gone
    assert getattr(lc._conn, "closed", False), "precondition: connection is closed"

    with lc.cursor() as cur:                      # next use must transparently reconnect
        cur.execute("SELECT 42")
        assert cur.fetchone()[0] == 42, "plane did not recover from a dropped DB link"
    assert not getattr(lc._conn, "closed", False), "connection should be live again after self-heal"
