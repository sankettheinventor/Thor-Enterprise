"""
P0.5 proof — M11 (read-only room root FS) + M10 (routable rooms.address in the registry).

M11: the room root FS is read-only; only /work (the worktree) + /tmp + /home/cook are writable. A cook
     write OUTSIDE that set fails; a normal build (write /work + git commit) still succeeds.
M10: the registry (state_summary) exposes a routable address per room (room_id:agent_port).

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_room_hardening.py
"""
import os
import subprocess
import tempfile

import docker

from manager import db, pg
from manager.core import ThorManager

pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
with conn.cursor() as cur:
    cur.execute("TRUNCATE eventlog, rooms, cards, features")
conn.commit()
mgr = ThorManager(conn)

wt = tempfile.mkdtemp(prefix="m11-")
subprocess.run(["git", "init", "-q", wt])
subprocess.run(["git", "-C", wt, "checkout", "-q", "-b", "feature/M11"])
os.system(f"chmod -R 0777 {wt}")   # the unprivileged cook (uid 1000) must be able to write the worktree

room = mgr.provision_room("M11", branch="feature/M11", worktree_host_path=wt, network_mode="one_door")
c = docker.from_env().containers.get(room["room_id"])


def sh(cmd):
    return c.exec_run(["bash", "-lc", cmd], user="cook").output.decode().strip()


try:
    print("=== M11: root FS is READ-ONLY (writes outside the writable set must FAIL) ===")
    print("write / :    ", sh("echo x > /thor_root 2>&1 || echo BLOCKED"))
    print("write /etc : ", sh("echo x > /etc/thor 2>&1 || echo BLOCKED"))
    print("write /usr : ", sh("echo x > /usr/thor 2>&1 || echo BLOCKED"))
    print("=== the minimal WRITABLE set works ===")
    print("write /work :", sh("echo ok > /work/probe.txt && echo WROTE"))
    print("write /tmp : ", sh("echo ok > /tmp/probe.txt && echo WROTE"))
    print("write ~ :    ", sh("echo ok > ~/probe.txt && echo WROTE"))
    print("=== a normal build still succeeds on the read-only-root room ===")
    print("build+commit:", sh("cd /work && echo 'def f(): return 1' > feat.py && "
                              "git -c user.email=c@t -c user.name=c add -A && "
                              "git -c user.email=c@t -c user.name=c commit -q -m build && echo COMMIT_OK")[-20:])
    print("=== M10: the registry exposes a routable address ===")
    addr = mgr.state_summary()["rooms"][room["room_id"]]["address"]
    print("room address:", addr)

    assert "BLOCKED" in sh("echo x > /thor_root 2>&1 || echo BLOCKED"), "root FS must be read-only"
    assert sh("echo ok > /work/x && echo W")[-1] == "W", "/work must be writable"
    assert addr == f"{room['room_id']}:{room['agent_port']}", "registry must hold a routable address"
finally:
    mgr.destroy_room(room["room_id"], room.get("_mount_plan"))
print("P0_5_ROOM_HARDENING_OK")
