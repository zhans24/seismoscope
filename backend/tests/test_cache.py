import unittest
from unittest.mock import patch

from redis.exceptions import RedisError

from seismoscope.cache import cache_key, cached_json


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.operations = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def set(self, key, value, **_kwargs):
        self.operations.append((key, value))
        return self

    async def execute(self):
        for key, value in self.operations:
            self.client.values[key] = value


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, *, nx=False, **_kwargs):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def pipeline(self, **_kwargs):
        return FakePipeline(self)

    async def eval(self, _script, _key_count, key, token):
        if self.values.get(key) == token:
            self.values.pop(key, None)
            return 1
        return 0


class UnavailableRedis(FakeRedis):
    async def get(self, _key):
        raise RedisError("offline")


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_request_is_a_cache_hit(self):
        client = FakeRedis()
        calls = 0

        async def fetch():
            nonlocal calls
            calls += 1
            return {"items": [1]}

        with patch("seismoscope.cache.get_redis", return_value=client):
            first, first_status = await cached_json("events", {"limit": 10}, fetch, fresh_ttl=60, stale_ttl=120, stale_if=(RuntimeError,))
            second, second_status = await cached_json("events", {"limit": 10}, fetch, fresh_ttl=60, stale_ttl=120, stale_if=(RuntimeError,))

        self.assertEqual(first, second)
        self.assertEqual((first_status, second_status), ("MISS", "HIT"))
        self.assertEqual(calls, 1)

    async def test_stale_value_is_used_after_upstream_failure(self):
        client = FakeRedis()
        parameters = {"limit": 10}

        async def fetch():
            return {"items": [1]}

        with patch("seismoscope.cache.get_redis", return_value=client):
            await cached_json("events", parameters, fetch, fresh_ttl=60, stale_ttl=120, stale_if=(RuntimeError,))
            client.values.pop(cache_key("events", parameters))

            async def failing_fetch():
                raise RuntimeError("upstream unavailable")

            value, status = await cached_json("events", parameters, failing_fetch, fresh_ttl=60, stale_ttl=120, stale_if=(RuntimeError,))

        self.assertEqual(value, {"items": [1]})
        self.assertEqual(status, "STALE")

    async def test_redis_failure_bypasses_cache(self):
        async def fetch():
            return {"items": [1]}

        with patch("seismoscope.cache.get_redis", return_value=UnavailableRedis()):
            value, status = await cached_json("events", {}, fetch, fresh_ttl=60, stale_ttl=120, stale_if=(RuntimeError,))

        self.assertEqual(value, {"items": [1]})
        self.assertEqual(status, "BYPASS")


if __name__ == "__main__":
    unittest.main()
