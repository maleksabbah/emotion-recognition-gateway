"""
Gateway integration tests — single file.
Run from gateway/ root: `pytest Test.py -v`

Requires:
  pip install asgi-lifespan respx
  pytest.ini with session-scoped loops (see storage)
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio
import respx
from asgi_lifespan import LifespanManager
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


# ══════════════════════════════════════════════
# Containers
# ══════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def postgres():
    with PostgresContainer("postgres:15") as pg:
        os.environ["POSTGRES_HOST"] = pg.get_container_host_ip()
        os.environ["POSTGRES_PORT"] = str(pg.get_exposed_port(5432))
        os.environ["POSTGRES_USER"] = pg.username
        os.environ["POSTGRES_PASSWORD"] = pg.password
        os.environ["GATEWAY_DB"] = pg.dbname
        yield


@pytest.fixture(scope="session", autouse=True)
def redis_url():
    with RedisContainer() as rc:
        url = f"redis://{rc.get_container_host_ip()}:{rc.get_exposed_port(6379)}"
        os.environ["REDIS_URL"] = url
        yield url


@pytest.fixture(scope="session", autouse=True)
def downstream_env():
    os.environ["ORCHESTRATOR_URL"] = "http://fake-orchestrator:8001"
    os.environ["STORAGE_URL"] = "http://fake-storage:8002"
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
    yield


# ══════════════════════════════════════════════
# App + client (session-scoped, row reset per test)
# ══════════════════════════════════════════════

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_client(postgres, redis_url, downstream_env):
    from app.main import app
    from app.Config.Database import engine
    from app.Entities.Base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def client(app_client):
    c, engine = app_client
    from app.Entities.Base import Base
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield c


# ══════════════════════════════════════════════
# Path discovery — pull auth/upload prefixes from the live app so test
# paths don't break when main.py mounts routes with extra prefixes.
# ══════════════════════════════════════════════

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def paths(app_client):
    """Find actual paths for the endpoints we want to hit."""
    c, _ = app_client
    app = c._transport.app
    register = login = me = upload_request = None
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.endswith("/register"):
            register = path
        elif path.endswith("/login"):
            login = path
        elif path.endswith("/me"):
            me = path
        elif path.endswith("/upload/request") or path.endswith("/request"):
            if "upload" in path:
                upload_request = path
    assert register and login and me, (
        f"Could not discover all paths. routes: {[r.path for r in app.routes]}"
    )
    return {
        "register": register,
        "login": login,
        "me": me,
        "upload_request": upload_request,
    }


# ══════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_register_login_me_flow(client, paths):
    r = await client.post(paths["register"], json={
        "email": "user@test.io", "username": "user", "password": "P@ssword123",
    })
    assert r.status_code == 200

    r = await client.post(paths["login"], json={
        "email": "user@test.io", "password": "P@ssword123",
    })
    token = r.json()["access_token"]

    r = await client.get(paths["me"], headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "user@test.io"


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_register_409(client, paths):
    payload = {"email": "dup@test.io", "username": "dup", "password": "P@ss1234"}
    await client.post(paths["register"], json=payload)
    r = await client.post(paths["register"], json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_bad_login_401(client, paths):
    r = await client.post(paths["login"], json={"email": "nobody@test.io", "password": "bad"})
    assert r.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
@respx.mock
async def test_upload_request_proxies_to_storage(client, paths):
    await client.post(paths["register"], json={
        "email": "up@test.io", "username": "uploader", "password": "P@ss1234",
    })
    token = (await client.post(paths["login"], json={
        "email": "up@test.io", "password": "P@ss1234",
    })).json()["access_token"]

    respx.post("http://fake-orchestrator:8001/api/sessions").mock(
        return_value=httpx.Response(200, json={
            "session_id": "11111111-1111-1111-1111-111111111111",
            "id": "11111111-1111-1111-1111-111111111111",
            "status": "pending",
        })
    )
    # Match whatever URL the gateway actually uses (regex covers both
    # http://storage:8002 and http://fake-storage:8002)
    import re
    respx.post(re.compile(r"http://[^/]+/internal/presign/upload")).mock(
        return_value=httpx.Response(200, json={
            "file_id": "abc",
            "upload_url": "https://minio/...",
            "s3_key": "sessions/x/video.mp4",
        })
    )
    respx.post(re.compile(r"http://[^/]+/api/sessions")).mock(
        return_value=httpx.Response(200, json={
            "session_id": "11111111-1111-1111-1111-111111111111",
            "id": "11111111-1111-1111-1111-111111111111",
            "status": "pending",
        })
    )

    upload_path = paths["upload_request"] or "/upload/request"
    r = await client.post(upload_path,
        json={"filename": "v.mp4", "content_type": "video/mp4", "mode": "video"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text