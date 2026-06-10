"""
The Cook seam: EVERY action a cook proposes is governed by the Leash (THOR's invariant). The production
cook is Claude Code in the room (governed by leash.claude_code_hook — see test_claude_code_hook.py); here
the in-process ScriptedCook proves the same routing invariant with no LLM/no network. Docker-free.
"""
import os
import shutil
import tempfile

from adapters import agt_adapter
from cook.agent import ScriptedCook
from leash.policy import FrozenPolicy
from leash.proxy import InRoomProxy

ROOM = "room-cook"
POLICY = FrozenPolicy(room_id=ROOM, scope_files=("src/",), forbidden_patterns=("infra/", "**/secrets*"),
                      language_lock="python", frozen_at=0.0)


class _NoopRecorder:
    def record_decision(self, verdict, action):
        return {}


def _proxy():
    base = tempfile.mkdtemp(prefix="cook-")
    wt = os.path.join(base, "wt")
    os.makedirs(os.path.join(wt, "src"))
    agt_adapter.load_policy(POLICY)
    return InRoomProxy(agt_adapter, _NoopRecorder(), wt), wt, base


def test_scripted_cook_actions_are_governed_by_the_leash():
    proxy, wt, base = _proxy()
    try:
        cook = ScriptedCook([
            {"name": "write_file", "args": {"path": "src/login.py", "content": "def check(p): return len(p)>=8\n"}},
            {"name": "write_file", "args": {"path": "infra/secrets.tf", "content": "leak"}},   # out of scope
            {"name": "write_file", "args": {"path": "src/../../escape.txt", "content": "pwn"}},  # traversal
        ])
        r = cook.build({"room_id": ROOM, "feature_id": "F"}, proxy)
        assert r["n_allowed"] == 1, r                       # only the in-scope write
        assert r["n_denied"] == 2, r                        # out-of-scope + traversal both blocked
        assert os.path.exists(os.path.join(wt, "src/login.py"))
        assert not os.path.exists(os.path.join(wt, "infra/secrets.tf"))
        assert not os.path.exists(os.path.realpath(os.path.join(base, "escape.txt")))
    finally:
        shutil.rmtree(base, ignore_errors=True)
