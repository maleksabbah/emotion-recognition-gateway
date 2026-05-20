"""
Redis connection factory.

main.py calls get_redis() during lifespan, stores the result on
app.state.redis. dependencies.py reads it from there per request.
"""
from __future__ import annotations

import redis.asyncio as redis

from app.Config.Config import REDIS_URL


def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=False)