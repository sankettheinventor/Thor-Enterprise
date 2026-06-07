"""
The THOR Manager — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 2). Verified against REALITY — a real Postgres-backed Manager, real Ed25519
signatures, real sealed Docker rooms — never a stand-in. Deferred from the default run (P7/Rule 2);
run intentionally:  pytest -m deferred tests/manager

11 of 12 ACs prove now. AC-6 (claim_done → QA → verdict) needs the GovernanceEngine Verdict
Coordinator (Module 6 / Task 5) and stays honestly skipped — no fake green (Rule 11).
"""
import json
import tempfile

import pytest

pytestmark = pytest.mark.deferred


def _operator_keys():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64
    priv = Ed25519PrivateKey.generate()
    pub_b64 = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub_b64


def _sign(priv, material: str) -> str:
    from wall.identity_stamper import _b64
    return _b64(priv.sign(material.encode()))


@pytest.fixture
def mgr():
    """A real Postgres-backed Manager on a clean ledger; destroys any rooms it created."""
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
    m = ThorManager(conn)
    yield m
    from wall import provisioner
    with conn.cursor() as cur:
        cur.execute("SELECT room_id FROM rooms")
        ids = [r[0] for r in cur.fetchall()]
    for rid in ids:
        try:
            provisioner.destroy_room(rid)
        except Exception:  # noqa: BLE001
            pass


def test_ac1_only_manager_writes_eventlog(mgr):
    """AC-1: other components record THROUGH the Manager — a Leash decision lands as an
    `action.decided` event written by the Manager (actor=leash), in the one ledger."""
    from adapters import agt_adapter
    from leash.decision import DecisionRecorder
    from leash.policy import FrozenPolicy
    from leash.proxy import InRoomProxy

    agt_adapter.load_policy(FrozenPolicy(
        room_id="room-ac1", scope_files=("src/",), forbidden_patterns=("infra/",), frozen_at=0.0))
    work = tempfile.mkdtemp(prefix="mgr-ac1-")
    proxy = InRoomProxy(agt_adapter, DecisionRecorder(mgr), work)
    proxy.handle_tool_call({"name": "write_file", "room_id": "room-ac1",
                            "args": {"path": "src/ok.py", "content": "# ok"}})
    proxy.handle_tool_call({"name": "write_file", "room_id": "room-ac1",
                            "args": {"path": "infra/secret.tf", "content": "leak"}})
    with mgr.conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM eventlog WHERE event_type='action.decided' AND actor='leash'")
        decided = cur.fetchone()[0]
    assert decided == 2


def test_ac2_signed_chain_tamper_evident(mgr):
    """AC-2: the signed hash chain verifies; altering a past event breaks verify_chain."""
    mgr.add_feature("F1", "x")
    assert mgr.eventlog.verify_chain() is True
    with mgr.conn.cursor() as cur:
        cur.execute("UPDATE eventlog SET payload=%s WHERE seq=0", ('{"tampered":true}',))
    mgr.conn.commit()
    assert mgr.eventlog.verify_chain() is False


def test_ac3_replay_rebuilds_exact_state(mgr):
    """AC-3: capture state, then a 'restarted' Manager rebuilds the EXACT registry/cards/features
    purely by replaying the durable log (the real M1 path)."""
    from manager.core import ThorManager
    from manager import db

    mgr.add_feature("F300", "build F300")
    mgr.set_feature_status("F300", "ready")
    mgr.raise_card("plan", "F300", {"summary": "plan"})
    mgr.provision_room("F300", task_type="build", network_mode="sealed")  # real sealed room
    s1 = mgr.state_summary()

    mgr2 = ThorManager(db.connect(), stamper=mgr.stamper)  # restart on the same DB
    mgr2.rebuild_from_log()                                 # projections rebuilt purely by replay
    s2 = mgr2.state_summary()
    assert s1 == s2 and s1["rooms"] and s1["cards"], "replay must reconstruct identical non-empty state"


def test_ac4_signature_gates_the_plan(mgr):
    """AC-4: a card is not approved until a VALID operator signature gates it."""
    priv, pub = _operator_keys()
    card = mgr.raise_card("plan", "F300", {"summary": "plan"})
    assert mgr.is_card_approved(card) is False
    from manager.core import ThorManager
    material = ThorManager.card_material(card, {"summary": "plan"})
    mgr.approve(card, _sign(priv, material), pub)
    assert mgr.is_card_approved(card) is True


def test_ac5_forged_signature_rejected_card_stays_open(mgr):
    """AC-5: a forged/wrong-material signature is rejected and the card stays open."""
    priv, pub = _operator_keys()
    card = mgr.raise_card("plan", "F300", {"summary": "plan"})
    res = mgr.approve(card, _sign(priv, "wrong material"), pub)
    assert res["verified"] is False
    assert mgr.is_card_approved(card) is False


@pytest.mark.skip(
    reason="AC-6 claim_done → QA → verdict needs the GovernanceEngine Verdict Coordinator "
    "(Module 6 / Task 5). No fake green (Rule 11)."
)
def test_ac6_claim_done_drives_qa_then_verdict():
    """AC-6: on claim_done, QA then verdict; never merged on the agent's claim."""


def test_ac7_eventlog_unwritable_fail_closed(mgr):
    """AC-7: with the EventLog unwritable, the Manager refuses governed actions (no unaudited action)."""
    from manager.core import FailClosed

    n_before = mgr.eventlog.count()
    mgr.set_eventlog_writable(False)
    refused = False
    try:
        mgr.record_decision(
            type("V", (), {"decision": "allow", "reason": "x", "classification": "non_critical"})(),
            {"room_id": "room-ac7", "type": "tool_call", "name": "write_file", "target": "src/x.py"})
    except FailClosed:
        refused = True
    mgr.set_eventlog_writable(True)
    assert refused and mgr.eventlog.count() == n_before


def test_ac8_bad_identity_token_refused(mgr):
    """AC-8: a good room identity token is trusted; a forged one is refused."""
    room = mgr.provision_room("F100", task_type="build", network_mode="sealed")
    assert mgr.verify_room_identity(room["room_id"], room["identity_token"]) is True
    assert mgr.verify_room_identity(room["room_id"], "forged.token") is False


def test_ac9_second_provision_same_branch_refused(mgr):
    """AC-9: a second provision on an already-owned branch is refused (one-branch-one-room)."""
    mgr.provision_room("F100", task_type="build", network_mode="sealed")
    with pytest.raises(ValueError, match="one-branch-one-room"):
        mgr.provision_room("F100", task_type="build", network_mode="sealed")


def test_ac10_sentinel_reads_true_health(mgr):
    """AC-10: the Manager reports truthful health incl. eventlog-writable + postgres."""
    h = mgr.health()
    assert h["alive"] and h["responsive"] and h["eventlog_writable"] and h["deps"]["postgres"]


def test_ac11_escalated_card_never_auto_resolved(mgr):
    """AC-11: an escalated (held) card stays held with no human action."""
    card = mgr.raise_card("critical", "F400", {"what": "dependency add"}, held=True)
    assert mgr._get_card(card)["status"] == "held"


def test_ac12_duplicate_appends_idempotent(mgr):
    """AC-12: duplicate event appends (retries) are idempotent; the chain gains no duplicate."""
    n0 = mgr.eventlog.count()
    mgr.eventlog.append("test.retry", {"x": 1}, client_id="DUP-1")
    n1 = mgr.eventlog.count()
    dup = mgr.eventlog.append("test.retry", {"x": 1}, client_id="DUP-1")
    n2 = mgr.eventlog.count()
    assert n1 == n0 + 1 and n2 == n1 and dup.get("idempotent")
