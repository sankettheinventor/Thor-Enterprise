"""
P0 (M4) proof — the single-writer holds across PROCESSES.

N separate processes (each its own Postgres connection) hammer the SAME ledger concurrently. With only
the in-process threading.Lock this would fork the chain: two processes compute the same `seq`, and since
`seq` is the PRIMARY KEY one INSERT wins while the other raises a unique-violation (or the chain gets a
gap/dup). With the Postgres advisory lock the max(seq)->INSERT is serialized across all processes, so the
result is a perfect contiguous chain.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_concurrent_writer.py
"""
import multiprocessing as mp

import docker

from manager import db, pg
from manager.core import ThorManager
from manager.eventlog import EventLogWriter

PROCS = 8
PER_PROC = 60


def _worker(proc_id: int) -> int:
    conn = db.connect()
    writer = EventLogWriter(conn)
    for i in range(PER_PROC):
        writer.append("load.tick", {"proc": proc_id, "i": i}, actor="manager")
    conn.close()
    return PER_PROC


if __name__ == "__main__":
    pg.start(docker.from_env())
    conn = db.connect()
    db.init_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE eventlog, rooms, cards, features")
    conn.commit()

    with mp.Pool(PROCS) as pool:
        pool.map(_worker, range(PROCS))

    mgr = ThorManager(db.connect())
    chain_ok = mgr.eventlog.verify_chain()
    seqs = [e["seq"] for e in mgr.eventlog.all_events()]
    total = PROCS * PER_PROC

    print(f"processes={PROCS} per_proc={PER_PROC} expected={total}")
    print(f"rows_written={len(seqs)}")
    print(f"seqs_contiguous_0..N-1={sorted(seqs) == list(range(total))}")
    print(f"no_duplicate_seq={len(set(seqs)) == len(seqs)}")
    print(f"verify_chain={chain_ok}")
    assert len(seqs) == total, "lost or extra rows under concurrency"
    assert sorted(seqs) == list(range(total)), "seq not contiguous — the chain forked"
    assert len(set(seqs)) == len(seqs), "duplicate seq — two writers collided"
    assert chain_ok, "hash-chain broke under concurrency"
    print("P0_CONCURRENT_WRITER_OK")
