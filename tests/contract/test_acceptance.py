"""
The Task Handoff Contract — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 4). The six-message seam, slice minimality, direction/version/idempotency, and
amend-authority prove in-process; AC-3/AC-5/AC-12 verify the SAME suite over a REAL room via
docker-exec (the read-only slice mount). Deferred (live); run: pytest -m deferred tests/contract.
"""
import json

import pytest

from contract.messages import MessageError, validate
from contract.seam import ContractError, Seam, conformance_suite
from contract.slice_builder import build_slice, leaks_catalog
from contract.transport import DockerExecTransport, InProcessTransport

pytestmark = pytest.mark.deferred

FEATURE = {"feature_id": "F1", "task_type": "build", "goals": ["g"],
           "acceptance_criteria": ["ac1"], "scope_files": ["src/"]}


def _slice_dict():
    return build_slice(FEATURE).model_dump()


def _real_room(mgr, fid="F1"):
    # the Manager mounts its own read-only slice {"feature_id": fid} at /task/feature.json; that is
    # all AC-3 needs (read works, write fails). Slice minimality is proven in-proc by AC-2/AC-10.
    from wall import provisioner
    room = mgr.provision_room(fid, task_type="build", network_mode="sealed")
    return room, provisioner.client.containers.get(room["room_id"])


def test_ac1_only_six_messages_accepted():
    seam = Seam(InProcessTransport())
    assert seam.accept("provision") and seam.accept("claim_done")
    with pytest.raises(ContractError):
        seam.accept("self_certify")


def test_ac2_slice_one_feature_no_catalog():
    sl = build_slice(FEATURE)
    assert sl.feature_id == "F1"
    assert not leaks_catalog(sl, {"F2", "F3", "F99"})


def test_ac3_slice_readonly_write_fails(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    room, c = _real_room(mgr)
    try:
        t = DockerExecTransport(c)
        assert t.read_slice(room["room_id"])["feature_id"] == "F1"   # slice readable over docker-exec
        assert t.attempt_write_slice(room["room_id"]) is False        # write FAILS — read-only mount
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_ac4_no_self_certify_path():
    from contract.messages import ClaimDone
    assert "done" not in ClaimDone.model_fields and "verdict" not in ClaimDone.model_fields
    seam = Seam(InProcessTransport())
    with pytest.raises(ContractError):  # a room cannot issue the authoritative done
        seam.room_send("result_decision", {"room_id": "r", "feature_id": "F1",
                                           "decision": "approved", "message_id": "m"})


def test_ac5_same_suite_both_transports(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    assert conformance_suite(Seam(InProcessTransport(), manager=mgr), "room-X", _slice_dict()) is True
    room, c = _real_room(mgr)
    try:
        assert conformance_suite(Seam(DockerExecTransport(c), manager=mgr),
                                 room["room_id"], _slice_dict()) is True
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))


def test_ac6_malformed_rejected():
    with pytest.raises(MessageError):
        validate("status", {"room_id": "r", "state": "not-a-valid-state"})
    with pytest.raises(MessageError):
        validate("claim_done", {"room_id": "r", "feature_id": "F1", "message_id": "m", "extra": 1})


def test_ac7_amend_authority():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from wall.identity_stamper import _b64

    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    change = {"add_scope": "tests/"}
    material = f"amend|room-1|{json.dumps(change, sort_keys=True)}"
    seam = Seam(InProcessTransport())

    with pytest.raises(ContractError):  # agent-originated (no authority) → rejected
        seam.manager_send("amend", {"room_id": "room-1", "change": change, "human_authority": {}})
    ok = seam.manager_send("amend", {"room_id": "room-1", "change": change,
                                     "human_authority": {"signer_pub": pub,
                                                         "signature": _b64(priv.sign(material.encode()))}})
    assert ok["ack"] is True


def test_ac8_duplicate_claim_one_verdict():
    seam = Seam(InProcessTransport())
    p = {"room_id": "r", "feature_id": "F1", "message_id": "knock-1"}
    seam.room_send("claim_done", p)
    seam.room_send("claim_done", p)   # duplicate knock
    assert seam.verdicts == 1


def test_ac9_version_mismatch_clean_fail():
    seam = Seam(InProcessTransport())
    with pytest.raises(ContractError, match="version"):
        seam.negotiate_version("0.9")


def test_ac10_no_credentials_or_other_room_data():
    # extra/sensitive fields are dropped by the whitelist — never forwarded across the seam
    dirty = {**FEATURE, "aws_secret": "AKIA...", "other_feature": "F2", "roadmap": ["F2", "F3"]}
    sl = build_slice(dirty)
    blob = sl.model_dump_json()
    assert "AKIA" not in blob and "roadmap" not in blob and "F2" not in blob


def test_ac11_every_message_recorded_event(fresh_ledger):
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    conformance_suite(Seam(InProcessTransport(), manager=mgr), "room-Y", _slice_dict())
    contract_events = [e for e in mgr.eventlog.all_events() if e["event_type"].startswith("contract.")]
    kinds = {e["event_type"] for e in contract_events}
    assert {"contract.assign_task", "contract.status", "contract.claim_done",
            "contract.result_decision"} <= kinds


def test_ac12_transport_swap_no_logic_change(fresh_ledger):
    # the IDENTICAL conformance_suite code runs over both transports; switching changes nothing.
    from manager.core import ThorManager
    mgr = ThorManager(fresh_ledger)
    in_proc = conformance_suite(Seam(InProcessTransport(), manager=mgr), "room-Z", _slice_dict())
    room, c = _real_room(mgr)
    try:
        docker = conformance_suite(Seam(DockerExecTransport(c), manager=mgr), room["room_id"], _slice_dict())
        assert in_proc == docker is True
    finally:
        mgr.destroy_room(room["room_id"], room.get("_mount_plan"))
