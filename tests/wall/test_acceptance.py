"""
The Wall — Acceptance Criteria AC-1..AC-12 (PRD §15).

PROVING PASS (Task 1). These verify the Wall against REALITY — real Docker containers, real
git history, the real Ed25519 verifier — never the cook's self-report (Rule 11: an unprovable
check stays skipped, never green). They carry `pytest.mark.deferred`, so they are NOT part of a
default `pytest` run; the proving suite is run intentionally:

    pytest -m deferred tests/wall --no-header

10 of 12 ACs are provable now against Module 1 (the Wall) + Docker + git. Two remain honestly
deferred with a named reason:
  - AC-8 (crash recovery) needs the Manager's re-attach/reload flow (Task 3+).
  - AC-9 (k8s parity) needs a real Kubernetes cluster (absent in the WSL dev env).

Day-one phasing note (Rule 9): the network is SEALED SHUT (network_disabled=True). AC-2/AC-4
are proven in that sealed-shut form today; the one-door (:8001) upgrade lands with the Leash
(Module 2) and tightens — never loosens — the same guarantee.
"""
import os
import subprocess
import tempfile
from contextlib import contextmanager

import pytest

pytestmark = pytest.mark.deferred


# --------------------------------------------------------------------------------------------
# helpers — all docker/wall imports are LAZY so a default (docker-free) pytest run is unaffected
# --------------------------------------------------------------------------------------------
_DK = {}


@pytest.fixture(autouse=True)
def _need_docker():
    """Skip the proving suite (don't error) if no Docker daemon is reachable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        _DK["client"] = client
    except Exception as e:  # noqa: BLE001 - any docker failure => skip, never a false pass
        pytest.skip(f"docker daemon unavailable: {e}")


def _client():
    return _DK["client"]


def _run(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)


def _exec(container, script, user="cook"):
    """Run a shell line inside the room as the unprivileged cook; return (rc, combined output)."""
    res = container.exec_run(["bash", "-lc", script], user=user)
    return res.exit_code, res.output.decode(errors="replace")


@contextmanager
def room(**kwargs):
    """Provision a REAL room via the Wall and guarantee teardown."""
    from wall import provisioner

    r = provisioner.provision_room(**kwargs)
    try:
        yield r, _client().containers.get(r["room_id"])
    finally:
        provisioner.destroy_room(r["room_id"], r.get("_mount_plan"))


def _git_worktree(branch):
    """A fresh host git repo on `branch` — the read-write worktree the cook builds in (FR-8)."""
    d = tempfile.mkdtemp(prefix="thor-ac-")
    os.chmod(d, 0o777)
    _run(f"git init -q {d}")
    _run(f'git -C {d} config user.email cook@thor.local; git -C {d} config user.name "THOR Cook"')
    _run(f"git -C {d} checkout -q -b {branch}")
    return d


_COMMIT = (
    "export HOME=/home/cook; git config --global --add safe.directory /work; "
    "cd /work && echo '{body}' > {f} && git add {f} && "
    "git commit -q -m '{msg}' && git rev-parse HEAD"
)


# --------------------------------------------------------------------------------------------
# AC-1 .. AC-12
# --------------------------------------------------------------------------------------------
def test_ac1_real_commit_on_branch():
    """AC-1: a provisioned room runs a cook that creates a REAL commit on its branch — verified
    via host `git log` ground-truth, NOT the cook's word."""
    work = _git_worktree("room/F-ac1")
    with room(task_type="build", feature_slice={"feature_id": "F-ac1"},
              worktree_host_path=work) as (r, c):
        rc, out = _exec(c, _COMMIT.format(body="real build", f="BUILT.txt", msg="cook commit"))
        assert rc == 0, out
        in_room_head = out.strip().splitlines()[-1]
    # checked AFTER the room is destroyed: the commit is real and persisted in git, not in-memory
    host_head = _run("git -C %s rev-parse room/F-ac1" % work).stdout.strip()
    assert host_head == in_room_head, "in-room HEAD must equal host git ground-truth"
    assert "BUILT.txt" in _run(f"git -C {work} show --stat room/F-ac1").stdout


def test_ac2_egress_dropped_except_door():
    """AC-2: from inside the room, the internet/model-API/other rooms are unreachable. Day-one
    sealed-shut form: network_disabled=True => no route at all. Verified from INSIDE + ground-truth."""
    from wall import network_enforcer

    with room(task_type="build", feature_slice={"feature_id": "F-ac2"}) as (r, c):
        assert r["sealed"] is True
        rc, out = _exec(c, "getent hosts github.com >/dev/null 2>&1 && echo OPEN || echo SEALED")
        assert out.strip() == "SEALED", out
        assert network_enforcer.assert_sealed(c) is True  # no attached network has an IP


def test_ac3_cannot_read_host_fs():
    """AC-3: the cook cannot read host files outside its mounts."""
    secret = tempfile.NamedTemporaryFile("w", prefix="host-secret-", suffix=".txt", delete=False)
    secret.write("TOPSECRET-HOST-VALUE")
    secret.close()
    try:
        with room(task_type="build", feature_slice={"feature_id": "F-ac3"}) as (r, c):
            rc, out = _exec(c, f"cat {secret.name} 2>&1 || echo NO-ACCESS")
            assert "TOPSECRET-HOST-VALUE" not in out
            assert "NO-ACCESS" in out or "No such file" in out
    finally:
        os.unlink(secret.name)


def test_ac4_cannot_reach_other_room():
    """AC-4: the cook cannot reach another running room. Sealed-shut form: the room has no global
    network address at all, so there is no path to any peer."""
    with room(task_type="build", feature_slice={"feature_id": "F-ac4a"}) as (ra, ca), \
         room(task_type="build", feature_slice={"feature_id": "F-ac4b"}) as (rb, cb):
        rc, out = _exec(ca, "ip -o addr show scope global 2>/dev/null | wc -l")
        assert out.strip() == "0", f"a sealed room must have no global address; got {out!r}"


def test_ac5_task_slice_readonly():
    """AC-5: the feature slice is mounted read-only — a write to /task/feature.json fails at the
    kernel/FS layer (FR-6). The cook cannot edit its own scope."""
    with room(task_type="build",
              feature_slice={"feature_id": "F-ac5", "goals": ["x"]}) as (r, c):
        rc, rd = _exec(c, "cat /task/feature.json")
        assert "F-ac5" in rd
        rc, wr = _exec(c, "echo tamper >> /task/feature.json 2>&1 || echo RO-DENIED")
        assert "RO-DENIED" in wr or "Read-only" in wr, wr


def test_ac6_checker_codebase_readonly():
    """AC-6: a checker room mounts the codebase READ-ONLY and cannot modify it (FR-9)."""
    code = tempfile.mkdtemp(prefix="codebase-")
    with open(os.path.join(code, "app.py"), "w") as f:
        f.write("print(1)\n")
    with room(task_type="checker", feature_slice={"feature_id": "F-ac6"},
              codebase_host_path=code) as (r, c):
        rc, rd = _exec(c, "cat /codebase/app.py")
        assert "print(1)" in rd
        rc, wr = _exec(c, "echo hacked >> /codebase/app.py 2>&1 || echo RO-DENIED")
        assert "RO-DENIED" in wr or "Read-only" in wr, wr
    with open(os.path.join(code, "app.py")) as f:
        assert f.read() == "print(1)\n", "host codebase must be untouched"


def test_ac7_destroy_preserves_branch():
    """AC-7: destroying a room removes the container (docker ground-truth) but the branch persists
    in git."""
    from wall import provisioner

    work = _git_worktree("room/F-ac7")
    r = provisioner.provision_room(task_type="build",
                                   feature_slice={"feature_id": "F-ac7"},
                                   worktree_host_path=work)
    c = _client().containers.get(r["room_id"])
    _exec(c, _COMMIT.format(body="wip", f="WIP.txt", msg="wip"))
    head = _run(f"git -C {work} rev-parse room/F-ac7").stdout.strip()

    res = provisioner.destroy_room(r["room_id"], r.get("_mount_plan"))
    assert res["status"] == "destroyed" and res["branch_preserved"] is True
    gone = _client().containers.list(all=True,
                                     filters={"label": f"thor.room_id={r['room_id']}"})
    assert gone == [], "container must be gone from Docker"
    assert _run(f"git -C {work} rev-parse room/F-ac7").stdout.strip() == head, "branch must persist"


@pytest.mark.skip(
    reason="AC-8 crash-recovery (re-attach worktree + reload state, resume work) needs the "
    "Manager's recovery flow — lands with Manager wiring (Task 3+). No fake green (Rule 11)."
)
def test_ac8_crash_recovery_resumes():
    """AC-8: a crashed container is recovered by re-attaching the worktree + reloading state."""


@pytest.mark.skip(
    reason="AC-9 k8s parity needs a real Kubernetes cluster (absent in the WSL dev env). The same "
    "OCI image runs on Compose today; k8s parity is proven at the deploy pass. No fake green (Rule 11)."
)
def test_ac9_same_image_compose_and_k8s():
    """AC-9: the same OCI image runs on Docker Compose and on Kubernetes."""


def test_ac10_identity_rejects_forged_token():
    """AC-10: identity verification accepts a genuine token and rejects forged/stale/wrong-room/
    wrong-key tokens (negative test against wall.identity_stamper.IdentityStamper.verify)."""
    from wall.identity_stamper import IdentityStamper

    s = IdentityStamper()
    tok = s.stamp("room-xyz", "build")
    assert s.verify(tok, expect_room_id="room-xyz") is True
    assert s.verify(tok, expect_room_id="room-OTHER") is False     # right key, wrong room
    assert s.verify(tok[:-4] + "AAAA") is False                    # tampered signature
    assert s.verify("garbage.token") is False                      # malformed
    other = IdentityStamper(key_path=tempfile.mktemp(suffix=".pem"))
    assert s.verify(other.stamp("room-xyz", "build")) is False     # signed by a DIFFERENT key


def test_ac11_resource_limits_hold():
    """AC-11: a room cannot exceed its caps. Ground-truth: the caps are really applied (docker
    inspect); stress: allocating past the RAM cap is OOM-killed, not allowed to exceed (FR-11)."""
    with room(task_type="build", feature_slice={"feature_id": "F-ac11"},
              mem="64m", cpu=0.5) as (r, c):
        c.reload()
        hc = c.attrs["HostConfig"]
        assert hc["Memory"] == 64 * 1024 * 1024, hc["Memory"]      # cap really applied
        assert hc["NanoCpus"] == int(0.5 * 1e9), hc["NanoCpus"]
        rc, out = _exec(
            c, "python3 -c \"a=bytearray(300*1024*1024)\" 2>&1; echo rc=$?"
        )
        assert "rc=0" not in out, f"allocation past the cap must fail (OOM), got: {out!r}"


def test_ac12_no_orphans_after_destroy():
    """AC-12: no orphaned container remains after a destroy cycle, and the reconciliation reaper
    finds nothing left behind (LifecycleController.reap_orphans)."""
    from wall import provisioner

    r = provisioner.provision_room(task_type="build", feature_slice={"feature_id": "F-ac12"})
    rid = r["room_id"]
    provisioner.destroy_room(rid, r.get("_mount_plan"))
    left = _client().containers.list(all=True, filters={"label": f"thor.room_id={rid}"})
    assert left == [], "no orphan container after destroy"
    reaped = provisioner._lifecycle.reap_orphans(known_room_ids=set())
    assert rid not in reaped, "destroyed room must not reappear as a reapable orphan"
