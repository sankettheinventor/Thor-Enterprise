"""
Postgres container lifecycle for the THOR Manager's [ThorDB] + [EventLog].

Bootstrap convenience: stand up a local postgres:16-alpine on a high host port (so it never
collides with a system Postgres). In production this is an external managed Postgres; only the
DSN changes.
"""
from __future__ import annotations

import os
import time

import docker

# Bootstrap defaults are TODAY'S exact values, so an unconfigured process (make test / make prove)
# behaves identically. The QA lane (make qa) sets these env vars to point at a SEPARATE throwaway
# Postgres — its own container name, host port, password and NAMED volume — so a QA run can never
# touch or corrupt the dev DB or its volume. Read once at import: the calling process sets the env
# BEFORE importing, so each lane binds its own DSN. (Test-infra seam only — no logic change.)
PG_NAME = os.environ.get("THOR_PG_NAME", "thor-postgres")
PG_HOST_PORT = int(os.environ.get("THOR_PG_PORT", "55432"))
PG_PASSWORD = os.environ.get("THOR_PG_PASSWORD", "thor")
PG_DB = os.environ.get("THOR_PG_DB", "thor")
PG_VOLUME = os.environ.get("THOR_PG_VOLUME")  # None -> anonymous volume (today's behavior)
DSN = os.environ.get("THOR_PG_DSN") or f"postgresql://postgres:{PG_PASSWORD}@localhost:{PG_HOST_PORT}/{PG_DB}"


def start(client: docker.DockerClient | None = None) -> str:
    client = client or docker.from_env()
    for c in client.containers.list(all=True, filters={"name": PG_NAME}):
        c.remove(force=True)
    kwargs = dict(
        name=PG_NAME, detach=True,
        environment={"POSTGRES_PASSWORD": PG_PASSWORD, "POSTGRES_DB": PG_DB},
        ports={"5432/tcp": PG_HOST_PORT},
        labels={"thor.manager": "postgres"},
    )
    if PG_VOLUME:  # QA lane: pin a dedicated NAMED volume so QA data lives on its own disk, not dev's
        kwargs["volumes"] = {PG_VOLUME: {"bind": "/var/lib/postgresql/data", "mode": "rw"}}
        kwargs["labels"] = {"thor.manager": "postgres", "thor.qa": "1"}
    client.containers.run("postgres:16-alpine", **kwargs)
    wait_ready()
    return DSN


def wait_ready(tries: int = 40) -> None:
    import psycopg

    for _ in range(tries):
        try:
            with psycopg.connect(DSN, connect_timeout=2) as c:
                c.execute("SELECT 1")
            return
        except Exception:  # noqa: BLE001 - retry until the server is accepting connections
            time.sleep(1)
    raise RuntimeError("postgres did not become ready in time")


def stop(client: docker.DockerClient | None = None) -> None:
    client = client or docker.from_env()
    for c in client.containers.list(all=True, filters={"name": PG_NAME}):
        c.remove(force=True)
