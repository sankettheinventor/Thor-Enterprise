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
from sdlc.stages import _git, _sanitize_git_dir


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


def check_sanitized():
    """The full-flow defence: the cook plants a clean FILTER + a diff TEXTCONV + a hook (everything it
    controls in /work/.git); THOR sanitizes the .git then runs host-side git. Nothing must execute."""
    repo = tempfile.mkdtemp(prefix="san-")
    subprocess.run(["git", "init", "-q", repo])
    marker = os.path.join(repo, "SANITIZE_PWNED")
    subprocess.run(["git", "-C", repo, "config", "filter.evil.clean", f"sh -c 'touch {marker}'"])
    subprocess.run(["git", "-C", repo, "config", "diff.evil.textconv", f"sh -c 'touch {marker}'"])
    open(os.path.join(repo, ".gitattributes"), "w").write("* filter=evil diff=evil\n")
    hd = os.path.join(repo, ".git", "hooks")
    os.makedirs(hd, exist_ok=True)
    with open(os.path.join(hd, "pre-commit"), "w") as f:
        f.write(f"#!/bin/sh\ntouch {marker}\n")
    os.chmod(os.path.join(hd, "pre-commit"), 0o755)
    open(os.path.join(repo, "src.py"), "w").write("x = 1\n")

    _sanitize_git_dir(repo)                                    # THOR cleans the cook's .git
    _git(repo, "add", "-A")                                    # would run the clean filter
    _git(repo, "-c", "user.email=c", "-c", "user.name=c", "commit", "-q", "-m", "build")
    open(os.path.join(repo, "src.py"), "w").write("x = 2\n")
    _git(repo, "diff")                                         # would run the diff textconv
    fired = os.path.exists(marker)
    landed = subprocess.run(["git", "-C", repo, "log", "--oneline"], capture_output=True, text=True).stdout.strip()
    print(f"[{'sanitize(filter+diff+hook)':22}] cook code executed on host: {fired} | commit landed: {bool(landed)}")
    assert not fired, "a cook-planted filter/diff/hook EXECUTED after sanitize (RCE)"
    assert landed, "the legitimate commit must still land after sanitize"


check(_git, "sdlc.stages._git")
check(gitea_adapter._git, "gitea_adapter._git")
check_sanitized()
print("GIT_HOOK_SAFETY_OK — host-side git executes no cook-controlled code (hooks/filters/diff); commits still work.")
