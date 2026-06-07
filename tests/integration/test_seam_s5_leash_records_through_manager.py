"""
Seam S5 — Leash → Manager (record each decision).  Gaps H7 + H6.

Proves the split-brain is gone: the Leash's DecisionRecorder records THROUGH the Manager (the
single signed ledger), not its own local `.thor/eventlog.jsonl` chain. Verified against REALITY —
a real Postgres-backed Manager, a real proxy decision — and asserts the decision_id is preserved.

Deferred (needs Postgres). Run in the proving pass:  pytest -m deferred tests/integration
"""
import json
import os
import tempfile

import pytest

pytestmark = pytest.mark.deferred


@pytest.fixture
def manager():
    try:
        import docker
        from manager import db, pg
        from manager.core import ThorManager
        pg.start(docker.from_env())
        conn = db.connect()
        db.init_schema(conn)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"postgres/docker unavailable: {e}")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE eventlog, rooms, cards, features")
    conn.commit()
    return ThorManager(conn)


def test_seam_S5_leash_records_through_manager(manager):
    from adapters import agt_adapter
    from leash.decision import DecisionRecorder
    from leash.policy import FrozenPolicy
    from leash.proxy import InRoomProxy

    # the old local second ledger must NOT exist / be written
    local_ledger = os.path.join(os.getcwd(), ".thor", "eventlog.jsonl")
    before_local = os.path.exists(local_ledger)

    agt_adapter.load_policy(FrozenPolicy(
        room_id="room-s5", scope_files=("src/",), forbidden_patterns=("infra/",), frozen_at=0.0))
    work = tempfile.mkdtemp(prefix="s5-")
    recorder = DecisionRecorder(manager)        # sinks THROUGH the Manager (H7)
    proxy = InRoomProxy(agt_adapter, recorder, work)

    n_before = manager.eventlog.count()
    res = proxy.handle_tool_call(
        {"name": "write_file", "room_id": "room-s5", "args": {"path": "src/ok.py", "content": "# ok"}})
    assert res["status"] == "allow"

    events = manager.eventlog.all_events()
    assert len(events) == n_before + 1, "exactly one decision event, in the Manager's single ledger"
    ev = events[-1]
    assert ev["event_type"] == "action.decided" and ev["actor"] == "leash"

    payload = json.loads(ev["payload"])
    assert payload["decision_id"], "the Leash decision_id must be preserved through the Manager (H7)"
    assert payload["decision"] == "allow"

    # no second ledger was created by the recording path (the split-brain chain is retired)
    assert os.path.exists(local_ledger) == before_local, "the Leash must not write a local .thor/eventlog.jsonl"
    # the single ledger is intact + signed
    assert manager.eventlog.verify_chain() is True
