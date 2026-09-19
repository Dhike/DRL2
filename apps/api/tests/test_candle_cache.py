import asyncio

import pytest

from app.market.cache import CandleCache

KEY = ("gate", "BTC/USDT", "1h", 100)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_serves_from_cache_until_ttl_expires():
    clock = Clock()
    cache = CandleCache(clock=clock)
    calls = []

    async def fetch():
        calls.append(1)
        return []

    async def scenario():
        await cache.get_or_fetch(KEY, 60, fetch)
        clock.now = 59
        await cache.get_or_fetch(KEY, 60, fetch)
        assert len(calls) == 1
        clock.now = 61
        await cache.get_or_fetch(KEY, 60, fetch)
        assert len(calls) == 2

    asyncio.run(scenario())


def test_concurrent_misses_share_one_fetch():
    cache = CandleCache()
    calls = []

    async def fetch():
        calls.append(1)
        await asyncio.sleep(0.01)
        return []

    async def scenario():
        await asyncio.gather(*(cache.get_or_fetch(KEY, 60, fetch) for _ in range(5)))

    asyncio.run(scenario())
    assert len(calls) == 1


def test_failed_fetch_is_not_cached():
    cache = CandleCache()
    state = {"calls": 0}

    async def fetch():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("boom")
        return []

    async def scenario():
        with pytest.raises(RuntimeError):
            await cache.get_or_fetch(KEY, 60, fetch)
        await cache.get_or_fetch(KEY, 60, fetch)

    asyncio.run(scenario())
    assert state["calls"] == 2
