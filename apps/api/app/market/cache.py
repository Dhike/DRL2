import asyncio
import time
from collections.abc import Awaitable, Callable

from app.market.models import Candle

CacheKey = tuple[str, str, str, int]


class CandleCache:
    """In-memory cache with a per-key TTL. Concurrent misses share one fetch."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[CacheKey, tuple[float, list[Candle]]] = {}
        self._locks: dict[CacheKey, asyncio.Lock] = {}

    def _fresh(self, key: CacheKey) -> list[Candle] | None:
        entry = self._entries.get(key)
        if entry is not None and entry[0] > self._clock():
            return entry[1]
        return None

    async def get_or_fetch(
        self,
        key: CacheKey,
        ttl_seconds: float,
        fetch: Callable[[], Awaitable[list[Candle]]],
    ) -> list[Candle]:
        cached = self._fresh(key)
        if cached is not None:
            return cached
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._fresh(key)
            if cached is not None:
                return cached
            candles = await fetch()
            self._entries[key] = (self._clock() + ttl_seconds, candles)
            return candles
