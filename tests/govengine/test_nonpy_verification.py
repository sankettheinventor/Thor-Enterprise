"""
Language-agnostic mechanical verification (HH-nonpy-coverage closed). A non-Python feature is now machine-
verified by mutation-discrimination: empty each contracted source and re-run the cook's test — a test that
genuinely exercises the source must go RED. Proven here with SHELL source/tests (docker-free: `sh` is on the
host, so the gated trusted path runs without a sandbox). Only when the test does NOT exercise the source (or
its runtime is absent) does the feature escalate to a human — never a false auto-`done`.
"""
import os
import stat

from govengine import fake_test, reality
from govengine.engine import _stakes


def _w(p, content):
    with open(p, "w") as f:
        f.write(content)
    os.chmod(p, os.stat(p).st_mode | stat.S_IRWXU)


def _repo(tmp_path, source, test, src_name="greet.sh", test_name="test_greet.sh"):
    os.makedirs(tmp_path, exist_ok=True)
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


def test_m1_runner_is_language_aware(tmp_path):
    """The M1 test runner runs the RIGHT interpreter for the test's language (here: shell), not python3."""
    repo, contract = _repo(tmp_path, "echo hello\n", REAL_TEST)
    argv = fake_test.test_argv(contract["test_file"], contract)
    assert argv == ["sh", "test_greet.sh"]
    rc, _ = reality.run_test(repo, contract["test_file"], argv=argv)
    assert rc == 0                                  # the shell test ran and passed (python3 would have errored)
    # a broken source makes the same runner report failure
    _w(tmp_path / "greet.sh", "echo goodbye\n")
    rc2, _ = reality.run_test(repo, contract["test_file"], argv=argv)
    assert rc2 != 0


def test_is_hollow_routes_non_python_to_mutation_check(tmp_path):
    """M1's hollow gate catches a hollow SHELL test and passes a genuine one — no Python needed."""
    repo_ok, c_ok = _repo(tmp_path / "ok", "echo hello\n", REAL_TEST)
    hollow, _ = fake_test.is_hollow(repo_ok, c_ok["test_file"], c_ok)
    assert hollow is False                          # genuine shell test → not hollow
    repo_bad, c_bad = _repo(tmp_path / "bad", "echo hello\n", "exit 0\n")
    hollow2, _ = fake_test.is_hollow(repo_bad, c_bad["test_file"], c_bad)
    assert hollow2 is True                          # vacuous shell test → hollow (M1 will fail it)


def test_test_command_override_runs_the_declared_command(tmp_path):
    # a .conf source verified by an explicit shell test_command
    _w(tmp_path / "app.conf", "port=8080\n")
    _w(tmp_path / "check.sh", 'grep -q "port=8080" app.conf && exit 0 || exit 1\n')
    contract = {"scope": {"files": ["app.conf"]}, "test_file": "check.sh",
                "test_command": "sh check.sh"}
    status, why = fake_test.verify_nonpython(str(tmp_path), contract)
    assert status == "verified", why
