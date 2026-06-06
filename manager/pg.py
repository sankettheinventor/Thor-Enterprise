"""
Postgres container lifecycle for the THOR Manager's [ThorDB] + [EventLog].

Bootstrap convenience: stand up a local postgres:16-alpine on a high host port (so it never
collides with a system Postgres). In production this is an external managed Postgres; only the
DSN changes.
"""
from __future__ import annotations

import time

import docker

PG_NAME = "thor-postgres"
PG_HOST_PORT = 55432
DSN = f"postgresql://postgres:thor@localhost:{PG_HOST_PORT}/thor"


def start(client: docker.DockerClient | None = None) -> str:
    client = client or docker.from_env()
    for c in client.containers.list(all=True, filters={"name": PG_NAME}):
        c.remove(force=True)
    client.containers.run(
        "postgres:16-alpine", name=PG_NAME, detach=True,
        environment={"POSTGRES_PASSWORD": "thor", "POSTGRES_DB": "thor"},
        ports={"5432/tcp": PG_HOST_PORT},
        labels={"thor.manager": "postgres"},
    )
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
