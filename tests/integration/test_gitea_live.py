"""
P5: a feature merges through a LIVE Gitea server via the GitPort swap (GiteaServerBackend), and ONLY
after THOR's Signature 3. THOR decides + runs its own tests; Gitea executes. Deferred + auto-skips if no
Gitea is reachable (so the gate never fakes green on a host without Gitea).
"""
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.deferred

GITEA = os.environ.get("GITEA_URL", "http://localhost:3000")
OWNER = os.environ.get("GITEA_OWNER", "thor")


def _gitea_up():
    try:
        urllib.request.urlopen(f"{GITEA}/api/v1/version", timeout=3)
        return os.path.exists("/tmp/gitea_token.txt")
    except Exception:
        return False


@pytest.mark.skipif(not _gitea_up(), reason="no live Gitea on :3000 (boot the gitea compose service to run)")
def test_feature_merges_through_live_gitea_only_after_sig3():
    token = open("/tmp/gitea_token.txt").read().strip()

    def api(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{GITEA}/api/v1{path}", data=data, method=method,
                                     headers={"Authorization": f"token {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                t = r.read().decode()
                return r.status, (json.loads(t) if t else {})
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    name = "feat-test"
    api("DELETE", f"/repos/{OWNER}/{name}")
    api("POST", "/user/repos", {"name": name, "auto_init": True, "default_branch": "main"})

    repo = tempfile.mkdtemp(prefix="gitea-t-")

    def g(*a):
        subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True)

    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    open(f"{repo}/README.md", "w").write("base\n")
    g("add", "-A"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    g("checkout", "-q", "-b", "feature/X")
    open(f"{repo}/feat.py", "w").write("def f():\n    return 42\n")
    g("add", "-A"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "feat")

    os.environ.update(GITEA_URL=GITEA, GITEA_TOKEN=token, GITEA_OWNER=OWNER, GITEA_REPO=name)
    from adapters.gitea_adapter import GiteaServerBackend

    gitea = GiteaServerBackend()
    pr = gitea.open_pr(repo, "feature/X", {"feature_id": "X", "gitea_repo": name})
    assert pr["pr_id"]

    assert gitea.merge(repo, pr["pr_id"], None)["merged"] is False, "must refuse without Sig 3"
    ok = gitea.merge(repo, pr["pr_id"], signature_ref="SIG3-abc")
    assert ok["merged"] is True and ok.get("sha"), ok

    _, prstate = api("GET", f"/repos/{OWNER}/{name}/pulls/{pr['pr_id']}")
    assert prstate.get("merged") is True, "the merge must actually land in Gitea"
