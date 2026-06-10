"""
CookRunner ties the selected runtime to a room: provision with the agent's image, run the agent as the
unprivileged cook, collect the result. Docker-free (fake provisioner + fake docker client).
"""
import cook.runner as runner_mod
from cook.runner import CookRunner

SLICE = {"feature_id": "F", "scope_files": ["src/"]}


def test_plan_is_docker_free_and_auditable(monkeypatch):
    monkeypatch.setenv("THOR_COOK", "generic")
    monkeypatch.setenv("THOR_COOK_IMAGE", "agent:latest")
    monkeypatch.setenv("THOR_COOK_CMD", "agent build {task}")
    p = CookRunner().plan(SLICE)
    assert p["runtime"] == "generic" and p["image"] == "agent:latest"
    assert p["command"][:2] == ["agent", "build"]


class _FakeContainer:
    def __init__(self):
        self.calls = []

    def exec_run(self, cmd, user=None, workdir=None):
        self.calls.append((cmd, user, workdir))
        return type("R", (), {"exit_code": 0, "output": b"built ok\n"})()


def test_run_uses_runtime_image_command_env_and_cook_user(monkeypatch):
    monkeypatch.setenv("THOR_COOK", "generic")
    monkeypatch.setenv("THOR_COOK_IMAGE", "agent:latest")
    monkeypatch.setenv("THOR_COOK_CMD", "agent build {task}")
    monkeypatch.setenv("THOR_COOK_ENV_FOO", "bar")

    prov_kw = {}

    class _FakeProv:
        def provision_room(self, **kw):
            prov_kw.update(kw)
            return {"room_id": "room-x", "_mount_plan": None}

    container = _FakeContainer()

    class _Containers:
        def get(self, rid):
            return container

    monkeypatch.setattr(runner_mod, "_docker", lambda: type("D", (), {"containers": _Containers()})())

    r = CookRunner(provisioner=_FakeProv()).run(SLICE, worktree_host_path="/tmp/wt")

    assert prov_kw["image"] == "agent:latest"                 # the agent's room image
    assert prov_kw["extra_env"] == {"FOO": "bar"}             # the agent's own secret, passed through
    assert prov_kw["worktree_host_path"] == "/tmp/wt"
    assert prov_kw["network_mode"] == "sealed"                # sealed by default (no egress built yet)
    assert container.calls[0][1] == "cook"                    # runs as the UNPRIVILEGED cook
    assert container.calls[0][0][:2] == ["agent", "build"]    # the runtime's command
    assert r["room_id"] == "room-x" and r["exit_code"] == 0 and "built ok" in r["output"]
