"""
run_real_task — drive ONE real feature through THOR end-to-end with a REAL cook:
  assign_task -> the cook builds it IN a sealed one-door room -> verdict-from-reality -> human Ed25519
  signature -> real git merge into the repo's main.

The cook is chosen by THOR_COOK (no THOR source change to swap agents):

  • claude-code  (default) — Claude Code authenticated by your SUBSCRIPTION login, NOT a paid API key.
        Get the token once on a logged-in machine:   claude setup-token
        Then:   export CLAUDE_CODE_OAUTH_TOKEN=<the token>
        Image (built): thor-room-claude:latest  (carries the claude CLI + the unbypassable Leash hook).

  • generic — bring ANY agent (Kimi, a local model, your own) with a Docker image + launch command:
        export THOR_COOK=generic THOR_COOK_IMAGE=<image> THOR_COOK_CMD='<how to launch it>'
        (inject the agent's own secret via THOR_COOK_ENV_*; THOR governs it identically).

The task + repo are configurable (else a real demo runs):
  THOR_TASK_REPO=/path/to/a/git/repo        (default: a throwaway demo repo is created)
  THOR_TASK_SCOPE=src/util.py               (the ONLY file the cook may write + the verdict's target)
  THOR_TASK_TEST=src/test_util.py           (the test the cook must write; the verdict RUNS it)
  THOR_TASK_DESC='<what to build>'           (natural-language acceptance criteria for the agent)

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/run_real_task.py
"""
import os
import subprocess
import sys
import tempfile

import docker

COOK = os.environ.setdefault("THOR_COOK", "claude-code")
if COOK == "claude-code":
    os.environ.setdefault("THOR_COOK_IMAGE", "thor-room-claude:latest")
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        sys.exit("CLAUDE_CODE_OAUTH_TOKEN is not set.\n"
                 "  Run `claude setup-token` on a machine logged into your Claude subscription, then:\n"
                 "    export CLAUDE_CODE_OAUTH_TOKEN=<the token>\n"
                 "  (This uses your subscription — NO per-token API cost. Or set THOR_COOK=generic for your own agent.)")

SCOPE = os.environ.get("THOR_TASK_SCOPE", "src/util.py")
TESTF = os.environ.get("THOR_TASK_TEST", "src/test_util.py")
DESC = os.environ.get("THOR_TASK_DESC",
                      "Add a function slugify(text) that returns a URL-safe slug: lowercase, spaces and "
                      "underscores become single hyphens, drop every other non-alphanumeric, collapse "
                      "repeated hyphens, and strip leading/trailing hyphens. Add a real test that asserts "
                      "slugify('Hello,  World!') == 'hello-world'.")

from contract.seam import Seam  # noqa: E402
from contract.slice_builder import build_slice  # noqa: E402
from contract.transport import InProcessTransport  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402
from govengine.engine import GovernanceEngine, VerdictContext  # noqa: E402
from manager import db, pg  # noqa: E402
from manager.core import ThorManager  # noqa: E402
from sdlc.merge_driver import MergeDriver  # noqa: E402
from sdlc.stages import BuildStage  # noqa: E402
from wall.identity_stamper import _b64  # noqa: E402


def _demo_repo() -> str:
    repo = tempfile.mkdtemp(prefix="thor-task-")
    os.chmod(repo, 0o777)
    os.makedirs(os.path.join(repo, "src"))
    open(os.path.join(repo, "src", "__init__.py"), "w").close()
    open(os.path.join(repo, "README.md"), "w").write("# Demo project governed by THOR\n")
    for a in (["init", "-q", repo], ["-C", repo, "add", "-A"],
              ["-C", repo, "-c", "user.email=demo@x", "-c", "user.name=Demo", "commit", "-q", "-m", "initial"],
              ["-C", repo, "branch", "-M", "main"]):
        subprocess.run(["git", *a], capture_output=True)
    return repo


repo = os.environ.get("THOR_TASK_REPO") or _demo_repo()
print(f"[task] cook={COOK}  repo={repo}\n[task] {DESC}\n")

# THOR ledger + manager + the operator (CEO) signing key
pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
mgr = ThorManager(conn)
priv = Ed25519PrivateKey.generate()
pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
mgr.register_operator(pub)

fid = "TASK1"
feature = {"feature_id": fid, "task_type": "build", "acceptance_criteria": [DESC],
           "scope_files": [SCOPE], "planned_test": TESTF, "regression_file": TESTF, "code_file": SCOPE}
seam = Seam(InProcessTransport(), manager=mgr)
seam.manager_send("assign_task", {"room_id": "room-assign",
                  "feature_slice": build_slice(feature, {"scope_files": [SCOPE]}).model_dump()})

print("[task] the cook is building in a sealed one-door room (this is the real agent — it may take a minute)...")
out = BuildStage().execute(feature=feature, repo=repo, manager=mgr)
branch = out["branch"]
print(f"[task] build done — branch={branch} net={out.get('network_mode')} runtime={out.get('runtime')}")

print("[task] verdict-from-reality (THOR runs the cook's test SEALED + judges the diff)...")
result = mgr.run_verdict(fid, branch, repo)
print(f"[task] VERDICT = {result['verdict'].upper()}  ({result.get('reason', '')})")

if result["verdict"] != "done":
    diff = subprocess.run(["git", "-C", repo, "diff", "main..." + branch], capture_output=True, text=True).stdout
    print("\n[task] the verdict was NOT 'done' — THOR refuses to merge unproven work (this is correct).")
    print("[task] what the cook actually changed:\n" + (diff[:1500] or "(no diff)"))
    sys.exit(0)

# human signs (Ed25519 + one-time nonce) -> real merge into main
driver = MergeDriver(mgr, engine=GovernanceEngine(mgr))
card = driver.on_verdict(result)
nonce = mgr.issue_challenge(card)
material = ThorManager.card_material(card, mgr._get_card(card)["payload"], nonce)
assert mgr.approve(card, _b64(priv.sign(material.encode())), pub, nonce=nonce)["verified"], "signature rejected"
merged = driver.merge_if_authorized(card, repo, branch, result, VerdictContext(fid, branch, repo, contract={}))
assert merged["merged"], merged

subprocess.run(["git", "-C", repo, "checkout", "-q", "main"], capture_output=True)
final = subprocess.run(["git", "-C", repo, "show", "main:" + SCOPE], capture_output=True, text=True).stdout
print(f"\n[task] ✅ MERGED into main of {repo}")
print(f"[task] {SCOPE} on main now:\n----\n{final.rstrip()}\n----")
print("REAL_TASK_OK")
