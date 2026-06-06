"""
The Wall — Acceptance Criteria AC-1..AC-12 (PRD §15).

⚠️ DEFERRED PROVING (P7 / Rule 2): these are written ALONGSIDE the build but are NOT run as a
gate on progress. They are skipped by default so a normal `pytest` run is green without making
any false claim. The real proving pass happens LATER, when THOR is whole — and each test below
must then verify against REALITY (git, docker, the network), never the cook's self-report.

Each AC is a stub with the exact verification it MUST perform, so the proving pass has a spec.
Nothing here fabricates a pass (Rule 11): an unimplemented check stays `skip`, never green.

To run the (currently skipped) suite intentionally:  pytest -m deferred --no-header
"""
import pytest

pytestmark = pytest.mark.deferred

DEFER = "deferred proving — do not gate progress (P7 / Rule 2); implement at the proving pass"


@pytest.mark.skip(reason=DEFER)
def test_ac1_real_commit_on_branch():
    """AC-1: a provisioned container runs a cook that creates a REAL commit on its branch
    (verified via `git log` ground-truth, NOT the cook's word). Headline milestone w/ AC-2."""


@pytest.mark.skip(reason=DEFER)
def test_ac2_egress_dropped_except_door():
    """AC-2: from inside the container, reaching any address other than :8001 is DROPPED
    (curl/dig/raw-socket all fail). Day-one form: network_disabled=True => no route at all."""


@pytest.mark.skip(reason=DEFER)
def test_ac3_cannot_read_host_fs():
    """AC-3: the cook cannot read the host FS outside its mounts (attempted reads fail)."""


@pytest.mark.skip(reason=DEFER)
def test_ac4_cannot_reach_other_room():
    """AC-4: the cook cannot reach another running room (attempted connection fails)."""


@pytest.mark.skip(reason=DEFER)
def test_ac5_task_slice_readonly():
    """AC-5: writing to /task/feature.json fails (read-only mount verified)."""


@pytest.mark.skip(reason=DEFER)
def test_ac6_checker_codebase_readonly():
    """AC-6: a checker room cannot modify the mounted codebase (read-only verified)."""


@pytest.mark.skip(reason=DEFER)
def test_ac7_destroy_preserves_branch():
    """AC-7: destroying a room removes the container but the branch persists (verified both
    ways: container gone via docker, branch present via gitea_adapter.branch_exists)."""


@pytest.mark.skip(reason=DEFER)
def test_ac8_crash_recovery_resumes():
    """AC-8: a crashed container is recovered by re-attaching the worktree + reloading state;
    work resumes (verified end-to-end)."""


@pytest.mark.skip(reason=DEFER)
def test_ac9_same_image_compose_and_k8s():
    """AC-9: the same OCI image runs on Docker Compose and on Kubernetes (verified on both)."""


@pytest.mark.skip(reason=DEFER)
def test_ac10_identity_rejects_forged_token():
    """AC-10: identity verification rejects a forged/stale token (negative test against
    wall.identity_stamper.IdentityStamper.verify)."""


@pytest.mark.skip(reason=DEFER)
def test_ac11_resource_limits_hold():
    """AC-11: a room cannot exceed its CPU/RAM/disk caps (stress test)."""


@pytest.mark.skip(reason=DEFER)
def test_ac12_no_orphans_after_destroy():
    """AC-12: no orphaned containers/networks/volumes remain after a destroy cycle
    (verified by LifecycleController.reap_orphans reconciliation finding nothing)."""
