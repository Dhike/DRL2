import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.market.models import (
    Candle,
    DataCapability,
    MarketInstrument,
    MarketType,
    Timeframe,
)
from app.market.provider import MarketDataProvider

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_candle(**overrides):
    values = dict(
        timestamp=T0, open=100.0, high=110.0, low=95.0, close=105.0, volume=12.5
    )
    values.update(overrides)
    return Candle(**values)


def test_timeframe_lengths():
    assert {tf.value: tf.seconds for tf in Timeframe} == {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }


def test_market_types():
    assert {m.value for m in MarketType} == {
        "forex",
        "crypto",
        "stocks",
        "indices",
        "synthetic",
    }


def test_valid_candle_keeps_values():
    candle = make_candle()
    assert (candle.open, candle.high, candle.low, candle.close) == (
        100.0,
        110.0,
        95.0,
        105.0,
    )
    assert candle.volume == 12.5
    assert candle.timestamp == T0


def test_candle_is_immutable():
    candle = make_candle()
    with pytest.raises(FrozenInstanceError):
        candle.close = 1.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"high": 90.0},
        {"low": 106.0},
        {"volume": -1.0},
        {"timestamp": datetime(2026, 1, 1)},
    ],
)
def test_invalid_candles_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_candle(**overrides)


def test_provider_interface_is_abstract():
    with pytest.raises(TypeError):
        MarketDataProvider()


class FakeProvider(MarketDataProvider):
    name = "fake"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def instruments(self):
        return [MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT")]

    def timeframes(self):
        return [Timeframe.H1]

    async def get_candles(self, instrument, timeframe, limit=200):
        return [make_candle()]


def test_minimal_provider_works():
    provider = FakeProvider()
    instrument = provider.instruments()[0]
    candles = asyncio.run(provider.get_candles(instrument, Timeframe.H1))
    assert candles == [make_candle()]
    asyncio.run(provider.aclose())
