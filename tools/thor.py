#!/usr/bin/env python3
"""
thor — the THOR project CLI. How a user STARTS and RUNS a governed project. No code editor required.

  thor init <name>                 create a NEW governed project (an empty git repo) — "Session 0".
  thor attach <path|git-url>       bring an EXISTING project under THOR governance.
  thor build <repo> "<what>" [opts]  the governed build: a real cook builds it in a sealed room ->
                                   verdict-from-reality -> human Ed25519 signature -> merge into main.
        --scope a.js,b.js          the ONLY files the cook may write (+ the verdict's targets).
        --test  path/to/test       the test the cook must write; the verdict RUNS it (node/python/... by ext).
        --cook  claude-code|generic  default claude-code (reuses your existing Claude login — no API cost).
  thor status <repo>               where the project stands (branches + the governed history).

Cook auth: Claude Code reuses your current login automatically (no token). For a JS/TS project, set
THOR_VERIFY_IMAGE=thor-room-claude:latest so the sealed verdict can run node.
"""
from __future__ import annotations

import os
import subprocess
import sys

PROJECTS = os.path.expanduser(os.environ.get("THOR_PROJECTS_DIR", "~/thor-projects"))


def _git(repo, *a, check=True):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=check)


def cmd_init(name: str) -> int:
    repo = os.path.join(PROJECTS, name)
    if os.path.exists(repo):
        sys.exit(f"already exists: {repo}")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    open(os.path.join(repo, "README.md"), "w").write(f"# {name}\n\nA THOR-governed project. Built by AI, judged from reality, human-signed.\n")
    _git(repo, "add", "-A"); _git(repo, "-c", "user.email=thor@local", "-c", "user.name=THOR", "commit", "-q", "-m", "thor init")
    _git(repo, "branch", "-M", "main")
    print(f"✅ Session 0 ready — new governed project at {repo}")
    print(f"   Now describe a feature:\n   thor build {repo} \"add a function ...\" --scope src/x.js --test src/x.test.mjs")
    return 0


def cmd_attach(src: str) -> int:
    os.makedirs(PROJECTS, exist_ok=True)
    if src.startswith(("http://", "https://", "git@")):
        name = os.path.basename(src).removesuffix(".git")
        repo = os.path.join(PROJECTS, name)
        if not os.path.exists(repo):
            print(f"cloning {src} ...")
            subprocess.run(["git", "clone", "-q", src, repo], check=True)
    else:
        repo = os.path.abspath(os.path.expanduser(src))
        if not os.path.isdir(os.path.join(repo, ".git")):
            sys.exit(f"not a git repo: {repo}")
    head = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    print(f"✅ Attached — {repo} (on {head}). THOR will build into branches off main and merge on your signature.")
    print(f"   Assign work:\n   thor build {repo} \"<what to build>\" --scope <files> --test <testfile>")
    return 0


def cmd_status(repo: str) -> int:
    repo = os.path.abspath(os.path.expanduser(repo))
    print(f"project: {repo}")
    print("branches:\n" + _git(repo, "branch", "-a", check=False).stdout)
    print("recent governed history:\n" + _git(repo, "log", "--oneline", "-8", check=False).stdout)
    return 0


def cmd_build(repo: str, desc: str, scope: str, test: str, cook: str, autosign: bool) -> int:
    repo = os.path.abspath(os.path.expanduser(repo))
    os.environ["THOR_COOK"] = cook
    if cook == "claude-code":
        os.environ.setdefault("THOR_COOK_IMAGE", "thor-room-claude:latest")
        from cook.runtime import discover_claude_oauth
        if not discover_claude_oauth():
            sys.exit("No Claude login found — log into Claude Code on this machine (no API cost), or set THOR_COOK=generic.")
    scope_files = [s.strip() for s in scope.split(",") if s.strip()]
    if not scope_files or not test:
        sys.exit("build needs --scope <files> and --test <testfile>")
    # spell out the verdict's execution contract so the agent's test is runnable + exercises the new code
    full_desc = (f"{desc} Put the implementation in {scope_files[0]} and a real test in {test}. The test is "
                 f"executed directly (e.g. `node {test}` / `python3 {test}`), so its assertions must RUN when "
                 f"the file is executed (not a framework), import the code under test, and print 'ok' at the end.")

    import docker
    from contract.seam import Seam
    from contract.slice_builder import build_slice
    from contract.transport import InProcessTransport
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from govengine.engine import GovernanceEngine, VerdictContext
    from manager import db, pg
    from manager.core import ThorManager
    from sdlc.merge_driver import MergeDriver
    from sdlc.stages import BuildStage
    from wall.identity_stamper import _b64

    pg.start(docker.from_env())
    conn = db.connect(); db.init_schema(conn)
    mgr = ThorManager(conn)
    priv = Ed25519PrivateKey.generate()
    pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    mgr.register_operator(pub)

    fid = "F" + os.urandom(2).hex().upper()
    feature = {"feature_id": fid, "task_type": "build", "acceptance_criteria": [full_desc],
               "scope_files": scope_files + [test], "planned_test": test, "regression_file": test, "code_file": scope_files[0]}
    Seam(InProcessTransport(), manager=mgr).manager_send(
        "assign_task", {"room_id": "room-assign", "feature_slice": build_slice(feature, {"scope_files": scope_files + [test]}).model_dump()})

    print(f"\n[{fid}] {desc}\n[{fid}] the cook ({cook}) is building in a sealed one-door room ...")
    out = BuildStage().execute(feature=feature, repo=repo, manager=mgr)
    branch = out["branch"]
    print(f"[{fid}] build done — branch={branch} net={out.get('network_mode')}")
    result = mgr.run_verdict(fid, branch, repo)
    print(f"[{fid}] VERDICT = {result['verdict'].upper()}  ({result.get('reason','')})")
    for b in result.get("blockers", []):
        print(f"[{fid}]   blocker: {b.get('probe')} — {str(b.get('detail'))[:120]}")

    if result["verdict"] != "done":
        diff = _git(repo, "diff", f"main...{branch}", check=False).stdout
        print(f"[{fid}] not merged (THOR refuses unproven work). The cook's diff:\n{diff[:1600]}")
        return 1
    if not autosign:
        print(f"[{fid}] DONE — awaiting your signature in the cockpit (Need Your Decisions).")
        return 0
    driver = MergeDriver(mgr, engine=GovernanceEngine(mgr))
    card = driver.on_verdict(result)
    nonce = mgr.issue_challenge(card)
    material = ThorManager.card_material(card, mgr._get_card(card)["payload"], nonce)
    assert mgr.approve(card, _b64(priv.sign(material.encode())), pub, nonce=nonce)["verified"]
    assert driver.merge_if_authorized(card, repo, branch, result, VerdictContext(fid, branch, repo, contract={}))["merged"]
    _git(repo, "checkout", "-q", "main", check=False)
    print(f"[{fid}] ✅ signed + MERGED into main of {repo}")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__); return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "init" and rest:
        return cmd_init(rest[0])
    if cmd == "attach" and rest:
        return cmd_attach(rest[0])
    if cmd == "status" and rest:
        return cmd_status(rest[0])
    if cmd == "build" and len(rest) >= 2:
        repo, desc = rest[0], rest[1]
        opts = rest[2:]
        def opt(name, default=None):
            return opts[opts.index(name) + 1] if name in opts else default
        return cmd_build(repo, desc, opt("--scope", ""), opt("--test", ""),
                         opt("--cook", "claude-code"), "--nosign" not in opts)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
