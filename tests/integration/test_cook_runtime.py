"""
The cook is PLUGGABLE — THOR governs the walls, not the agent. Proves: the user selects the agent via
THOR_COOK; Claude Code is just one runtime; ANY agent runs with ZERO THOR code via the generic runtime.
Docker-free, un-deferred.
"""
import pytest

from cook.runtime import (ClaudeCodeRuntime, GenericCommandRuntime, known_runtimes,
                          register_runtime, select_runtime)

SLICE = {"feature_id": "F1", "acceptance_criteria": ["works"], "scope_files": ["src/"]}


def test_default_runtime_is_claude_code(monkeypatch):
    monkeypatch.delenv("THOR_COOK", raising=False)
    assert select_runtime().name == "claude-code"


def test_user_selects_runtime_via_env(monkeypatch):
    monkeypatch.setenv("THOR_COOK", "generic")
    assert isinstance(select_runtime(), GenericCommandRuntime)


def test_unknown_runtime_is_rejected():
    with pytest.raises(ValueError):
        select_runtime("no-such-agent")


def test_claude_code_runtime_describes_a_non_interactive_run(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-123")
    rt = ClaudeCodeRuntime()
    cmd = rt.command(SLICE)
    assert cmd[0] == "claude" and "-p" in cmd and "--output-format" in cmd
    assert rt.env() == {"CLAUDE_CODE_OAUTH_TOKEN": "tok-123"}     # NO API key — subscription token
    assert "thor-room-claude" in rt.image()


def test_bring_any_agent_with_zero_thor_code(monkeypatch):
    # a third agent THOR has never heard of — configured purely by env, no code change
    monkeypatch.setenv("THOR_COOK", "generic")
    monkeypatch.setenv("THOR_COOK_IMAGE", "my-org/aider-room:latest")
    monkeypatch.setenv("THOR_COOK_CMD", "aider --yes --message {task}")
    monkeypatch.setenv("THOR_COOK_ENV_OPENAI_API_KEY", "sk-xyz")
    rt = select_runtime()
    d = rt.describe(SLICE)
    assert d["image"] == "my-org/aider-room:latest"
    assert d["command"][:3] == ["aider", "--yes", "--message"]   # {task} substituted as one arg
    assert d["command"][-1].startswith("Implement feature F1")
    assert rt.env() == {"OPENAI_API_KEY": "sk-xyz"}              # the agent's OWN secret, passed through


def test_generic_runtime_requires_image_and_cmd(monkeypatch):
    monkeypatch.setenv("THOR_COOK", "generic")
    monkeypatch.delenv("THOR_COOK_IMAGE", raising=False)
    with pytest.raises(ValueError):
        select_runtime().image(SLICE) if False else select_runtime().image()


def test_a_new_runtime_can_be_registered():
    class _MyAgent(GenericCommandRuntime):
        name = "my-agent"

        def image(self):
            return "my-agent:latest"

        def command(self, feature_slice):
            return ["my-agent", "build"]

    register_runtime("my-agent", _MyAgent)
    assert "my-agent" in known_runtimes()
    assert select_runtime("my-agent").image() == "my-agent:latest"
