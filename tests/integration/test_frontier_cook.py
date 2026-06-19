"""
Frontier cook (Claude Code) — wiring + preflight proven always (docker-free); the LIVE run executes only
when an operator supplies `CLAUDE_CODE_OAUTH_TOKEN` (+ the claude room image + Docker). This is the one
production item gated on an operator credential, not on code — so here it SKIPS with an honest reason rather
than a fake pass. Swapping in the real cook is `THOR_COOK=claude-code` + the token, no code change.
"""
import os

import pytest

from cook.runner import CookRunner
from cook.runtime import ClaudeCodeRuntime

SLICE = {"feature_id": "FRT1", "scope_files": ["src/"]}


def test_wiring_resolves_command_egress_env():
    plan = CookRunner(runtime=ClaudeCodeRuntime()).plan(SLICE)
    assert plan["runtime"] == "claude-code"
    assert plan["network_mode"] == "one_door"                     # it needs its model → one governed door
    assert "claude" in plan["command"][0]
    assert "api.anthropic.com" in plan["egress_allowlist"]        # the model host is allowlisted


def test_preflight_demands_the_oauth_token(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    problems = ClaudeCodeRuntime().preflight()
    assert problems and "CLAUDE_CODE_OAUTH_TOKEN" in problems[0]
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "test-token")
    assert ClaudeCodeRuntime().preflight() == []                  # configured → ready


def test_runner_refuses_to_launch_without_the_token(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CLAUDE_CODE_OAUTH_TOKEN"):
        CookRunner(runtime=ClaudeCodeRuntime()).run(SLICE, worktree_host_path="/tmp/nope")


@pytest.mark.deferred
def test_frontier_live_run_when_token_present(tmp_path):
    """Real frontier cook end-to-end — runs ONLY when the operator has supplied the credential + image."""
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        pytest.skip("no CLAUDE_CODE_OAUTH_TOKEN — frontier live run is operator-credential-gated (not faked)")
    try:
        import docker
        cli = docker.from_env()
        image = os.environ.get("THOR_COOK_IMAGE", "thor-room-claude:latest")
        if not cli.images.list(name=image):
            pytest.skip(f"claude room image {image} not built — `make` the claude image to run this")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"docker unavailable for the live frontier run: {e}")

    import subprocess
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q", repo], check=True)
    os.chmod(repo, 0o777)
    os.environ["THOR_COOK"] = "claude-code"
    r = CookRunner(runtime=ClaudeCodeRuntime()).run(
        {"feature_id": "FRTLIVE", "scope_files": ["greeting.py"],
         "task": "create greeting.py with a function hello() that returns 'hello'"},
        worktree_host_path=repo)
    assert r["network_mode"] == "one_door"          # the frontier cook ran behind the governed one door
    assert r["room_id"]                              # a room was provisioned and the cook launched
