"""
RED-TEAM proof — the cook writes /work (incl. its .git), and THOR runs host-side git (add/commit/checkout/
push) on that repo. A planted .git/hooks/* (or a core.fsmonitor config) would execute on the control plane
= RCE. The hardened _git helpers run with hooks/fsmonitor/sshCommand/ext-protocol disabled. This plants
every hook + a config injection and proves none fire, while legitimate commits still land.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_git_hook_safety.py
"""
import os
import subprocess
import tempfile

from adapters import gitea_adapter
from sdlc.stages import _git


def _attack_repo():
    repo = tempfile.mkdtemp(prefix="hook-")
    subprocess.run(["git", "init", "-q", repo])
    open(os.path.join(repo, "f"), "w").write("x")
    marker = os.path.join(repo, "PWNED_ON_HOST")
    hooks_dir = os.path.join(repo, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    for hook in ("pre-commit", "post-commit", "pre-push", "post-checkout", "prepare-commit-msg", "post-merge"):
        p = os.path.join(hooks_dir, hook)
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\ntouch {marker}\n")
        os.chmod(p, 0o755)
    subprocess.run(["git", "-C", repo, "config", "core.fsmonitor", f"sh -c 'touch {marker}'"])  # config-based RCE
    return repo, marker


def check(gitfn, label):
    repo, marker = _attack_repo()
    gitfn(repo, "add", "-A")
    gitfn(repo, "-c", "user.email=c", "-c", "user.name=c", "commit", "-q", "-m", "build")
    gitfn(repo, "checkout", "-q", "-B", "feature/x")
    fired = os.path.exists(marker)
    landed = subprocess.run(["git", "-C", repo, "log", "--oneline"], capture_output=True, text=True).stdout.strip()
    print(f"[{label:22}] cook hook executed on host: {fired} | commit landed: {bool(landed)}")
    assert not fired, f"{label}: a cook-planted git hook EXECUTED on the host (RCE)"
    assert landed, f"{label}: the legitimate commit must still land"


check(_git, "sdlc.stages._git")
check(gitea_adapter._git, "gitea_adapter._git")
print("GIT_HOOK_SAFETY_OK — host-side git executes no cook-controlled code; commits still work.")
