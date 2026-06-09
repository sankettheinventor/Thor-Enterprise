"""
Phase 4 step 5 — DB PERSISTENCE / REPLAY proof.

Builds real signed state, then "kills the Manager" and rebuilds a FRESH Manager whose projections are
replayed purely from the EventLog (the source of truth, FR-13). Asserts the rebuilt state is identical
to the original — proving the database genuinely persists and the ledger is authoritative.

Run (from ~/thor-enterprise):  .venv/bin/python tools/qa/prove_replay.py
"""
import docker

from manager import db, pg
from manager.core import ThorManager

pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
with conn.cursor() as c:
    c.execute("TRUNCATE eventlog, rooms, cards, features")
conn.commit()

mgr = ThorManager(conn)
# real signed events → projected into cards/features
mgr.raise_card("plan", "RP1", {"feature_id": "RP1", "summary": "replay-proof plan"})
mgr.raise_card("merge", "RP2", {"feature_id": "RP2"})
mgr._record("feature.status", {"feature_id": "RP1", "status": "in_progress"}, feature_id="RP1")

before = mgr.state_summary()
n_events = mgr.eventlog.count()

# "kill the Manager" → a fresh Manager on a fresh connection; wipe projections; replay from the log only.
mgr2 = ThorManager(db.connect())
mgr2.rebuild_from_log()                  # TRUNCATE rooms/cards/features, then replay every event
after = mgr2.state_summary()

rebuilt_matches = (before == after) and bool(before["cards"])
print(f"events_in_log={n_events}")
print(f"before_cards={sorted(before['cards'])}")
print(f"after_cards ={sorted(after['cards'])}")
print(f"rebuilt_matches={rebuilt_matches}")
assert rebuilt_matches, "replay did NOT reconstruct identical non-empty state"
print("REPLAY_PROOF: OK")
