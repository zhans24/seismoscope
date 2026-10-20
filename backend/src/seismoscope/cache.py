from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, TypeVar

from redis.asyncio import Redis
from redis.exceptions import RedisError

from seismoscope.settings import settings

logger = logging.getLogger(__name__)

CacheStatus = Literal["HIT", "MISS", "STALE", "BYPASS"]
T = TypeVar("T")
_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


async def close_cache() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def cache_key(namespace: str, parameters: Mapping[str, Any]) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"seismoscope:{namespace}:v1:{digest}"


async def cached_json(
    namespace: str,
    parameters: Mapping[str, Any],
    fetch: Callable[[], Awaitable[T]],
    *,
    fresh_ttl: int,
    stale_ttl: int,
    stale_if: tuple[type[Exception], ...],
) -> tuple[T, CacheStatus]:
    """Return shared cached JSON and retain an older copy for upstream outages."""
    client = get_redis()
    key = cache_key(namespace, parameters)
    stale_key = f"{key}:stale"
    lock_key = f"{key}:lock"

    try:
        cached = await client.get(key)
    except RedisError as error:
        logger.warning("Redis unavailable; bypassing cache: %s", error)
        return await fetch(), "BYPASS"

    if cached is not None:
        return json.loads(cached), "HIT"

    token = uuid.uuid4().hex
    try:
        owns_lock = bool(await client.set(lock_key, token, ex=settings.cache_lock_seconds, nx=True))
    except RedisError as error:
        logger.warning("Redis lock unavailable; bypassing cache: %s", error)
        return await fetch(), "BYPASS"

    if not owns_lock:
        for _ in range(10):
            await asyncio.sleep(0.1)
            try:
                cached = await client.get(key)
            except RedisError:
                break
            if cached is not None:
                return json.loads(cached), "HIT"

    try:
        try:
            value = await fetch()
        except stale_if:
            try:
                stale = await client.get(stale_key)
            except RedisError:
                stale = None
            if stale is not None:
                logger.warning("Serving stale %s cache after upstream failure", namespace)
                return json.loads(stale), "STALE"
            raise

        payload = json.dumps(value, separators=(",", ":"), default=str)
        try:
            async with client.pipeline(transaction=False) as pipeline:
                pipeline.set(key, payload, ex=fresh_ttl)
                pipeline.set(stale_key, payload, ex=stale_ttl)
                await pipeline.execute()
        except RedisError as error:
            logger.warning("Could not write %s cache: %s", namespace, error)
        return value, "MISS"
    finally:
        if owns_lock:
            try:
                await client.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                    1,
                    lock_key,
                    token,
                )
            except RedisError:
                pass
