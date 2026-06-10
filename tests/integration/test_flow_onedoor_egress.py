"""
FLOW — one-door egress end-to-end: a SEALED room can reach ONLY its allowlisted hosts, through the
governed gateway; everything else is blocked. Regression guard for FINDING-D (start_gateway now ensures
its networks). Deferred (live: real Docker networks + gateway + room + internet).
"""
import os
import tempfile

import pytest

pytestmark = pytest.mark.deferred


def test_flow_one_door_egress_allowlisted_only():
    import docker

    from leash import gateway
    from wall import network_enforcer as ne
    from wall import provisioner

    cli = docker.from_env()
    for name in ("thor-leash-gateway", "thor-upstream"):
        for c in cli.containers.list(all=True, filters={"name": name}):
            c.remove(force=True)

    wt = tempfile.mkdtemp(prefix="od-test-")
    os.chmod(wt, 0o777)
    room = None
    try:
        gateway.start_gateway(cli, leash_host_path=os.path.join(os.getcwd(), "leash"),
                              decision_log_dir="/tmp/leash-test", allowlist=("example.com",))
        room = provisioner.provision_room(task_type="build", feature_slice={"feature_id": "ODT"},
                                          worktree_host_path=wt, network_mode="one_door")
        c = cli.containers.get(room["room_id"])
        assert ne.assert_no_internet(c), "the room must be on the internal net ONLY (no direct internet)"

        def reach(url):
            code = ("import urllib.request as u\n"
                    "try:\n  print('OK', u.urlopen(%r, timeout=15).status)\n"
                    "except Exception as e:\n  print('BLOCKED', type(e).__name__)\n" % url)
            return c.exec_run(["python3", "-c", code], user="cook").output.decode().strip()

        assert reach("https://example.com").startswith("OK"), "an ALLOWLISTED host must be reachable"
        assert reach("https://www.google.com").startswith("BLOCKED"), "a NON-allowlisted host must be blocked"
    finally:
        if room:
            provisioner.destroy_room(room["room_id"], room.get("_mount_plan"))
        gateway.teardown(cli)
