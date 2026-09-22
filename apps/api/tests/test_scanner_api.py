from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.main import app
from app.market.cache import CandleCache
from app.market.models import Candle, DataCapability, MarketInstrument, MarketType, Timeframe
from app.market.provider import MarketDataProvider
from app.market.service import MarketService
from app.models import User
from app.routers.scanner import get_service

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Same fixture used throughout the strategy tests: candle 11 is a strong
# break, candle 17 a bullish marubozu confirming the 111.0 retest.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def setup_candles():
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[11] = (112.3, 113.8, 114.0, 112.0)
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


class FakeProvider(MarketDataProvider):
    name = "fake"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(self, candles=None):
        self.candles = candles if candles is not None else setup_candles()

    def instruments(self):
        return [MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT")]

    def timeframes(self):
        return [Timeframe.H1, Timeframe.D1]

    async def get_candles(self, instrument, timeframe, limit=200):
        # Ignore limit: always return the fixed fixture (shorter than any
        # bucket size, so MarketService's slicing leaves it unchanged).
        return self.candles


@pytest.fixture
def api():
    provider = FakeProvider()
    service = MarketService(provider, CandleCache())
    app.dependency_overrides[get_current_user] = lambda: User(
        email="tester@drl2.dev", password_hash="x"
    )
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        yield client, provider
    app.dependency_overrides.clear()


def scan_body(**overrides):
    body = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "strategies": ["trend_continuation"],
    }
    body.update(overrides)
    return body


def test_scan_produces_a_real_signal(api):
    client, _ = api
    response = client.post("/scanner/scan", json=scan_body())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["signals"]) == 1
    signal = body["signals"][0]
    assert signal["strategy"] == "trend_continuation"
    assert signal["direction"] == "bullish"
    assert signal["entry_price"] == 112.4
    assert signal["stop_loss"] == 110.5
    assert signal["take_profit"] is None
    assert signal["structure_scope"] == "external"
    assert signal["symbol"] == "BTC/USDT"
    assert signal["market"] == "crypto"


def test_scan_with_a_non_matching_scope_returns_no_signals(api):
    client, _ = api
    response = client.post("/scanner/scan", json=scan_body(scope="internal"))
    assert response.status_code == 200
    assert response.json()["signals"] == []


def test_empty_strategies_is_422(api):
    client, _ = api
    response = client.post("/scanner/scan", json=scan_body(strategies=[]))
    assert response.status_code == 422


def test_unknown_symbol_is_404(api):
    client, _ = api
    response = client.post("/scanner/scan", json=scan_body(symbol="DOGE/USDT"))
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown instrument"


def test_unsupported_timeframe_is_422(api):
    client, _ = api
    response = client.post("/scanner/scan", json=scan_body(timeframe="1m"))
    assert response.status_code == 422


def test_login_is_required():
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.post("/scanner/scan", json=scan_body()).status_code == 401
