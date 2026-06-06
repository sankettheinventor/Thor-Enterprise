"""
ONE-TIME smoke demonstration of the Task Handoff Contract (Module 5).

Headline (PRD §15): AC-2 + AC-4 — a room briefed with only its one feature, read-only, with
structurally no way to declare itself done. Part A is pure schema/seam logic; Part B drives the
REAL Manager + a REAL room (slice via `docker exec cat`, read-only write attempt, events in the log).

NOT the formal proving suite (Rule 2). No faked results (Rule 11).

Run (inside the WSL venv, from ~/thor-enterprise):  python tools/smoke_contract.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import docker
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from contract.messages import CONTRACT_VERSION, ClaimDone, MessageError, validate
from contract.seam import ContractError, Seam, conformance_suite
from contract.slice_builder import build_slice, leaks_catalog
from contract.transport import DockerExecTransport, InProcessTransport
from wall.identity_stamper import _b64

CATALOG = {
    "F047": {"feature_id": "F047", "task_type": "build", "context": "login form",
             "goals": ["users can log in"], "acceptance_criteria": ["valid creds → session"],
             "capability_tags": ["ui-form", "auth"]},
    "F045": {"feature_id": "F045"}, "F046": {"feature_id": "F046"}, "F048": {"feature_id": "F048"},
}
OTHER_IDS = {"F045", "F046", "F048"}


def operator_keys():
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    return priv, pub


def part_a() -> tuple[dict, dict]:
    results: dict[str, bool] = {}
    slice_obj = build_slice(CATALOG["F047"], policy={"scope_files": ["src/auth/"]})
    slice_dict = slice_obj.model_dump()

    print("== AC-1 — only the six messages are accepted; a seventh is rejected ==")
    seam = Seam(InProcessTransport())
    ok_six = seam.accept("assign_task")
    try:
        seam.accept("hack_the_room")
        rej = False
    except ContractError:
        rej = True
    results["AC-1 only six messages accepted"] = ok_six and rej

    print("== AC-4 — no self-certify path (claim_done has no verdict field; room can't issue verdict) ==")
    no_verdict_field = not ({"done", "verdict", "result", "decision", "approved"}
                            & set(ClaimDone.model_fields))
    try:
        seam.room_send("result_decision", {"room_id": "r1", "feature_id": "F047",
                                           "decision": "approved", "message_id": "x"})
        room_issued_verdict = True
    except ContractError:
        room_issued_verdict = False
    results["AC-4 no self-certify path"] = no_verdict_field and not room_issued_verdict
    print(f"   claim_done fields={set(ClaimDone.model_fields)}  room_can_issue_verdict={room_issued_verdict}")

    print("== AC-5 (in-process) — the six-message suite passes over the in-process transport ==")
    results["AC-5a in-process conformance"] = conformance_suite(Seam(InProcessTransport()), "r1", slice_dict)

    print("== AC-6 — a malformed message is rejected ==")
    try:
        seam.manager_send("assign_task", {"room_id": "r1",
                          "feature_slice": {"feature_id": "F", "task_type": "build", "bogus": 1}})
        results["AC-6 malformed rejected"] = False
    except MessageError as e:
        results["AC-6 malformed rejected"] = True
        print(f"   rejected extra field: {str(e)[:60]}...")

    print("== AC-7 — amend: human authority applied, agent-originated rejected ==")
    priv, pub = operator_keys()
    room_id, change = "r1", {"scope_add": ["src/new.js"]}
    material = f"amend|{room_id}|{json.dumps(change, sort_keys=True)}"
    good_auth = {"signer_pub": pub, "signature": _b64(priv.sign(material.encode()))}
    bad_auth = {"signer_pub": pub, "signature": _b64(priv.sign(b"forged"))}
    applied = seam.manager_send("amend", {"room_id": room_id, "change": change,
                                          "human_authority": good_auth})["ack"]
    try:
        seam.manager_send("amend", {"room_id": room_id, "change": change, "human_authority": bad_auth})
        agent_amend_rejected = False
    except ContractError:
        agent_amend_rejected = True
    results["AC-7 amend authority enforced"] = applied and agent_amend_rejected

    print("== AC-8 — duplicate claim_done → exactly one verdict ==")
    s8 = Seam(InProcessTransport())
    for _ in range(3):
        s8.room_send("claim_done", {"room_id": "r1", "feature_id": "F047", "message_id": "knock-dup"})
    results["AC-8 idempotent claim → one verdict"] = (s8.verdicts == 1)
    print(f"   3 identical claim_done → verdicts={s8.verdicts}")

    print("== AC-9 — version mismatch fails cleanly ==")
    try:
        Seam(InProcessTransport()).negotiate_version("9.9")
        bad_ver = False
    except ContractError:
        bad_ver = True
    good_ver = Seam(InProcessTransport()).negotiate_version(CONTRACT_VERSION)
    results["AC-9 version mismatch clean fail"] = bad_ver and good_ver

    print("== AC-10 — no credentials / other-room data cross (schema forbids) ==")
    try:
        validate("result_decision", {"room_id": "r1", "feature_id": "F047", "decision": "approved",
                                     "message_id": "x", "credentials": "SECRET"})
        cred_rejected = False
    except MessageError:
        cred_rejected = True
    slice_clean = not leaks_catalog(slice_obj, OTHER_IDS) and "credentials" not in slice_obj.model_dump_json()
    results["AC-10 no creds / no catalog leak"] = cred_rejected and slice_clean

    return results, slice_dict


def part_b(slice_dict: dict) -> dict:
    """Real Manager + real room: AC-2 (one-feature slice), AC-3 (read-only), AC-5(docker), AC-11."""
    from manager import db, pg
    from manager.core import ThorManager
    from wall import provisioner

    results: dict[str, bool] = {}
    client = docker.from_env()
    room_id = None
    mount_plan = None
    try:
        print("== Part B: real Manager + real room ==")
        pg.start(client)
        conn = db.connect()
        db.init_schema(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE eventlog, rooms, cards, features")
        mgr = ThorManager(conn)

        # provision a REAL room with the FULL slice mounted read-only at /task/feature.json
        room = provisioner.provision_room(task_type="build", network_mode="sealed",
                                          feature_slice=slice_dict)
        room_id = room["room_id"]
        mount_plan = room.get("_mount_plan")
        container = client.containers.get(room_id)
        transport = DockerExecTransport(container)

        print("== AC-2 — the room's slice has exactly one feature; no catalog / other features ==")
        delivered = transport.read_slice(room_id)
        one_feature = delivered is not None and delivered.get("feature_id") == "F047"
        no_leak = not any(fid in json.dumps(delivered) for fid in OTHER_IDS)
        results["AC-2 one-feature slice, no catalog"] = one_feature and no_leak
        print(f"   /task/feature.json feature_id={delivered.get('feature_id')}  leaks_other={not no_leak}")

        print("== AC-3 — writing /task/feature.json from inside the room fails (read-only) ==")
        wrote = transport.attempt_write_slice(room_id)
        results["AC-3 slice read-only (write fails)"] = not wrote
        print(f"   write succeeded={wrote} (expected False)")

        print("== AC-5 (docker-exec) — the SAME six-message suite passes over docker-exec ==")
        seam = Seam(transport, manager=mgr)
        results["AC-5b docker-exec conformance"] = conformance_suite(seam, room_id, slice_dict)

        print("== AC-11 — every seam message is recorded as an event in the Manager EventLog ==")
        with conn.cursor() as cur:
            cur.execute("SELECT event_type FROM eventlog WHERE event_type LIKE 'contract.%' ORDER BY seq")
            evs = [r[0] for r in cur.fetchall()]
        results["AC-11 messages recorded as events"] = (
            {"contract.assign_task", "contract.status", "contract.claim_done",
             "contract.result_decision"} <= set(evs))
        print(f"   contract events in EventLog: {evs}")

        return results
    finally:
        if room_id:
            try:
                provisioner.destroy_room(room_id, mount_plan)
            except Exception:  # noqa: BLE001
                pass
        pg.stop(client)


def main() -> int:
    print("########## PART A — schema + seam logic ##########")
    results, slice_dict = part_a()
    print("\n########## PART B — real Manager + real room ##########")
    try:
        results.update(part_b(slice_dict))
    except Exception as e:  # noqa: BLE001 - report honestly
        print(f"   PART B ERROR: {e}")
        results["PART B integration"] = False

    # AC-5 (both transports) and AC-12 (same suite/seam over both → no logic change)
    results["AC-5 same suite on both transports"] = bool(
        results.get("AC-5a in-process conformance") and results.get("AC-5b docker-exec conformance"))
    results["AC-12 transport swap, no logic change"] = results["AC-5 same suite on both transports"]

    print("\n==== CONTRACT SMOKE RESULTS (real, observed) ====")
    for k, v in results.items():
        print(f"   [{'PASS' if v else 'FAIL'}] {k}")
    headline = results.get("AC-2 one-feature slice, no catalog") and results.get("AC-4 no self-certify path")
    print(f"\n   HEADLINE (AC-2 + AC-4: one-feature read-only + no self-certify): "
          f"{'PASS' if headline else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
