"""
RedisRepository — Redis access for the gateway.

Gateway only uses Redis for rate limiting. Live-mode frame state lives in
the orchestrator (the WebSocket is proxied through to it via nginx), so
there is no live-session state here.
"""
from __future__ import annotations

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

    # ══════════════════════════════════════════
    # S3 key validation
    # ══════════════════════════════════════════

    _S3_KEY_PREFIX = "s3key"   # s3key:{session_id}
    _S3_KEY_TTL = 3600          # 1 hour

    async def store_expected_s3_key(self, session_id: str, s3_key: str) -> None:
        """Store the expected s3_key for a session (1hr TTL)."""
        key = f"{self._S3_KEY_PREFIX}:{session_id}"
        await self.r.set(key, s3_key, ex=self._S3_KEY_TTL)

    async def get_expected_s3_key(self, session_id: str) -> str | None:
        """Retrieve the expected s3_key for a session, or None if expired/missing."""
        key = f"{self._S3_KEY_PREFIX}:{session_id}"
        val = await self.r.get(key)
        if val is None:
            return None
        return val.decode() if isinstance(val, bytes) else val