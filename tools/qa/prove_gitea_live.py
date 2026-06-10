"""
P5 proof — a feature merges through a LIVE Gitea server, and ONLY after THOR's Signature 3.

Proves the GitPort swap is real (GiteaServerBackend talks to a running Gitea), the merge is gated on a
Sig-3 ref (refused without it), and the merge actually lands in Gitea. The verdict (M1/M4) is separate and
still runs THOR's own tests — Gitea executes, it never judges.

Setup: a Gitea container at :3000 with token in /tmp/gitea_token.txt (see the P5 boot commands).
Run:   PYTHONPATH=. .venv/bin/python tools/qa/prove_gitea_live.py
"""
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

GITEA = os.environ.get("GITEA_URL", "http://localhost:3000")
TOKEN = open("/tmp/gitea_token.txt").read().strip()
OWNER = "thor"
NAME = "feat-demo"


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{GITEA}/api/v1{path}", data=data, method=method,
                                 headers={"Authorization": f"token {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            t = r.read().decode()
            return r.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


api("DELETE", f"/repos/{OWNER}/{NAME}")
print("create repo:", api("POST", "/user/repos", {"name": NAME, "auto_init": True, "default_branch": "main"})[0])

repo = tempfile.mkdtemp(prefix="gitea-")


def g(*a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout


subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
open(f"{repo}/README.md", "w").write("base\n")
g("add", "-A"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
g("checkout", "-q", "-b", "feature/X")
open(f"{repo}/feat.py", "w").write("def f():\n    return 42\n")
g("add", "-A"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "feat X")

os.environ.update(GITEA_URL=GITEA, GITEA_TOKEN=TOKEN, GITEA_OWNER=OWNER, GITEA_REPO=NAME)
from adapters.gitea_adapter import GiteaServerBackend

gitea = GiteaServerBackend()
pr = gitea.open_pr(repo, "feature/X", {"feature_id": "X", "gitea_repo": NAME})
print("PR opened in Gitea:", pr["pr_id"], "|", pr.get("url"))

no_sig = gitea.merge(repo, pr["pr_id"], None)                       # ATTACK: merge without Sig 3
print("merge WITHOUT Sig3:", no_sig)
assert no_sig["merged"] is False, "merge must be refused without Signature 3"

ok = gitea.merge(repo, pr["pr_id"], signature_ref="SIG3-deadbeef")  # merge WITH Sig 3
print("merge WITH Sig3:", {k: ok[k] for k in ("merged", "sha") if k in ok})
assert ok["merged"] is True and ok.get("sha"), "merge must succeed with Signature 3"

_, prstate = api("GET", f"/repos/{OWNER}/{NAME}/pulls/{pr['pr_id']}")
print("Gitea PR state:", prstate.get("state"), "| merged:", prstate.get("merged"))
assert prstate.get("merged") is True, "the merge must actually land in Gitea"
print("P5_GITEA_LIVE_OK")
