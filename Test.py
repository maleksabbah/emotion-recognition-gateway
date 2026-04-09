"""
Unit tests for the gateway.
Mocks Redis, PostgreSQL, and orchestrator HTTP calls.
"""
import uuid
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.Schemas import (
    HealthResponse,
    RegisterRequest,
    TokenResponse,
    UploadRequest,
)


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock()
    r.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True])
    r.pipeline.return_value = pipe
    r.xread = AsyncMock(return_value=[])
    r.close = AsyncMock()
    return r


@pytest.fixture
def fake_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.username = "testuser"
    user.hashed_password = "$2b$12$fakehash"
    user.is_active = True
    user.is_admin = False
    user.created_at = datetime.now(timezone.utc)
    user.last_login = None
    return user


@pytest.fixture
def auth_headers(fake_user):
    from app.Auth import create_access_token
    token = create_access_token(str(fake_user.id), fake_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client(mock_redis):
    from fastapi.testclient import TestClient
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        from main import app
        app.state.redis = mock_redis
        with TestClient(app) as c:
            yield c


class TestSchemas:
    def test_health_response(self):
        resp = HealthResponse()
        assert resp.service == "gateway"
        assert resp.status == "ok"

    def test_register_request_validation(self):
        req = RegisterRequest(email="test@example.com", username="testuser", password="password123")
        assert req.email == "test@example.com"
        assert req.username == "testuser"

    def test_register_short_password_fails(self):
        with pytest.raises(Exception):
            RegisterRequest(email="test@example.com", username="testuser", password="short")

    def test_register_short_username_fails(self):
        with pytest.raises(Exception):
            RegisterRequest(email="test@example.com", username="ab", password="password123")

    def test_upload_request(self):
        req = UploadRequest(filename="video.mp4", content_type="video/mp4")
        assert req.mode == "video"

    def test_token_response(self):
        resp = TokenResponse(access_token="abc", refresh_token="def", expires_in=900)
        assert resp.token_type == "bearer"


class TestAuth:
    def test_hash_and_verify_password(self):
        from app.Auth import hash_password, verify_password
        hashed = hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_create_and_decode_access_token(self):
        from app.Auth import create_access_token, decode_token
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "test@example.com")
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from app.Auth import create_refresh_token, decode_token
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_raises(self):
        from app.Auth import decode_token
        with pytest.raises(Exception):
            decode_token("invalid.token.here")

    @pytest.mark.asyncio
    @patch("app.Auth.async_session")
    async def test_create_user(self, mock_session_factory, fake_user):
        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.refresh = AsyncMock()

        from app.Auth import create_user
        user = await create_user("new@example.com", "newuser", "password123")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.Auth.async_session")
    async def test_authenticate_user_success(self, mock_session_factory, fake_user):
        from app.Auth import hash_password

        fake_user.hashed_password = hash_password("correctpassword")

        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.Auth import authenticate_user
        user = await authenticate_user("test@example.com", "correctpassword")
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    @patch("app.Auth.async_session")
    async def test_authenticate_user_wrong_password(self, mock_session_factory, fake_user):
        from app.Auth import hash_password
        fake_user.hashed_password = hash_password("correctpassword")

        mock_db = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.Auth import authenticate_user
        with pytest.raises(Exception) as exc_info:
            await authenticate_user("test@example.com", "wrongpassword")
        assert exc_info.value.status_code == 401


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_allows(self, mock_redis):
        from app.Middleware import check_rate_limit
        assert await check_rate_limit(mock_redis, "test:key", 100, 60) is True

    @pytest.mark.asyncio
    async def test_rate_limit_blocks(self, mock_redis):
        from app.Middleware import check_rate_limit
        pipe = mock_redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[101, True])
        assert await check_rate_limit(mock_redis, "test:key", 100, 60) is False


class TestAPIRoutes:
    def test_health_endpoint(self, test_client):
        response = test_client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["service"] == "gateway"
        assert response.json()["status"] == "ok"

    @patch("app.Routes.create_user")
    def test_register_endpoint(self, mock_create_user, test_client, fake_user):
        mock_create_user.return_value = fake_user
        response = test_client.post("/api/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"

    @patch("app.Routes.authenticate_user")
    def test_login_endpoint(self, mock_auth, test_client, fake_user):
        mock_auth.return_value = fake_user
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @patch("app.Auth.get_user_by_id")
    def test_me_endpoint(self, mock_get_user, test_client, fake_user, auth_headers):
        mock_get_user.return_value = fake_user
        response = test_client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    def test_me_without_auth(self, test_client):
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401

    @patch("app.Auth.get_user_by_id")
    @patch("app.Routes.httpx.AsyncClient")
    def test_upload_request_endpoint(self, mock_httpx_cls, mock_get_user, test_client, fake_user, auth_headers, mock_redis):
        mock_get_user.return_value = fake_user

        session_id = str(uuid.uuid4())
        mock_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"session_id": session_id, "mode": "video", "status": "active"}

        presign_resp = MagicMock()
        presign_resp.status_code = 200
        presign_resp.json.return_value = {"upload_url": "https://s3.example.com/upload", "s3_key": f"uploads/{session_id}/video.mp4"}

        mock_client.post = AsyncMock(side_effect=[session_resp, presign_resp])

        response = test_client.post("/api/upload/request", headers=auth_headers, json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "mode": "video",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "upload_url" in data

    @patch("app.Auth.get_user_by_id")
    @patch("app.Routes.httpx.AsyncClient")
    def test_session_status_endpoint(self, mock_httpx_cls, mock_get_user, test_client, fake_user, auth_headers):
        mock_get_user.return_value = fake_user

        mock_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {
            "session_id": "test-session",
            "status": "processing",
            "progress": 0.5,
            "total_frames": 100,
            "current_frame": 50,
        }
        mock_client.get = AsyncMock(return_value=status_resp)

        response = test_client.get("/api/sessions/test-session/status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "processing"
        assert response.json()["progress"] == 0.5

    @patch("app.Auth.get_user_by_id")
    @patch("app.Routes.httpx.AsyncClient")
    def test_session_not_found(self, mock_httpx_cls, mock_get_user, test_client, fake_user, auth_headers):
        mock_get_user.return_value = fake_user

        mock_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        not_found_resp = MagicMock()
        not_found_resp.status_code = 404
        mock_client.get = AsyncMock(return_value=not_found_resp)

        response = test_client.get("/api/sessions/nonexistent/status", headers=auth_headers)
        assert response.status_code == 404

    @patch("app.Auth.get_user_by_id")
    @patch("app.Routes.httpx.AsyncClient")
    def test_list_sessions_endpoint(self, mock_httpx_cls, mock_get_user, test_client, fake_user, auth_headers):
        mock_get_user.return_value = fake_user

        mock_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.json.return_value = [{"id": "s1", "mode": "live", "status": "complete"}]
        mock_client.get = AsyncMock(return_value=list_resp)

        response = test_client.get("/api/sessions", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestWebSocket:
    def test_websocket_no_token_rejected(self, test_client):
        with pytest.raises(Exception):
            with test_client.websocket_connect("/ws/live"):
                pass

    @patch("app.WebSocket.get_user_by_id")
    def test_websocket_invalid_token_rejected(self, mock_get_user, test_client):
        mock_get_user.return_value = None
        with pytest.raises(Exception):
            with test_client.websocket_connect("/ws/live?token=invalid.token.here"):
                pass

    @patch("app.WebSocket.httpx.AsyncClient")
    @patch("app.WebSocket.get_user_by_id")
    @patch("app.WebSocket.decode_token")
    def test_websocket_connect_and_receive_session(
        self, mock_decode, mock_get_user, mock_httpx_cls, test_client, fake_user, mock_redis
    ):
        mock_decode.return_value = {"sub": str(fake_user.id), "type": "access"}
        mock_get_user.return_value = fake_user

        session_id = str(uuid.uuid4())
        mock_client = AsyncMock()
        mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"session_id": session_id}
        mock_client.post = AsyncMock(return_value=session_resp)
        mock_redis.xread = AsyncMock(side_effect=[[], asyncio.CancelledError()])

        with test_client.websocket_connect("/ws/live?token=valid") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "session_created"
            assert msg["session_id"] == session_id
