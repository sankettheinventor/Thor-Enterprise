"""
C1 proof — the CookRunner AUTO-WIRES one-door egress for a cook that declares an allowlist. A generic cook
with THOR_COOK_EGRESS=example.com gets a real one_door room (gateway started by the runner): it reaches the
allowlisted host and is BLOCKED for every other host, and no model-host secret is in the room env.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_cook_onedoor.py
"""
import os
import subprocess
import tempfile

import docker

from wall import config

# A generic cook that needs egress to exactly one host; its "build" just probes egress.
wt = tempfile.mkdtemp(prefix="cook-od-")
os.chmod(wt, 0o777)
subprocess.run(["git", "init", "-q", wt])
with open(os.path.join(wt, "probe.py"), "w") as f:
    f.write("import urllib.request as u\n"
            "for h in ('https://example.com', 'https://www.google.com'):\n"
            "    try: print(h, 'OK', u.urlopen(h, timeout=12).status)\n"
            "    except Exception as e: print(h, 'BLOCKED', type(e).__name__)\n")

os.environ["THOR_COOK"] = "generic"
os.environ["THOR_COOK_IMAGE"] = config.ROOM_IMAGE          # the built room image (has python3)
os.environ["THOR_COOK_CMD"] = "python3 probe.py"
os.environ["THOR_COOK_EGRESS"] = "example.com"             # the ONLY host this cook may reach

from cook.runner import CookRunner  # noqa: E402 — env must be set before importing the runtime
from leash import gateway  # noqa: E402
from wall import provisioner  # noqa: E402

cli = docker.from_env()
for n in (gateway.GATEWAY_NAME, gateway.UPSTREAM_NAME):
    for c in cli.containers.list(all=True, filters={"name": n}):
        c.remove(force=True)

r = CookRunner().run({"feature_id": "OD", "scope_files": ["src/"]}, worktree_host_path=wt)
print("network_mode:", r["network_mode"])
print("cook egress probe output:\n" + r["output"].strip())

room = cli.containers.get(r["room_id"])
room_env = room.exec_run(["env"], user="cook").output.decode()
leaked = gateway.UPSTREAM_CRED in room_env
print("model-host secret in room env:", leaked)

provisioner.destroy_room(r["room_id"], r.get("_mount_plan"))
gateway.teardown(cli)

assert r["network_mode"] == "one_door", "the runner must auto-select one_door for a cook with an allowlist"
assert "example.com OK" in r["output"], "the allowlisted host must be reachable through the gateway"
assert "www.google.com BLOCKED" in r["output"], "every non-allowlisted host must be blocked"
assert not leaked, "no model-host secret may appear in the room env"
print("C1_COOK_ONEDOOR_OK")
