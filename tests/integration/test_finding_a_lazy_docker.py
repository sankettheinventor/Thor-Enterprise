"""
FINDING-A: importing the product must NOT require a live Docker daemon.

wall/provisioner.py ran `docker.from_env()` at MODULE-IMPORT time, so importing ThorManager (which
imports wall.provisioner) failed with DockerException wherever no daemon/socket was reachable. This
test imports the modules in a subprocess with DOCKER_HOST pointed at a non-existent socket and asserts
the import still succeeds — the Docker client must be created lazily, only when a room is provisioned.

Docker-free, un-deferred → runs on every gate.
"""
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]


def test_provisioner_and_manager_import_without_docker_daemon():
    env = {**os.environ, "DOCKER_HOST": "unix:///nonexistent/thor-no-docker.sock"}
    r = subprocess.run(
        [sys.executable, "-c", "import wall.provisioner; import manager.core; print('IMPORT_OK')"],
        capture_output=True, text=True, env=env, cwd=str(REPO),
    )
    assert "IMPORT_OK" in r.stdout, f"import required a Docker daemon (FINDING-A):\n{r.stderr}"
