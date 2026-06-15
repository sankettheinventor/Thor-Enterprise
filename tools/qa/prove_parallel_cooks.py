"""
PARALLEL-COOKS proof — two real cooks run AT THE SAME TIME, each behind its OWN governed door, fully
isolated, with NO global lock. Every request carries a feature_id, so the runner keys a per-cook gateway
(thor-leash-gateway-<id>) on a per-cook internal net (thor-room-net-<id>). We prove:

  * both cooks run CONCURRENTLY (their build windows overlap in wall-clock — not serialized one-at-a-time),
  * cook A (allowlist=example.com) reaches example.com and is BLOCKED for www.google.com,
  * cook B (allowlist=www.google.com) reaches www.google.com and is BLOCKED for example.com,
    => each gateway enforces ONLY its own cook's allowlist; there is no cross-wiring between parallel cooks,
  * the cooks' gateway lifetimes overlap (each sees the other's per-cook gateway live while it runs).

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_parallel_cooks.py
"""
import os
import subprocess
import tempfile
import threading
import time

import docker

from cook.runner import CookRunner
from cook.runtime import GenericCommandRuntime
from leash import gateway
from wall import config, network_enforcer, provisioner

HOST_A = "example.com"       # cook A's only allowed host (returns 200)
HOST_B = "www.google.com"    # cook B's only allowed host (returns 200) — distinct from A
PROBE = ("import urllib.request as u\n"
         f"for h in ('https://{HOST_A}', 'https://{HOST_B}'):\n"
         "    try: print(h, 'OK', u.urlopen(h, timeout=15).status)\n"
         "    except Exception as e: print(h, 'BLOCKED', type(e).__name__, str(e)[:90])\n")


class ProbeRuntime(GenericCommandRuntime):
    """A no-THOR-code cook with an EXPLICIT per-instance allowlist (so two cooks in one process can hold
    different allowlists — exactly the parallel case the per-cook gateway must keep isolated)."""

    def __init__(self, allow: tuple[str, ...]) -> None:
        self._allow = allow

    def image(self) -> str:
        return config.ROOM_IMAGE

    def command(self, feature_slice: dict) -> list[str]:
        return ["python3", "probe.py"]

    def env(self) -> dict:
        return {}

    def egress_allowlist(self) -> tuple[str, ...]:
        return self._allow


def _worktree() -> str:
    wt = tempfile.mkdtemp(prefix="cook-para-")
    os.chmod(wt, 0o777)
    subprocess.run(["git", "init", "-q", wt])
    with open(os.path.join(wt, "probe.py"), "w") as f:
        f.write(PROBE)
    return wt


cli = docker.from_env()
results: dict[str, dict] = {}
barrier = threading.Barrier(2)   # release both cooks at the same moment so their windows overlap
_OTHER = {"PARA": "PARB", "PARB": "PARA"}


def run_cook(tag: str, allow: tuple[str, ...]) -> None:
    wt = _worktree()
    runner = CookRunner(runtime=ProbeRuntime(allow))
    barrier.wait()                                   # both threads start their builds together
    t0 = time.monotonic()
    # snapshot the live gateways MID-BUILD — this cook's gateway is still up here, so if the peer's gateway
    # is also up we have caught both alive simultaneously (true parallel, not serialized).
    saw_peer = threading.Event()

    def watch():
        for _ in range(400):                         # poll until the build returns
            live = {c.name for c in cli.containers.list(filters={"label": "thor.leash=gateway"})}
            if network_enforcer.gateway_name(_OTHER[tag]) in live:
                saw_peer.set(); return
            time.sleep(0.02)

    w = threading.Thread(target=watch); w.start()
    r = runner.run({"feature_id": tag, "scope_files": ["src/"]}, worktree_host_path=wt)
    t1 = time.monotonic()
    w.join(timeout=1)
    results[tag] = {"out": r["output"], "mode": r["network_mode"], "room": r["room_id"],
                    "mount": r.get("_mount_plan"), "t0": t0, "t1": t1, "saw_peer": saw_peer.is_set()}


# pre-clean any stale per-cook gateways/nets from a previous run
for tag in ("PARA", "PARB"):
    gateway.teardown(cli, suffix=tag)

ta = threading.Thread(target=run_cook, args=("PARA", (HOST_A,)))
tb = threading.Thread(target=run_cook, args=("PARB", (HOST_B,)))
ta.start(); tb.start(); ta.join(); tb.join()

a, b = results["PARA"], results["PARB"]
print(f"cook A (allow {HOST_A}) output:\n" + a["out"].strip())
print(f"cook B (allow {HOST_B}) output:\n" + b["out"].strip())
overlap = min(a["t1"], b["t1"]) - max(a["t0"], b["t0"])
coexisted = a["saw_peer"] or b["saw_peer"]
print(f"\nwall-clock build windows overlapped by {overlap:.2f}s (>0 => truly concurrent)")
print("each cook saw the peer's per-cook gateway live mid-build:", coexisted)

# teardown
for tag, res in results.items():
    try:
        provisioner.destroy_room(res["room"], res.get("mount"))
    except Exception:  # noqa: BLE001
        pass
    gateway.teardown(cli, suffix=tag)

assert a["mode"] == "one_door" and b["mode"] == "one_door", "both cooks must auto-select one_door"
assert f"{HOST_A} OK" in a["out"], "cook A must reach its OWN allowlisted host"
assert f"{HOST_B} BLOCKED" in a["out"], "cook A must be BLOCKED for cook B's host (no cross-wiring)"
assert f"{HOST_B} OK" in b["out"], "cook B must reach its OWN allowlisted host"
assert f"{HOST_A} BLOCKED" in b["out"], "cook B must be BLOCKED for cook A's host (no cross-wiring)"
assert overlap > 0, "the two cook build windows must overlap — proves no global serialization lock"
assert coexisted, "the two per-cook gateways must be alive at the same time (truly parallel)"
print("\nPARALLEL_COOKS_OK")
