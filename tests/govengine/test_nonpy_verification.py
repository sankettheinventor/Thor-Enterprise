"""
Language-agnostic mechanical verification (HH-nonpy-coverage closed). A non-Python feature is now machine-
verified by mutation-discrimination: empty each contracted source and re-run the cook's test — a test that
genuinely exercises the source must go RED. Proven here with SHELL source/tests (docker-free: `sh` is on the
host, so the gated trusted path runs without a sandbox). Only when the test does NOT exercise the source (or
its runtime is absent) does the feature escalate to a human — never a false auto-`done`.
"""
import os
import stat

from govengine import fake_test
from govengine.engine import _stakes


def _w(p, content):
    with open(p, "w") as f:
        f.write(content)
    os.chmod(p, os.stat(p).st_mode | stat.S_IRWXU)


def _repo(tmp_path, source, test, src_name="greet.sh", test_name="test_greet.sh"):
    _w(tmp_path / src_name, source)
    _w(tmp_path / test_name, test)
    return str(tmp_path), {"scope": {"files": [src_name]}, "test_file": test_name}


REAL_TEST = 'out=$(sh greet.sh)\n[ "$out" = "hello" ] && exit 0 || exit 1\n'


def test_genuine_shell_feature_is_verified(tmp_path):
    repo, contract = _repo(tmp_path, "echo hello\n", REAL_TEST)
    status, why = fake_test.verify_nonpython(repo, contract)
    assert status == "verified", why
    # and the verdict therefore does NOT escalate the non-.py source
    assert _stakes(contract, {"greet.sh"}, status) == "normal"


def test_hollow_shell_test_is_unverified_and_escalates(tmp_path):
    # a test that asserts nothing (exits 0 regardless) does not exercise the source
    repo, contract = _repo(tmp_path, "echo hello\n", "exit 0\n")
    status, why = fake_test.verify_nonpython(repo, contract)
    assert status == "unverified", why
    # fail-closed: the feature escalates to a human signature (high stakes)
    assert _stakes(contract, {"greet.sh"}, status) == "high"


def test_python_feature_is_not_affected(tmp_path):
    contract = {"scope": {"files": ["src/login.py"]}, "test_file": "test_login.py"}
    status, _ = fake_test.verify_nonpython(str(tmp_path), contract)
    assert status == "n/a"                          # python keeps its own (behaviour-level) gates
    assert _stakes(contract, {"src/login.py"}) == "normal"


def test_unknown_runner_escalates(tmp_path):
    # a test whose extension has no known interpreter and no contract.test_command → cannot run → escalate
    repo, contract = _repo(tmp_path, "echo hello\n", "whatever\n",
                           src_name="thing.conf", test_name="check.xyz")
    status, why = fake_test.verify_nonpython(repo, contract)
    assert status == "unverified", why
    assert _stakes(contract, {"thing.conf"}, status) == "high"


def test_test_command_override_runs_the_declared_command(tmp_path):
    # a .conf source verified by an explicit shell test_command
    _w(tmp_path / "app.conf", "port=8080\n")
    _w(tmp_path / "check.sh", 'grep -q "port=8080" app.conf && exit 0 || exit 1\n')
    contract = {"scope": {"files": ["app.conf"]}, "test_file": "check.sh",
                "test_command": "sh check.sh"}
    status, why = fake_test.verify_nonpython(str(tmp_path), contract)
    assert status == "verified", why
