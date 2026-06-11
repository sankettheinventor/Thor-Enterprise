"""
C3 proof — THOR carries ONE real change into a SEPARATE external repo (not the bundled THOR repo) through
the FULL signed operator flow: assign_task -> real-cook build IN the repo's worktree -> verdict-from-reality
-> human Ed25519 signature -> real git merge into the external repo's main. Proves the external-project path
needs ZERO code edits — only documented env (THOR_COOK, THOR_COOK_IMAGE) + the repo path.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_c3_external_repo.py
"""
import base64
import os
import subprocess
import tempfile

import docker

from wall import config

os.environ["THOR_COOK"] = "generic"
os.environ["THOR_COOK_IMAGE"] = config.ROOM_IMAGE

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

# ---- 1. a SEPARATE external "customer" repo (NOT the THOR repo) ----
ext = tempfile.mkdtemp(prefix="EXTERNAL-customer-")
os.chmod(ext, 0o777)


def g(*a):
    subprocess.run(["git", "-C", ext, *a], capture_output=True)


subprocess.run(["git", "init", "-q", ext])
os.makedirs(os.path.join(ext, "src"))
open(os.path.join(ext, "src", "greeter.py"), "w").write("def greet(name):\n    return 'hi ' + name\n")
open(os.path.join(ext, "README.md"), "w").write("# Acme customer project (a separate repo)\n")
g("add", "-A")
g("-c", "user.email=acme@x", "-c", "user.name=Acme", "commit", "-q", "-m", "initial")
g("branch", "-M", "main")
before = open(os.path.join(ext, "src", "greeter.py")).read()

# ---- 2. THOR ledger + manager + the CEO's operator key ----
pg.start(docker.from_env())
conn = db.connect()
db.init_schema(conn)
with conn.cursor() as c:
    c.execute("TRUNCATE eventlog, rooms, cards, features")
conn.commit()
mgr = ThorManager(conn)
priv = Ed25519PrivateKey.generate()
pub = _b64(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
mgr.register_operator(pub)

# ---- 3. operator flow: a feature + its contract, targeting the external repo ----
fid = "EXT1"
feature = {"feature_id": fid, "task_type": "build", "acceptance_criteria": ["greeting upgraded"],
           "scope_files": ["src/greeter.py"], "planned_test": "src/test_greeter.py",
           "regression_file": "src/test_greeter.py", "code_file": "src/greeter.py"}
seam = Seam(InProcessTransport(), manager=mgr)
seam.manager_send("assign_task", {"room_id": "room-assign",
                  "feature_slice": build_slice(feature, {"scope_files": ["src/greeter.py"]}).model_dump()})

# ---- 4. a real (deterministic) agent builds the change IN the external repo's worktree ----
NEW = "def greet(name):\n    return 'Hello, ' + name + '!'\n"
TEST = ("import sys; sys.path.insert(0, 'src')\nfrom greeter import greet\n"
        "assert greet('Acme') == 'Hello, Acme!'\nprint('ok')\n")
agent = ("import os\n"
         f"open('src/greeter.py','w').write({NEW!r})\n"
         f"open('src/test_greeter.py','w').write({TEST!r})\n"
         "print('AGENT BUILT in the external repo')\n")
os.environ["THOR_COOK_CMD"] = "sh -c 'echo %s | base64 -d | python3'" % base64.b64encode(agent.encode()).decode()
out = BuildStage().execute(feature=feature, repo=ext, manager=mgr)
branch = out["branch"]

# ---- 5. verdict-from-reality ----
result = mgr.run_verdict(fid, branch, ext)
assert result["verdict"] == "done", result

# ---- 6. human signs (Ed25519 + one-time nonce) -> real merge into the external repo's main ----
driver = MergeDriver(mgr, engine=GovernanceEngine(mgr))
card = driver.on_verdict(result)
assert card, "a done verdict must raise a merge card"
nonce = mgr.issue_challenge(card)
material = ThorManager.card_material(card, mgr._get_card(card)["payload"], nonce)
assert mgr.approve(card, _b64(priv.sign(material.encode())), pub, nonce=nonce)["verified"]
merged = driver.merge_if_authorized(card, ext, branch, result, VerdictContext(fid, branch, ext, contract={}))
assert merged["merged"], merged

# ---- 7. verify the change is on the EXTERNAL repo's main + signed in the ledger ----
g("checkout", "-q", "main")
after = open(os.path.join(ext, "src", "greeter.py")).read()
assert "Hello," in after and after != before
assert any(e["event_type"] == "feature.merged" for e in mgr.eventlog.all_events())

print("external repo:", ext)
print("greeter.py BEFORE:", before.strip().replace("\n", " | "))
print("greeter.py AFTER (on main):", after.strip().replace("\n", " | "))
print(f"verdict={result['verdict']} merged={merged['merged']} net={out.get('network_mode')} runtime={out.get('runtime')}")
print("C3_EXTERNAL_REPO_OK")
