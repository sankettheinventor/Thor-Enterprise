"""
Trusted project-prep phase (real installable repos) — the SECURITY-CRITICAL gating is tested here
docker-free. The actual build (network-on container) is integration-proven by the live humanize run.

Prep builds the project + installs declared deps into a COPY for the test runs, then the SEALED test runs
against it. It must be SKIPPED whenever it could run cook-tampered build code:
  * only for a real cook (THOR_COOK set) — the gated suite is self-contained;
  * only for an installable project (pyproject/setup.py present);
  * NEVER when the cook's diff touched a build/config file (those escalate to a human anyway).
"""
import os

from govengine import reality


def _proj(tmp_path, meta="pyproject.toml"):
    (tmp_path / meta).write_text("[build-system]\nrequires=['setuptools']\n")
    return str(tmp_path)


def test_build_file_classifier():
    assert reality._is_build_file("pyproject.toml")
    assert reality._is_build_file("setup.py")
    assert reality._is_build_file("a/b/requirements-dev.txt")
    assert reality._is_build_file("tox.ini")
    assert not reality._is_build_file("src/humanize/number.py")
    assert not reality._is_build_file("tests/test_roman.py")


def test_skipped_without_real_cook(tmp_path, monkeypatch):
    monkeypatch.delenv("THOR_COOK", raising=False)          # gated suite — never preps
    repo = _proj(tmp_path)
    assert reality.prepare_project(repo, []) == repo


def test_skipped_for_non_installable_project(tmp_path, monkeypatch):
    monkeypatch.setenv("THOR_COOK", "claude-code")
    repo = str(tmp_path)                                     # no pyproject/setup.py
    assert reality.prepare_project(repo, []) == repo


def test_skipped_when_cook_touched_a_build_file(tmp_path, monkeypatch):
    monkeypatch.setenv("THOR_COOK", "claude-code")
    repo = _proj(tmp_path)
    # the cook changed pyproject.toml -> NEVER run that build; the un-prepared repo is returned (escalates)
    assert reality.prepare_project(repo, ["src/x.py", "pyproject.toml"]) == repo


def test_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("THOR_COOK", "claude-code")
    monkeypatch.setenv("THOR_VERIFY_PREP", "0")
    assert reality.prepare_project(_proj(tmp_path), []) == str(tmp_path)


def test_cleanup_only_removes_a_prepared_copy(tmp_path):
    repo = str(tmp_path)
    reality.cleanup_prepared(repo, repo)                    # test_repo == repo -> no-op (must not delete repo)
    assert os.path.isdir(repo)
