from app.market.cache import CandleCache
from app.market.models import Candle, MarketInstrument, Timeframe
from app.market.provider import MarketDataProvider
from app.market.registry import get_provider

MAX_CANDLES = 1000
LIMIT_BUCKETS = (50, 100, 200, 500, 1000)

CACHE_TTL_SECONDS: dict[Timeframe, float] = {
    Timeframe.M1: 15,
    Timeframe.M5: 30,
    Timeframe.M15: 60,
    Timeframe.H1: 120,
    Timeframe.H4: 300,
    Timeframe.D1: 600,
}


class UnknownInstrumentError(Exception):
    """The requested symbol is not offered by the active provider."""


def _bucket_for(limit: int) -> int:
    # One extra candle so closed_only still returns `limit` candles.
    wanted = min(limit + 1, LIMIT_BUCKETS[-1])
    return next(bucket for bucket in LIMIT_BUCKETS if bucket >= wanted)


class MarketService:
    def __init__(self, provider: MarketDataProvider, cache: CandleCache) -> None:
        self._provider = provider
        self._cache = cache

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def instruments(self) -> list[MarketInstrument]:
        return self._provider.instruments()

    def timeframes(self) -> list[Timeframe]:
        return self._provider.timeframes()

    def find_instrument(self, symbol: str) -> MarketInstrument:
        for instrument in self._provider.instruments():
            if instrument.symbol == symbol:
                return instrument
        raise UnknownInstrumentError(symbol)

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200,
        closed_only: bool = False,
    ) -> list[Candle]:
        if not 1 <= limit <= MAX_CANDLES:
            raise ValueError(f"limit must be between 1 and {MAX_CANDLES}")
        instrument = self.find_instrument(symbol)
        if timeframe not in self._provider.timeframes():
            raise ValueError(
                f"{self._provider.name} does not support timeframe {timeframe.value}"
            )
        bucket = _bucket_for(limit)
        key = (self._provider.name, instrument.symbol, timeframe.value, bucket)
        candles = await self._cache.get_or_fetch(
            key,
            CACHE_TTL_SECONDS[timeframe],
            lambda: self._provider.get_candles(instrument, timeframe, bucket),
        )
        if closed_only:
            candles = [candle for candle in candles if candle.closed]
        return candles[-limit:]


_cache = CandleCache()


def get_market_service() -> MarketService:
    return MarketService(get_provider(), _cache)
