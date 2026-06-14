"""
Sub-modules 7.3–7.6 — the four stage types, all on the universal anatomy.

  Genesis (7.3)  — planning brain; drafts the feature catalog (human interview is stubbed by the
                   project_intent input; real Dashboard relay is Module 15). Human signs (Sig 1).
  Checker (7.4)  — read-only codebase analysis → findings to the DB; changes NOTHING.
  Build (7.5)    — provisions a real Wall room; the cook (stand-in) commits one feature on a branch;
                   emits claim_done.
  QA (7.6)       — a FRESH, independent room (did not write the code); runs the planned criteria,
                   then writes NEW edge-case tests beyond the plan and tries to break it; bugs → DB.

The cook and the QA agent's intelligence are deterministic stand-ins (no LLM, per our bootstrap),
but the STRUCTURE — independence, floor+specialty skills, edge-test generation — is real (Bible §10.4).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess

from adapters import agt_adapter
from leash.decision import DecisionRecorder
from leash.policy import FrozenPolicy
from leash.proxy import InRoomProxy
from scheduler import cto_stub

from .anatomy import Stage


# The cook writes /work (incl. its .git) — host-side git on that repo MUST NOT execute cook-controlled
# code: disable hooks, fsmonitor, and any sshCommand override (a planted .git/hooks/pre-commit would
# otherwise run on the control plane = RCE). These -c flags override the repo's local .git/config.
_SAFE_GIT = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=", "-c", "core.sshCommand=",
             "-c", "protocol.ext.allow=never")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *_SAFE_GIT, *args], capture_output=True, text=True)


# git config sections whose values are SHELL COMMANDS git runs (clean/smudge filters, diff textconv, merge
# drivers, aliases, …). The cook controls .git/config + .gitattributes in its rw worktree, so these are RCE
# vectors that `-c` flags can't neutralise (the cook names the driver). We strip them after the cook is done.
_DANGEROUS_SECTIONS = ("filter.", "diff.", "merge.", "difftool.", "mergetool.", "alias.", "sendemail.",
                       "credential.", "url.", "instead.")
_DANGEROUS_CORE = {"core.hookspath", "core.fsmonitor", "core.sshcommand", "core.attributesfile",
                   "core.editor", "core.pager", "core.fsmonitorhookversion"}


def _sanitize_git_dir(repo: str) -> None:
    """Neutralise EVERY git-config code-execution vector the cook could have planted in /work/.git before
    THOR runs host-side git on it: delete planted hooks + untracked attributes, and remove driver sections
    (filter/diff/merge/alias/…) and dangerous core.* keys from the repo's local config. Uses git's own
    parser (a bare `git config` read runs no cook code). Defense-in-depth on top of the `_SAFE_GIT` flags."""
    gd = os.path.join(repo, ".git")
    if not os.path.isdir(gd):
        return
    hooks = os.path.join(gd, "hooks")
    shutil.rmtree(hooks, ignore_errors=True)
    os.makedirs(hooks, exist_ok=True)
    try:
        open(os.path.join(gd, "info", "attributes"), "w").close()   # an UNtracked attributes file
    except OSError:
        pass

    def _cfg(*a):
        return subprocess.run(["git", "-C", repo, *_SAFE_GIT, "config", "--local", *a],
                              capture_output=True, text=True)

    names = _cfg("--list", "--name-only").stdout.splitlines()
    sections, core_keys = set(), set()
    for raw in names:
        key = raw.strip()
        kl = key.lower()
        if kl in _DANGEROUS_CORE:
            core_keys.add(key)
        elif any(kl.startswith(p) for p in _DANGEROUS_SECTIONS):
            parts = key.split(".")
            if len(parts) >= 2:
                sections.add(".".join(parts[:-1]))   # filter.evil.clean → filter.evil
    for key in core_keys:
        _cfg("--unset-all", key)
    for sec in sections:
        _cfg("--remove-section", sec)


def _dir_hash(repo: str) -> str:
    """Hash all tracked file contents — to prove the Checker changed nothing (AC-7)."""
    h = hashlib.sha256()
    for root, _dirs, files in sorted(os.walk(repo)):
        if "/.git" in root:
            continue
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(p.encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()


# ---------------------------------------------------------------------------
class GenesisStage(Stage):
    name = "genesis"

    def mandate(self) -> str:
        return "interview the human and draft the vision + feature catalog (acceptance criteria + tags)"

    def run(self, project_intent: dict, **_) -> dict:
        # Stub for the Dashboard interview: project_intent already carries the desired features.
        catalog = []
        for f in project_intent.get("features", []):
            catalog.append({
                "feature_id": f["feature_id"], "goals": f.get("goals", []),
                "acceptance_criteria": f.get("acceptance_criteria", []),
                "capability_tags": f.get("capability_tags", []), "task_type": f.get("task_type", "build"),
            })
        return {"catalog": catalog, "vision": project_intent.get("vision", "")}

    def edge_check(self, output: dict) -> tuple[bool, str]:
        for f in output["catalog"]:
            if not f["acceptance_criteria"]:
                return False, f"feature {f['feature_id']} has no acceptance criteria"
        return True, "catalog has testable acceptance criteria for every feature"


# ---------------------------------------------------------------------------
class CheckerStage(Stage):
    name = "checker"

    def mandate(self) -> str:
        return "read-only full-codebase analysis → findings to the DB; change nothing (the aha moment)"

    def run(self, repo: str, manager=None, **_) -> dict:
        before = _dir_hash(repo)
        # Provision a real read-only checker room (codebase mounted read-only — FR-5 trust guarantee).
        room = manager.provision_room(f"CHK-{os.path.basename(repo)}", task_type="checker",
                                      branch=f"checker/{os.path.basename(repo)}",
                                      codebase_host_path=repo) if manager else None
        findings = []
        for root, _d, files in os.walk(repo):
            if "/.git" in root:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                src = open(os.path.join(root, f)).read()
                if "TODO" in src or "FIXME" in src:
                    findings.append({"file": f, "issue": "unresolved TODO/FIXME (patch-hack)"})
                if "eval(" in src or "exec(" in src:
                    findings.append({"file": f, "issue": "dynamic eval/exec (attack surface)"})
        if manager:
            for fd in findings:
                manager.append_bug(f"CHK-{os.path.basename(repo)}", "info",
                                   f"{fd['file']}: {fd['issue']}", source="checker")
            manager.destroy_room(room["room_id"], room.get("_mount_plan"))
        after = _dir_hash(repo)
        return {"findings": findings, "room_id": room["room_id"] if room else None,
                "repo_unchanged": before == after}

    def edge_check(self, output: dict) -> tuple[bool, str]:
        return output["repo_unchanged"], ("read-only: codebase unchanged" if output["repo_unchanged"]
                                          else "VIOLATION: checker modified the codebase")


# ---------------------------------------------------------------------------
class BuildStage(Stage):
    name = "build"

    def mandate(self) -> str:
        return "build exactly one feature within scope, under the live Leash; produce a branch + claim_done"

    def run(self, feature: dict, repo: str, manager=None, cook=None, **_) -> dict:
        fid = feature["feature_id"]
        branch = f"feature/{fid}"
        # CTO plans at task-start (shared, rare): scope is PLAN-OWNED, deny-all if undeclared.
        plan = cto_stub.plan_task(fid, "build", feature=feature)

        # C2: when a REAL runtime is selected (THOR_COOK explicitly set), the agent builds INSIDE the room
        # via CookRunner — governed by the in-room PreToolUse hook + the walls + one-door egress (C1), and
        # judged by the verdict-from-reality. The gated suite leaves THOR_COOK unset and uses the
        # deterministic ScriptedCook + host-side InRoomProxy path below (the explicit gated default).
        _rt = os.environ.get("THOR_COOK")
        if cook is None and _rt and _rt not in ("scripted", "puppet"):
            return self._run_real_cook(feature, repo, fid, branch, plan, manager)

        room = manager.provision_room(fid, task_type="build", branch=branch, worktree_host_path=repo)
        room_id = room["room_id"]

        # The plan yields the FrozenPolicy the room is sealed with (Integration PRD S2).
        policy = FrozenPolicy(room_id=room_id, scope_files=tuple(plan["scope_files"]),
                              forbidden_patterns=tuple(plan["forbidden_patterns"]), frozen_at=0.0)
        # Loaded HOST-SIDE only — the policy is NEVER handed into the room; the cook can neither
        # see nor relax its own scope. That is what makes the boundary real (C1 / P1).
        agt_adapter.load_policy(policy)

        # C1: every cook write now routes THROUGH the per-room Leash BEFORE it executes (FLOW B).
        # The InRoomProxy is the cook's only exit: allow→written, deny→never created, escalate→held;
        # each decision recorded via the Manager (single ledger); fail-closed if the governor is down.
        proxy = InRoomProxy(agt_adapter, DecisionRecorder(manager), repo)
        _git(repo, "checkout", "-q", "-B", branch)

        # H4: the cook PROPOSES; the Leash DISPOSES. The cook is pluggable — default is the deterministic
        # ScriptedCook over the genesis code_files (puppet, for the gated suite); production passes a REAL
        # frontier cook (Claude Code etc. via cook.CookRuntime, running IN the room). Either way EVERY
        # action routes through the InRoomProxy above (decide-before, FLOW B) — the cook is UNTRUSTED and
        # cannot bypass it. The control plane does NOT clean/retry/supplement the cook's output.
        from cook.agent import ScriptedCook
        if cook is None:
            cook = ScriptedCook([{"name": "write_file", "args": {"path": rel, "content": content}}
                                 for rel, content in feature.get("code_files", {}).items()])
        result = cook.build({"room_id": room_id, "feature_id": fid, **feature}, proxy)
        decisions: dict[str, str] = {
            a["args"]["path"]: a["_verdict"]["status"]
            for a in (result["allowed"] + result["denied"] + result["escalated"])
            if a.get("name") == "write_file"}
        _sanitize_git_dir(repo)   # the cook may have planted .git hooks/filters — strip before host git
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.email=cook@thor", "-c", "user.name=cook", "commit", "-q",
             "-m", f"implement {feature.get('title', fid)} [{fid}]")
        return {"feature_id": fid, "branch": branch, "room_id": room_id, "claim_done": True,
                "_room": room, "decisions": decisions, "policy_hash": policy.policy_hash}

    def _run_real_cook(self, feature: dict, repo: str, fid: str, branch: str, plan: dict, manager) -> dict:
        """C2 — a REAL agent (the THOR_COOK runtime) builds INSIDE the room via CookRunner. The room is
        provisioned with the feature slice (scope at /task/feature.json, read-only) + one-door egress; the
        in-room PreToolUse hook enforces decide-before, the walls cage it, and the GovEngine verdict judges
        from reality. The control plane does NOT clean, retry, or supplement the cook's output."""
        from cook.runner import CookRunner

        _git(repo, "checkout", "-q", "-B", branch)
        # EXPLICIT slice fields only — never spread the whole feature dict, so operator-supplied context or
        # any future field never reaches the untrusted cook's read-only /task mount (AUD-realcook-hygiene).
        slice_ = {"feature_id": fid, "title": feature.get("title", fid),
                  "acceptance_criteria": feature.get("acceptance_criteria", []),
                  "scope_files": list(plan["scope_files"]),
                  "forbidden_patterns": list(plan["forbidden_patterns"]),
                  "planned_test": feature.get("planned_test"),
                  "regression_file": feature.get("regression_file")}
        runner = CookRunner()
        result = runner.run(slice_, worktree_host_path=repo)        # the agent builds in /work, in-room
        _sanitize_git_dir(repo)   # the cook may have planted .git hooks/filters — strip before host git
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.email=cook@thor", "-c", "user.name=cook", "commit", "-q",
             "-m", f"implement {feature.get('title', fid)} [{fid}]")
        exit_code = result.get("exit_code")
        # AUD-realcook-moat: the in-room hook governs each write but logs IN the room, not to the ledger,
        # so without this the ledger/cockpit would show nothing the real cook did and the verdict would
        # reconstruct an EMPTY files_touched. Record what the cook ACTUALLY landed (the git diff = the writes
        # the in-room hook let onto the branch) as allow decisions — the audit trail is real, and the verdict
        # reconstructs files_touched from reality. (Out-of-scope writes are still caught by _stakes.)
        if manager is not None:
            try:
                from govengine import reality
                _allow = type("V", (), {"decision": "allow", "reason": "real cook landed (audit)",
                                        "classification": "non_critical"})()
                for changed in sorted(reality.changed_files(repo, branch, "main")):
                    manager.record_decision(_allow, {"room_id": result["room_id"], "type": "tool_call",
                                                     "name": "write_file", "target": changed})
            except Exception:  # noqa: BLE001 — audit best-effort; the verdict is the enforcement
                pass
        # The branch is now on the host repo; the verdict reads git + runs tests on the HOST — it does not
        # need the build room. Destroy it immediately so no cook container (holding the cook's OWN
        # credential) leaks on a not_done/escalate/stop path (AUD-realcook-hygiene). The cook exit_code is
        # recorded but never trusted — the verdict-from-reality is the only arbiter of done.
        self._destroy_room(manager, result["room_id"], result.get("_mount_plan"))
        if manager is not None:
            try:
                manager._record("cook.ran", {"feature_id": fid, "room_id": result["room_id"],
                                "runtime": runner.runtime.name, "network_mode": result.get("network_mode"),
                                "exit_code": exit_code}, room_id=result["room_id"], feature_id=fid)
            except Exception:  # noqa: BLE001 — audit best-effort; the verdict is the enforcement
                pass
        return {"feature_id": fid, "branch": branch, "room_id": result["room_id"], "claim_done": True,
                "_room": {"room_id": result["room_id"], "_mount_plan": None},   # already destroyed above
                "decisions": {}, "runtime": runner.runtime.name, "exit_code": exit_code,
                "network_mode": result.get("network_mode"), "_cook_output": result.get("output")}

    @staticmethod
    def _destroy_room(manager, room_id: str, mount_plan) -> None:
        try:
            if manager is not None:
                manager.destroy_room(room_id, mount_plan)
            else:
                from wall import provisioner
                provisioner.destroy_room(room_id, mount_plan)
        except Exception:  # noqa: BLE001 — best-effort teardown; never mask the build result
            pass

    def edge_check(self, output: dict) -> tuple[bool, str]:
        ok = output.get("claim_done") and bool(output.get("branch"))
        return ok, "branch produced + claim_done emitted" if ok else "no branch / no claim_done"


# ---------------------------------------------------------------------------
class QAStage(Stage):
    name = "qa"

    def mandate(self) -> str:
        return "independent adversary: verify criteria + write NEW edge-case tests + try to break it"

    def run(self, feature: dict, repo: str, branch: str, build_room_id: str | None = None,
            manager=None, **_) -> dict:
        fid = feature["feature_id"]
        # FR-7 / AC-2: a FRESH room, different instance from the Build room.
        room = manager.provision_room(fid, task_type="qa", branch=f"qa/{fid}",
                                      codebase_host_path=repo) if manager else None
        qa_room_id = room["room_id"] if room else None

        # (a) verify the planned acceptance criteria (run the planned test).
        planned = feature.get("planned_test")
        planned_pass = self._run(repo, planned)[0] == 0 if planned else True

        # (b) read the ACTUAL code and write NEW edge-case tests beyond the plan (FR-8).
        new_tests, bugs = self._adversarial(repo, feature)

        # (c) emit findings as structured bugs to the DB via the Manager (FR-9 / AC-4).
        if manager:
            for b in bugs:
                manager.append_bug(fid, "high", b, source="qa")
            manager.destroy_room(room["room_id"], room.get("_mount_plan"))

        passed = planned_pass and not bugs
        return {"feature_id": fid, "passed": passed, "planned_pass": planned_pass,
                "new_tests": new_tests, "bugs": bugs, "qa_room_id": qa_room_id,
                "independent": qa_room_id != build_room_id}

    def _run(self, repo, rel):
        # QA runs the cook's planned test AND edge tests that import+call the cook's code — untrusted code.
        # With a real cook in play it runs SEALED (no host, no secrets, no network), same as the verdict;
        # the docker-free gated suite (trusted fixtures) uses a minimal-env host subprocess.
        if not rel or not os.path.exists(os.path.join(repo, rel)):
            return 1, "no test"
        from govengine import reality
        if reality._use_sandbox():
            rc, out, _ = reality.sandboxed_run(repo, ["python3", rel])
            return rc, out
        p = subprocess.run(["python3", os.path.join(repo, rel)], capture_output=True, text=True,
                           cwd=repo, env=reality._minimal_env(), timeout=30)
        return p.returncode, p.stdout + p.stderr

    # A MATRIX of edge inputs (not just zeros): empty/boundary values that trip un-handled cases.
    _QA_EDGE_INPUTS = ("0", "-1", "[]", "''", "{}", "None")
    # Only REAL-bug exceptions count (un-handled boundary/data errors). TypeError/AttributeError/
    # ValueError are EXCLUDED — passing a wrong-typed edge value or hitting a validation guard is not a
    # bug in the function, so clean numeric code (e.g. add(a,b)) is never false-flagged (no softening,
    # no false positives — failure-mode C both ways).
    _QA_BUG_EXC = ("ZeroDivisionError", "IndexError", "KeyError", "StopIteration",
                   "RecursionError", "OverflowError", "UnboundLocalError")

    def _adversarial(self, repo, feature):
        """Independent adversary: from the ACTUAL code, fuzz a matrix of edge inputs and flag any
        un-handled REAL-bug crash (a non-zeros bug — empty list, boundary — is caught, not just zeros)."""
        code_rel = feature.get("code_file")
        new_tests, bugs = [], []
        if not code_rel or not os.path.exists(os.path.join(repo, code_rel)):
            return new_tests, bugs
        src = open(os.path.join(repo, code_rel)).read()
        module = os.path.splitext(os.path.basename(code_rel))[0]
        mod_dir = os.path.dirname(code_rel) or "."
        bug_excs = ", ".join(self._QA_BUG_EXC)
        for name, params in re.findall(r"def (\w+)\(([^)]*)\)", src):
            n = len([p for p in params.split(",") if p.strip()])
            test_name = f"edge_{name}"
            new_tests.append(test_name)
            for ev in self._QA_EDGE_INPUTS:                      # try each edge input until one crashes
                args = ", ".join([ev] * n)
                script = (f"import sys; sys.path.insert(0, {mod_dir!r})\n"
                          f"from {module} import {name}\n"
                          f"try:\n    {name}({args})\n"
                          f"except ({bug_excs}) as e:\n"
                          f"    print('EDGE_BUG', type(e).__name__); sys.exit(2)\n"
                          f"except Exception:\n    pass\n"        # type-misuse / validation = NOT a bug
                          f"print('ok')\n")
                tf = os.path.join(repo, f".qa_{test_name}.py")
                open(tf, "w").write(script)
                rc, out = self._run(repo, f".qa_{test_name}.py")
                os.remove(tf)                                    # QA's own test space — cleaned up
                if rc == 2:
                    bugs.append(f"{name}() crashes on edge input ({args}): {out.strip().split()[-1]}")
                    break                                        # one confirmed crash per function is enough
        return new_tests, bugs

    def edge_check(self, output: dict) -> tuple[bool, str]:
        ok = output["independent"] and bool(output["new_tests"])
        return ok, "independent QA ran + wrote new tests" if ok else "QA not independent or wrote no tests"
