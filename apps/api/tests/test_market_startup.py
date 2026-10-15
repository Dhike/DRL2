import asyncio
from datetime import datetime, timezone

from app.config import Settings
from app.market import registry
from app.market.cache import CandleCache
from app.market.deriv import DerivProvider
from app.market.models import Candle, MarketInstrument, MarketType, Timeframe
from app.market.provider import MarketDataError, MarketDataProvider
from app.market.service import MarketService

INSTRUMENT = MarketInstrument(MarketType.FOREX, "EUR/USD", "frxEURUSD")
CANDLE = Candle(
    timestamp=datetime(2026, 10, 15, 6, tzinfo=timezone.utc),
    open=1.0, high=1.1, low=0.9, close=1.05, volume=0.0,
)


class LazyProvider(MarketDataProvider):
    name = "lazy"
    capabilities = frozenset()

    def __init__(self):
        self.refreshed = 0
        self._instruments = []

    def instruments(self):
        return list(self._instruments)

    def timeframes(self):
        return [Timeframe.H1]

    async def refresh_instruments(self):
        self.refreshed += 1
        self._instruments = [INSTRUMENT]
        return 1

    async def get_candles(self, instrument, timeframe, limit=200):
        return [CANDLE]


class FailingProvider(LazyProvider):
    name = "failing"

    async def refresh_instruments(self):
        raise MarketDataError("down")


def test_config_accepts_deriv():
    assert Settings(market_provider="deriv").market_provider == "deriv"


def test_registry_builds_deriv(monkeypatch):
    monkeypatch.setattr(registry, "_providers", {})
    assert isinstance(registry.get_provider("deriv"), DerivProvider)


def test_startup_failure_is_not_fatal(monkeypatch):
    monkeypatch.setattr(registry, "_providers", {})
    monkeypatch.setitem(registry._FACTORIES, "failing", FailingProvider)
    asyncio.run(registry.startup_providers("failing"))


def test_startup_loads_instruments(monkeypatch):
    monkeypatch.setattr(registry, "_providers", {})
    monkeypatch.setitem(registry._FACTORIES, "lazy", LazyProvider)
    asyncio.run(registry.startup_providers("lazy"))
    assert registry.get_provider("lazy").instruments() == [INSTRUMENT]


def test_service_refreshes_empty_catalog_once():
    provider = LazyProvider()
    service = MarketService(provider, CandleCache())

    async def go():
        first = await service.get_candles("EUR/USD", Timeframe.H1, 1)
        second = await service.get_candles("EUR/USD", Timeframe.H1, 1)
        return first, second

    first, second = asyncio.run(go())
    assert len(first) == len(second) == 1
    assert provider.refreshed == 1
