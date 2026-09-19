import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.market.cache import CandleCache
from app.market.models import (
    Candle,
    DataCapability,
    MarketInstrument,
    MarketType,
    Timeframe,
)
from app.market.provider import MarketDataError, MarketDataProvider
from app.market.service import MarketService, UnknownInstrumentError

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeProvider(MarketDataProvider):
    name = "fake"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def instruments(self):
        return [
            MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT"),
            MarketInstrument(MarketType.CRYPTO, "ETH/USDT", "ETH_USDT"),
        ]

    def timeframes(self):
        return [Timeframe.H1, Timeframe.D1]

    async def get_candles(self, instrument, timeframe, limit=200):
        self.calls.append((instrument.symbol, timeframe, limit))
        if self.fail:
            raise MarketDataError("provider down")
        return [
            Candle(
                timestamp=BASE + timedelta(hours=i),
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1.0,
                closed=(i < limit - 1),
            )
            for i in range(limit)
        ]


def make_service(fail=False):
    provider = FakeProvider(fail=fail)
    return MarketService(provider, CandleCache()), provider


def test_returns_latest_candles_oldest_first():
    service, provider = make_service()
    candles = asyncio.run(service.get_candles("BTC/USDT", Timeframe.H1, limit=5))
    assert len(candles) == 5
    times = [c.timestamp for c in candles]
    assert times == sorted(times)
    assert candles[-1].close == 100.5 + 49
    assert candles[-1].closed is False
    assert provider.calls == [("BTC/USDT", Timeframe.H1, 50)]


def test_closed_only_drops_forming_candle():
    service, _ = make_service()
    candles = asyncio.run(
        service.get_candles("BTC/USDT", Timeframe.H1, limit=5, closed_only=True)
    )
    assert len(candles) == 5
    assert all(c.closed for c in candles)
    assert candles[-1].close == 100.5 + 48


def test_nearby_limits_share_one_fetch():
    service, provider = make_service()

    async def scenario():
        first = await service.get_candles("BTC/USDT", Timeframe.H1, limit=60)
        second = await service.get_candles("BTC/USDT", Timeframe.H1, limit=90)
        return first, second

    first, second = asyncio.run(scenario())
    assert (len(first), len(second)) == (60, 90)
    assert provider.calls == [("BTC/USDT", Timeframe.H1, 100)]


def test_symbols_are_cached_separately():
    service, provider = make_service()

    async def scenario():
        await service.get_candles("BTC/USDT", Timeframe.H1, limit=5)
        await service.get_candles("ETH/USDT", Timeframe.H1, limit=5)

    asyncio.run(scenario())
    assert [call[0] for call in provider.calls] == ["BTC/USDT", "ETH/USDT"]


def test_unknown_symbol_is_rejected():
    service, provider = make_service()
    with pytest.raises(UnknownInstrumentError):
        asyncio.run(service.get_candles("DOGE/USDT", Timeframe.H1))
    assert provider.calls == []


def test_unsupported_timeframe_is_rejected():
    service, provider = make_service()
    with pytest.raises(ValueError, match="does not support"):
        asyncio.run(service.get_candles("BTC/USDT", Timeframe.M1))
    assert provider.calls == []


@pytest.mark.parametrize("limit", [0, 1001])
def test_invalid_limit_is_rejected(limit):
    service, _ = make_service()
    with pytest.raises(ValueError):
        asyncio.run(service.get_candles("BTC/USDT", Timeframe.H1, limit=limit))


def test_provider_errors_propagate_and_are_not_cached():
    service, provider = make_service(fail=True)

    async def scenario():
        with pytest.raises(MarketDataError):
            await service.get_candles("BTC/USDT", Timeframe.H1, limit=5)
        provider.fail = False
        return await service.get_candles("BTC/USDT", Timeframe.H1, limit=5)

    candles = asyncio.run(scenario())
    assert len(candles) == 5
    assert len(provider.calls) == 2
