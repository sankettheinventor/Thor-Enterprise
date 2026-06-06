"""
ONE-TIME smoke demonstration of the Wall's headline milestone: AC-1 + AC-2.

  AC-1 — a provisioned container runs a cook that creates a REAL commit on its branch
         (verified via `git log` ground-truth on the HOST, NOT the cook's word).
  AC-2 — from inside the container, a live network attempt FAILS (sealed-shut form:
         network_disabled=True — no route to the internet, the model API, or other rooms).

This is NOT the formal proving suite and NOT proving-as-you-go (Rule 2). It is a single
demonstration that the foundation works, run once, then we go straight back to building
(the Leash, Module 2, is next). It does NOT run the AC-3..AC-12 battery as a gate.

No faked or assumed results (Rule 11): every check prints the REAL observed outcome
(exit codes, the cook's SHA vs the host's SHA, the actual git log). A failure prints FAIL.

Run (inside the WSL venv, from ~/thor-enterprise):
    python tools/smoke_ac1_ac2.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Resolve to the repo root so provisioner.build_image() finds wall/image/ and bind paths are absolute.
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))   # make `wall` / `adapters` importable when run as a script
os.chdir(REPO)

import docker  # noqa: E402

from wall import provisioner  # noqa: E402


def sh(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def make_host_repo() -> str:
    """
    Create a standalone git repo on the HOST (a 'main' branch + one seed commit), mounted
    read-write at /work. The cook then makes a NEW commit on a feature branch INSIDE the
    sealed box; we verify that commit from host-side git — not from anything the cook reports.
    """
    repo = REPO / ".smoke" / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    sh("git", "init", "-q", "-b", "main", cwd=str(repo))
    sh("git", "-c", "user.email=host@thor.local", "-c", "user.name=host",
       "commit", "--allow-empty", "-q", "-m", "seed", cwd=str(repo))
    return str(repo)


def main() -> int:
    results: dict[str, bool] = {}

    print("== 1. build room image (needs network at BUILD time; the host has it) ==")
    print("   image id:", provisioner.build_image())

    repo = make_host_repo()
    print("   host repo:", repo)

    print("== 2. provision a sealed build room ==")
    room = provisioner.provision_room(
        task_type="build",
        feature_slice={"feature_id": "F001", "goals": ["hello"]},
        worktree_host_path=repo,
    )
    rid = room["room_id"]
    print("   provisioned:", {k: v for k, v in room.items() if not k.startswith("_")})

    client = docker.from_env()
    container = client.containers.get(rid)

    # ---- AC-2: the box is sealed. Docker ground-truth says no network, AND a live attempt fails. ----
    print("== 3. AC-2 — attempt a network call from INSIDE the sealed room (must FAIL) ==")
    netcheck = container.exec_run(
        ["python3", "-c",
         "import socket; socket.setdefaulttimeout(5); "
         "socket.create_connection(('1.1.1.1', 53)); print('REACHED')"],
        user="cook",
    )
    net_out = netcheck.output.decode(errors="replace").strip()
    ac2 = bool(room["sealed"]) and netcheck.exit_code != 0 and "REACHED" not in net_out
    results["AC-2 sealed — no escape"] = ac2
    print(f"   sealed(docker attr)={room['sealed']}  network attempt: exit={netcheck.exit_code}")
    print(f"   inside-room output: {net_out!r}")

    # ---- AC-1: the cook makes a REAL commit on its branch; verify from HOST git, not the cook. ----
    print("== 4. AC-1 — cook builds + commits inside the room ==")
    build = container.exec_run(
        ["bash", "-c",
         "cd /work && "
         "git -c user.email=cook@thor.local -c user.name='THOR Cook' checkout -q -b feature/smoke-ac1 && "
         "echo 'built by the cook inside the Wall' > built.txt && "
         "git add built.txt && "
         "git -c user.email=cook@thor.local -c user.name='THOR Cook' "
         "commit -q -m 'AC-1: cook builds inside the Wall [F001]' && "
         "git rev-parse HEAD"],
        user="cook",
    )
    cook_out = build.output.decode(errors="replace").strip()
    cook_sha = cook_out.splitlines()[-1] if (build.exit_code == 0 and cook_out) else ""

    # Independent verification from the HOST's view of the same repo (the ground-truth check):
    host_sha = sh("git", "-C", repo, "rev-parse", "feature/smoke-ac1").stdout.strip()
    log = sh("git", "-C", repo, "log", "--oneline", "feature/smoke-ac1").stdout.strip()
    ac1 = build.exit_code == 0 and bool(cook_sha) and host_sha == cook_sha
    results["AC-1 real commit on branch"] = ac1
    print(f"   cook exec exit={build.exit_code}  cook_sha={cook_sha[:12]}  host_sha={host_sha[:12]}")
    if build.exit_code != 0:
        print("   cook output:", cook_out)
    print("   host `git log feature/smoke-ac1`:")
    for line in log.splitlines():
        print("      ", line)

    # ---- destroy + confirm the branch persists after the container is gone (bonus: AC-7 shape) ----
    print("== 5. destroy the room; confirm container gone, branch persists ==")
    print("   destroyed:", provisioner.destroy_room(rid, room.get("_mount_plan")))
    gone = not client.containers.list(all=True, filters={"label": f"thor.room_id={rid}"})
    persists = sh("git", "-C", repo, "rev-parse", "feature/smoke-ac1").returncode == 0
    results["container removed"] = gone
    results["branch persists after destroy"] = persists

    print("\n==== SMOKE RESULTS (real, observed) ====")
    for k, v in results.items():
        print(f"   [{'PASS' if v else 'FAIL'}] {k}")
    headline = results.get("AC-1 real commit on branch") and results.get("AC-2 sealed — no escape")
    print(f"\n   HEADLINE (AC-1 + AC-2): {'PASS' if headline else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
