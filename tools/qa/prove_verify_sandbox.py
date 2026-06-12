"""
RED-TEAM proof — the verdict runs the COOK-WRITTEN test, so a malicious test is RCE on the control plane
unless it runs sealed. With a real cook in play (THOR_COOK set), reality.run_test must execute the test in
a network-disabled, minimal-env, non-root container against a repo COPY: no plane secret, no host write, no
network. This PoC plants an attack test and proves all three vectors are dead.

Run (from ~/thor-enterprise):  PYTHONPATH=. .venv/bin/python tools/qa/prove_verify_sandbox.py
"""
import os
import tempfile

os.environ["THOR_COOK"] = "generic"                          # a real (untrusted) cook is in play
os.environ["THOR_API_TOKEN"] = "PLANE-TOP-SECRET-do-not-leak"  # a secret that lives in the plane env

from govengine import reality  # noqa: E402

repo = tempfile.mkdtemp(prefix="sbx-")
os.makedirs(os.path.join(repo, "src"))
attack = (
    "import os\n"
    "print('SECRET_SEEN=' + os.environ.get('THOR_API_TOKEN', 'NONE'))\n"
    "try:\n"
    "    open('/host_pwned_marker', 'w').write('pwned'); print('HOST_WRITE=ok')\n"
    "except Exception as e: print('HOST_WRITE=blocked:' + type(e).__name__)\n"
    "try:\n"
    "    import urllib.request; urllib.request.urlopen('http://example.com', timeout=5); print('NET=reachable')\n"
    "except Exception as e: print('NET=blocked:' + type(e).__name__)\n"
)
with open(os.path.join(repo, "src", "test_calc.py"), "w") as f:
    f.write(attack)

rc, out = reality.run_test(repo, "src/test_calc.py")
print("--- sandboxed attack-test output ---")
print(out.strip())

assert "SECRET_SEEN=NONE" in out, "FAIL: the plane secret was visible to the cook test"
assert "NET=blocked" in out, "FAIL: the cook test reached the network"
assert not os.path.exists("/host_pwned_marker"), "FAIL: the cook test wrote the host filesystem"
print("VERIFY_SANDBOX_OK — cook test code is sealed: no plane secret, no host write, no network.")
