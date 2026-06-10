"""
The Leash ↔ Claude Code PreToolUse hook: every file the in-room Claude Code cook tries to write is
governed by the SAME leash.policy engine as FLOW B. In-scope → allow; out-of-scope / traversal → deny;
missing policy → fail closed. Docker-free, un-deferred. Also covers the CLI exit codes (0 allow / 2 block).
"""
import json
import os
import subprocess
import sys
import tempfile

from leash.claude_code_hook import evaluate_event


def _slice(monkeypatch, scope=("src/",)):
    d = tempfile.mkdtemp(prefix="cchook-")
    sp = os.path.join(d, "feature.json")
    with open(sp, "w") as f:
        json.dump({"feature_id": "F", "scope_files": list(scope)}, f)
    monkeypatch.setenv("THOR_TASK_SLICE", sp)
    monkeypatch.setenv("THOR_WORKTREE", d)
    return d


def test_in_scope_write_allowed(monkeypatch):
    d = _slice(monkeypatch)
    ev = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(d, "src/login.py"), "content": "x"}}
    allowed, reason = evaluate_event(ev)
    assert allowed, reason


def test_out_of_scope_write_denied(monkeypatch):
    d = _slice(monkeypatch)
    ev = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(d, "infra/secrets.tf"), "content": "x"}}
    allowed, reason = evaluate_event(ev)
    assert not allowed and "infra" in reason


def test_path_traversal_write_denied(monkeypatch):
    d = _slice(monkeypatch)
    ev = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(d, "src/../../escape.txt"), "content": "x"}}
    allowed, reason = evaluate_event(ev)
    assert not allowed, reason


def test_multiedit_governs_every_path(monkeypatch):
    d = _slice(monkeypatch)
    ev = {"tool_name": "MultiEdit", "tool_input": {"edits": [
        {"file_path": os.path.join(d, "src/a.py")},
        {"file_path": os.path.join(d, "infra/b.tf")}]}}      # one in-scope, one OUT
    allowed, reason = evaluate_event(ev)
    assert not allowed and "infra" in reason


def test_missing_slice_fails_closed(monkeypatch):
    monkeypatch.setenv("THOR_TASK_SLICE", "/nonexistent/feature.json")
    allowed, reason = evaluate_event({"tool_name": "Write", "tool_input": {"file_path": "/work/src/a.py"}})
    assert not allowed and "fail closed" in reason


def test_cli_exit_codes(monkeypatch):
    d = _slice(monkeypatch)
    env = {**os.environ}
    allow_ev = json.dumps({"tool_name": "Write", "tool_input": {"file_path": os.path.join(d, "src/ok.py")}})
    deny_ev = json.dumps({"tool_name": "Write", "tool_input": {"file_path": os.path.join(d, "infra/x.tf")}})
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = subprocess.run([sys.executable, "-m", "leash.claude_code_hook"], input=allow_ev,
                       capture_output=True, text=True, env=env, cwd=repo)
    b = subprocess.run([sys.executable, "-m", "leash.claude_code_hook"], input=deny_ev,
                       capture_output=True, text=True, env=env, cwd=repo)
    assert a.returncode == 0, a.stderr
    assert b.returncode == 2 and "THOR Leash DENY" in b.stderr, (b.returncode, b.stderr)
