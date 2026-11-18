"""
RedisRepository — Redis access for the gateway.

Gateway uses Redis for rate limiting, the pending-upload entry written at
presign and checked at complete, and a short per-user lock around upload
completion. Live-mode frame state lives in the orchestrator (the browser
opens its WebSocket there directly), so there is no live-session state here.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis


_RATE_LIMIT_PREFIX = "rate"   # rate:{ip}:{path}


class RedisRepository:
    def __init__(self, conn: redis.Redis):
        self.r = conn

    # ══════════════════════════════════════════
    # Rate limiting
    # ══════════════════════════════════════════

    async def incr_with_expiry(self, key: str, window_seconds: int) -> int:
        """
        Atomically INCR a counter and (re)set its TTL.
        Returns the new count.
        """
        pipe = self.r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        return int(results[0])

    @staticmethod
    def rate_key(ip: str, path: str) -> str:
        return f"{_RATE_LIMIT_PREFIX}:{ip}:{path}"

    @staticmethod
    def upload_rate_key(user_id: str, hour_bucket: int) -> str:
        """Per-user upload counter for one fixed hourly window."""
        return f"{_RATE_LIMIT_PREFIX}:upload:{user_id}:{hour_bucket}"

    # ══════════════════════════════════════════
    # Pending upload entry (presign → complete)
    # ══════════════════════════════════════════
    #
    # Written at presign with the server-side facts complete must trust:
    # {s3_key, user_id, kind, size}. Complete refuses to run without it.

    _UPLOAD_PREFIX = "upload"   # upload:{session_id} → JSON
    _UPLOAD_TTL = 3600          # 1 hour

    async def store_upload_entry(self, session_id: str, entry: dict[str, Any]) -> None:
        key = f"{self._UPLOAD_PREFIX}:{session_id}"
        await self.r.set(key, json.dumps(entry), ex=self._UPLOAD_TTL)

    async def get_upload_entry(self, session_id: str) -> Optional[dict[str, Any]]:
        """The entry, or None if expired/missing/unreadable."""
        key = f"{self._UPLOAD_PREFIX}:{session_id}"
        val = await self.r.get(key)
        if val is None:
            return None
        try:
            data = json.loads(val.decode() if isinstance(val, bytes) else val)
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    async def delete_upload_entry(self, session_id: str) -> None:
        await self.r.delete(f"{self._UPLOAD_PREFIX}:{session_id}")

    # ══════════════════════════════════════════
    # Short-lived per-user lock
    # ══════════════════════════════════════════
    #
    # SET NX with a random token; release / shorten only if we still own it,
    # so a lock that expired and was re-taken by another request is untouched.

    _LOCK_PREFIX = "lock"   # lock:{name}

    _RELEASE_LUA = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    _SHORTEN_LUA = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('pexpire', KEYS[1], ARGV[2]) else return 0 end"
    )

    async def acquire_lock(self, name: str, token: str, ttl_seconds: int) -> bool:
        key = f"{self._LOCK_PREFIX}:{name}"
        return bool(await self.r.set(key, token, nx=True, ex=ttl_seconds))

    async def release_lock(self, name: str, token: str) -> None:
        key = f"{self._LOCK_PREFIX}:{name}"
        await self.r.eval(self._RELEASE_LUA, 1, key, token)

    async def shorten_lock(self, name: str, token: str, ttl_ms: int) -> None:
        key = f"{self._LOCK_PREFIX}:{name}"
        await self.r.eval(self._SHORTEN_LUA, 1, key, token, ttl_ms)