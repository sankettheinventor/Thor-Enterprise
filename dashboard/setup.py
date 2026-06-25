"""
Cockpit-driven SELF-SETUP (pure code, NO AI). Powers the on-screen Setup wizard: check what's present,
let the user click "Build" to download/build the AI room image (progress streamed), and "Connect Claude"
to sign in ONCE (stored in a THOR location every room reuses). The control plane must already be up to
serve this (Docker + Python + Postgres) — the installer/`thor doctor` gets you there; the cockpit handles
the rest with buttons instead of the terminal.
"""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_THOR_DIR = Path(os.path.expanduser("~/.thor"))
_TOKEN_FILE = _THOR_DIR / "claude_token"

# image -> (Dockerfile, build context) for the two images THOR needs to run cooks + verdicts
_IMAGES = {
    "thor-room-claude:latest": ("wall/image/Dockerfile.claude", "the AI cook + verdict room"),
    "thor-room:dev": ("wall/image/Dockerfile", "the base sealed room"),
}

# live build state for the cockpit to poll (one build at a time — setup is sequential)
_build = {"running": False, "image": None, "done": False, "ok": None, "log": []}
_build_lock = threading.Lock()


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO))


def _docker_ok() -> bool:
    try:
        return _run(["docker", "info"]).returncode == 0
    except FileNotFoundError:
        return False


def _image_present(tag: str) -> bool:
    try:
        return bool(_run(["docker", "images", "-q", tag]).stdout.strip())
    except FileNotFoundError:
        return False


def claude_connected() -> bool:
    try:
        from cook.runtime import discover_claude_oauth
        return bool(discover_claude_oauth())
    except Exception:  # noqa: BLE001
        return False


def claude_source() -> str:
    """WHERE the Claude login came from, so the cockpit can tell the user whether they need to do anything:
      env           - an explicit CLAUDE_CODE_OAUTH_TOKEN
      connected     - the cockpit 'Connect Claude' token (~/.thor/claude_token)
      existing      - REUSING the user's existing Claude Code / desktop login (nothing to do)
      none          - not logged in anywhere (the paste fallback is needed)"""
    import glob as _glob
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return "env"
    if _TOKEN_FILE.exists() and _TOKEN_FILE.read_text(encoding="utf-8").strip():
        return "connected"
    for p in [os.path.expanduser("~/.thor/.credentials.json"),
              os.path.expanduser("~/.claude/.credentials.json"),
              *_glob.glob("/mnt/c/Users/*/.claude/.credentials.json")]:
        if os.path.exists(p):
            return "existing"
    return "none"


def check() -> dict:
    """Full requirement status for the Setup wizard. Pure detection, no side effects."""
    docker = _docker_ok()
    images = {tag: (_image_present(tag) if docker else False) for tag in _IMAGES}
    claude = claude_connected()
    ready = docker and all(images.values()) and claude
    return {
        "docker": docker,
        "images": [{"tag": t, "present": images[t], "desc": _IMAGES[t][1]} for t in _IMAGES],
        "claude": claude,
        "claude_source": claude_source(),
        "ready": ready,
        "build": dict(_build),   # current/last build progress
    }


def _do_build(tag: str, dockerfile: str) -> None:
    with _build_lock:
        _build.update(running=True, image=tag, done=False, ok=None, log=[f"building {tag} …"])
    try:
        proc = subprocess.Popen(["docker", "build", "-f", dockerfile, "-t", tag, "."],
                                cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:        # stream progress for the cockpit
            line = line.rstrip()
            if line:
                with _build_lock:
                    _build["log"].append(line)
                    _build["log"] = _build["log"][-200:]   # bounded
        rc = proc.wait()
        with _build_lock:
            _build.update(running=False, done=True, ok=(rc == 0))
            _build["log"].append("DONE" if rc == 0 else f"FAILED (exit {rc})")
    except Exception as e:  # noqa: BLE001
        with _build_lock:
            _build.update(running=False, done=True, ok=False)
            _build["log"].append(f"error: {e}")


def build_image(tag: str) -> dict:
    """Kick off (or refuse to double-start) a background build of one required image."""
    if tag not in _IMAGES:
        return {"ok": False, "reason": f"unknown image {tag}"}
    with _build_lock:
        if _build["running"]:
            return {"ok": False, "reason": f"a build is already running ({_build['image']})"}
    threading.Thread(target=_do_build, args=(tag, _IMAGES[tag][0]), name=f"build-{tag}", daemon=True).start()
    return {"ok": True, "image": tag, "building": True}


def build_status() -> dict:
    with _build_lock:
        return dict(_build)


def connect_claude(token: str) -> dict:
    """Store a Claude OAuth token (from `claude setup-token`) ONCE — every room reuses it via
    discover_claude_oauth(). Owner-only perms; the token is a secret."""
    token = (token or "").strip()
    if not token or len(token) < 20:
        return {"ok": False, "reason": "that doesn't look like a valid token"}
    _THOR_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        os.chmod(_THOR_DIR, 0o700)
        os.chmod(_TOKEN_FILE, 0o600)
    except OSError:
        pass
    return {"ok": claude_connected()}
