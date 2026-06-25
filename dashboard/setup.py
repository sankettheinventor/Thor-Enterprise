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
_CONSENT_FILE = _THOR_DIR / "consent.json"

# Frontier models THOR can drive as the cook. Claude is first-class (login auto-discovered); the others
# run via the generic runtime with the user's own key/login. THOR uses NONE of them until the user consents.
_PROVIDERS = {
    "claude": {"label": "Claude (Anthropic)", "cook": "claude-code", "first_class": True},
    "codex": {"label": "ChatGPT / Codex (OpenAI)", "cook": "generic", "first_class": False},
    "kimi": {"label": "Kimi (Moonshot)", "cook": "generic", "first_class": False},
    "other": {"label": "Other frontier model", "cook": "generic", "first_class": False},
}

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


def consent() -> dict:
    """Has the user explicitly authorized THOR to use a frontier-model login on their behalf, and which?
    THOR must NOT spend the user's subscription without this. Returns {authorized, model}."""
    try:
        import json
        d = json.loads(_CONSENT_FILE.read_text(encoding="utf-8"))
        if d.get("authorized") and d.get("model") in _PROVIDERS:
            return {"authorized": True, "model": d["model"]}
    except Exception:  # noqa: BLE001
        pass
    return {"authorized": False, "model": None}


def grant_consent(model: str) -> dict:
    """Record the user's explicit permission to use <model> as the AI builder (their subscription/key)."""
    if model not in _PROVIDERS:
        return {"ok": False, "reason": f"unknown model {model}"}
    import json
    _THOR_DIR.mkdir(parents=True, exist_ok=True)
    _CONSENT_FILE.write_text(json.dumps({"authorized": True, "model": model}), encoding="utf-8")
    try:
        os.chmod(_THOR_DIR, 0o700)
    except OSError:
        pass
    return {"ok": True, "model": model, "cook": _PROVIDERS[model]["cook"]}


def revoke_consent() -> dict:
    try:
        _CONSENT_FILE.unlink()
    except OSError:
        pass
    return {"ok": True}


def check() -> dict:
    """Full requirement status for the Setup wizard. Pure detection, no side effects."""
    docker = _docker_ok()
    images = {tag: (_image_present(tag) if docker else False) for tag in _IMAGES}
    claude = claude_connected()
    con = consent()
    providers = [{"id": k, "label": v["label"], "first_class": v["first_class"],
                  "detected": (k == "claude" and claude)} for k, v in _PROVIDERS.items()]
    # THOR is only "ready" once the user has CONSENTED to a model AND that model is usable
    ready = docker and all(images.values()) and con["authorized"] and (claude if con["model"] == "claude" else True)
    return {
        "docker": docker,
        "images": [{"tag": t, "present": images[t], "desc": _IMAGES[t][1]} for t in _IMAGES],
        "claude": claude,
        "claude_source": claude_source(),
        "consent": con,
        "providers": providers,
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
