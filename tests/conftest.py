"""
THOR test harness — shared fixtures (per docs/THOR-TEST-ENVIRONMENT.md).

The point: a green from the DEFERRED (LANE 2) run is trustworthy because every run starts from an
IDENTICAL clean state and exercises the REAL wired system (live Postgres + real Docker rooms + the
booted control plane), then tears down deterministically. Nothing here is a stand-in (Rule 11).

Fixtures:
  fresh_ledger  — a real Postgres-backed connection on a TRUNCATEd ledger (asserts genesis). [R1]
  clean_docker  — session autouse (deferred lane only): reaps THOR rooms before+after. [R2/R4]
  booted_plane  — the live control plane's URLs; reuses a running plane or boots one (subprocess). [R3]
  host_repo     — a throwaway git repo for AC-1-style real-commit proofs.

Lanes: default `pytest` (LANE 1) deselects `deferred` (addopts) → docker-free, fast. `pytest -m
deferred` (LANE 2) selects them → live. These fixtures only do heavy work in the deferred lane.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
VENV_PY = REPO / ".venv" / "bin" / "python"
SURFACES = {"manager": 7100, "dashboard": 7080, "sentinel": 7140, "selfaudit": 7150}
ROOM_LABEL = "thor.room=1"


def _lane(config) -> str:
    """'deferred' (LANE 2, live) when the marker expression is exactly 'deferred', else 'fast'."""
    expr = (getattr(config.option, "markexpr", "") or "").strip()
    return "deferred" if expr == "deferred" else "fast"


def _docker_or_none():
    try:
        import docker
        c = docker.from_env()
        c.ping()
        return c
    except Exception:  # noqa: BLE001
        return None


def _reap_rooms(client) -> list[str]:
    reaped = []
    for c in client.containers.list(all=True, filters={"label": ROOM_LABEL}):
        try:
            c.remove(force=True)
            reaped.append(c.name)
        except Exception:  # noqa: BLE001
            pass
    return reaped


def _http_ok(url: str, timeout: float = 1.0) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def clean_docker(request):
    """[R2/R4] In the deferred lane: reap all THOR rooms BEFORE (assert zero) and AFTER the run."""
    if _lane(request.config) != "deferred":
        yield None
        return
    client = _docker_or_none()
    if client is None:
        yield None
        return
    _reap_rooms(client)
    leftover = client.containers.list(all=True, filters={"label": ROOM_LABEL})
    assert leftover == [], f"clean start violated: THOR rooms present after reap: {leftover}"
    yield client
    _reap_rooms(client)  # deterministic teardown — a failed run never poisons the next


@pytest.fixture
def fresh_ledger():
    """[R1] A real Postgres connection on a TRUNCATEd ledger; asserts it starts at genesis."""
    try:
        from manager import db
        if os.environ.get("THOR_PG_DSN"):
            # QA lane (make qa): a SEPARATE throwaway Postgres is already provisioned on its own
            # network+volume; connect straight to it — no Docker socket inside the QA room, so the QA
            # verdict stays isolated from the dev DB. dev/prove lanes are unchanged (else-branch).
            conn = db.connect()
            db.init_schema(conn)
        else:
            import docker
            from manager import pg
            pg.start(docker.from_env())
            conn = db.connect()
            db.init_schema(conn)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"postgres/docker unavailable: {e}")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE eventlog, rooms, cards, features")
    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM eventlog")
        assert cur.fetchone()[0] == 0, "fresh_ledger must start at genesis (empty eventlog)"
    return conn


@pytest.fixture(scope="session")
def booted_plane(request):
    """[R3] URLs of the live control plane. Reuses a running plane; else boots one (subprocess)."""
    if _lane(request.config) != "deferred":
        pytest.skip("booted_plane is a deferred-lane (live) fixture")
    urls = {name: f"http://127.0.0.1:{p}" for name, p in SURFACES.items()}
    if _http_ok(urls["manager"] + "/health"):
        yield urls  # a plane is already up (e.g. started by `make prove`); don't manage its lifecycle
        return
    proc = subprocess.Popen([str(VENV_PY), "tools/start_thor.py"], cwd=str(REPO),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if _http_ok(urls["manager"] + "/health"):
                break
            time.sleep(1)
        else:
            raise RuntimeError("control plane did not boot within 60s")
        yield urls
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()


@pytest.fixture
def host_repo():
    """A throwaway git repo on a feature branch — the cook's read-write worktree for real proofs."""
    import tempfile
    d = tempfile.mkdtemp(prefix="thor-hostrepo-")
    os.chmod(d, 0o777)
    subprocess.run(f"git init -q {d}", shell=True, check=False)
    subprocess.run(f'git -C {d} config user.email cook@thor.local; '
                   f'git -C {d} config user.name "THOR Cook"', shell=True, check=False)
    subprocess.run(f"git -C {d} checkout -q -b room/test", shell=True, check=False)
    return d
