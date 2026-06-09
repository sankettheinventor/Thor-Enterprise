"""
Moat-LOGIC gate test (BUG-2 fix): the Leash policy engine, exercised DIRECTLY and DOCKER-FREE so it
runs on EVERY commit gate (`make test` / `make qa`) — not just the deferred live ACs in `make prove`.

This is the "harder, never easier" coverage the empty gate was missing: a reworded bypass to
policy.evaluate now goes red here, on a commit, with no Postgres/Docker/git needed. The live wired
ACs (tests/leash/test_acceptance.py, deferred) still prove the same logic against reality.
"""
import dataclasses

import pytest

from leash.policy import FrozenPolicy, evaluate

POLICY = FrozenPolicy(room_id="r", scope_files=("src/", "tests/"),
                      forbidden_patterns=("infra/", "**/secrets*"),
                      language_lock="python", frozen_at=0.0)


def _act(target, type_="tool_call", name="write_file"):
    return {"type": type_, "name": name, "target": target, "room_id": "r", "args": {}}


def test_in_scope_write_allowed():
    assert evaluate(POLICY, _act("src/login.py")).decision == "allow"


def test_out_of_scope_write_denied():
    assert evaluate(POLICY, _act("docs/readme.md")).decision == "deny"


def test_forbidden_pattern_denied_with_precedence():
    # forbidden wins even though infra/ is not in scope anyway — deny-precedence (PRD §10)
    assert evaluate(POLICY, _act("infra/main.tf")).decision == "deny"
    assert evaluate(POLICY, _act("src/secrets.env")).decision == "deny"   # **/secrets* glob


def test_dependency_manifest_escalates():
    assert evaluate(POLICY, _act("package.json")).decision == "escalate"


def test_unknown_action_type_denied_fail_closed():
    assert evaluate(POLICY, _act("src/x.py", type_="weird_type")).decision == "deny"


def test_path_traversal_denied():
    # BUG-1 guard, also asserted here at the logic gate so it can never silently regress.
    assert evaluate(POLICY, _act("src/../../escape.txt")).decision == "deny"
    assert evaluate(POLICY, _act("/etc/passwd")).decision == "deny"


def test_frozen_policy_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        POLICY.scope_files = ("anything/",)   # the room cannot relax its own rules (AC-11 / P1)
