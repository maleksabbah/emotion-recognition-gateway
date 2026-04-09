"""
WebSocket handler for live mode.

Flow:
  1. Frontend connects with JWT token as query param
  2. Gateway validates token, creates session via orchestrator
  3. Frontend sends video frames as binary WebSocket messages
  4. Gateway forwards frames to orchestrator via HTTP
  5. Gateway reads results from Redis stream, sends back as JSON
  6. On disconnect, tells orchestrator to end session + queue burn
"""
from __future__ import annotations

import asyncio
import uuid
import base64
import json
import logging
from typing import Optional

import httpx
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect

from app.Auth import decode_token, get_user_by_id
from app.Config import ORCHESTRATOR_URL, STREAM_LIVE_PREFIX, WS_MAX_FRAME_SIZE

logger = logging.getLogger(__name__)


class LiveSessionManager:
    """Manages a single WebSocket live session."""

    def __init__(self, websocket: WebSocket, redis_conn: redis.Redis, user_id: str):
        self.ws = websocket
        self.redis = redis_conn
        self.user_id = user_id
        self.session_id: Optional[str] = None
        self.frame_number: int = 0
        self._stream_task: Optional[asyncio.Task] = None
        self._running: bool = False
    async def start(self) -> None:
        """Create session via orchestrator and start streaming."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/sessions",
                json={"mode":"live","metadata":{"user_id":self.user_id}},

            )
            if resp.status_code != 200:
                await self.ws.close(code=1011,reason="Failed to create session")

                return
            data = resp.json()
            self.session_id = data["session_id"]
        await self.ws.send_json({"type":"session_created","session_id":self.session_id})
        self._running = True
        self._stream_task = asyncio.create_task(self._stream_results())
        logger.info(f"Live session {self.session_id} started for user {self.user_id}")

    async def handle_frame(self, data: bytes) -> None:
        if not self.session_id or not self._running:
            return

        if len(data) > WS_MAX_FRAME_SIZE:
            await self.ws.send_json({"type": "error", "message": "Frame too large"})
            return

        frame_id = str(uuid.uuid4())
        cache_key = f"frame:{self.session_id}:{frame_id}"
        queue_key = f"queue:frames:{self.session_id}"

        try:
            await self.redis.set(cache_key, data, ex=10)
            await self.redis.rpush(queue_key, json.dumps({
                "session_id": self.session_id,
                "frame_id": frame_id,
                "frame_number": self.frame_number,
            }))
            self.frame_number += 1
        except Exception as e:
            logger.error(f"Frame push failed: {e}")

    async def _stream_results(self) -> None:
        """Read inference results from Redis stream and send to frontend."""
        stream_key = f"{STREAM_LIVE_PREFIX}{self.session_id}"
        last_id = "0-0"

        while self._running:
            try:
                messages = await self.redis.xread(
                    {stream_key: last_id}, count=10, block=500,
                )
                for _, stream_msgs in messages:
                    for msg_id, fields in stream_msgs:
                        try:
                            payload = json.loads(fields[b"data"])
                            await self.ws.send_json({"type": "result", "data": payload})
                            last_id = msg_id
                        except (json.JSONDecodeError, KeyError):
                            last_id = msg_id
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream read error: {e}")
                await asyncio.sleep(0.5)

    async def stop(self) -> None:
        """End session — tell orchestrator to finalize and queue burn."""
        self._running = False
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

        if self.session_id:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{ORCHESTRATOR_URL}/api/sessions/{self.session_id}/end")
                logger.info(f"Live session {self.session_id} ended")
            except Exception as e:
                logger.error(f"Failed to end session {self.session_id}: {e}")

async def websocket_live(websocket: WebSocket) -> None:
    """WebSocket endpoint handler for /ws/live."""
    # Authenticate via query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return
        user = await get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="Invalid user")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    redis_conn = websocket.app.state.redis
    session_mgr = LiveSessionManager(websocket, redis_conn, str(user.id))

    try:
        await session_mgr.start()
        if not session_mgr.session_id:
            return

        while True:
            data = await websocket.receive_bytes()
            await session_mgr.handle_frame(data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_mgr.session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        await session_mgr.stop()




