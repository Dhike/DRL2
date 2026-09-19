from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.main import app
from app.market.cache import CandleCache
from app.market.models import (
    Candle,
    DataCapability,
    MarketInstrument,
    MarketType,
    Timeframe,
)
from app.market.provider import MarketDataError, MarketDataProvider
from app.market.service import MarketService
from app.models import User
from app.routers.market import get_service

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeProvider(MarketDataProvider):
    name = "fake"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(self):
        self.calls = []
        self.fail = False

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
            raise MarketDataError("provider down: secret detail")
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


def candles_params(**overrides):
    params = {"symbol": "BTC/USDT", "timeframe": "1h", "limit": 5}
    params.update(overrides)
    return params


def test_instruments(api):
    client, _ = api
    response = client.get("/market/instruments")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fake"
    assert [i["symbol"] for i in body["instruments"]] == ["BTC/USDT", "ETH/USDT"]
    assert body["instruments"][0]["market"] == "crypto"
    assert body["timeframes"] == ["1h", "1d"]


def test_candles_shape_and_order(api):
    client, _ = api
    response = client.get("/market/candles", params=candles_params())
    assert response.status_code == 200
    body = response.json()
    assert (body["provider"], body["symbol"], body["timeframe"]) == (
        "fake",
        "BTC/USDT",
        "1h",
    )
    candles = body["candles"]
    assert len(candles) == 5
    assert set(candles[0]) == {"time", "open", "high", "low", "close", "volume", "closed"}
    assert candles[0]["time"] == int((BASE + timedelta(hours=45)).timestamp())
    times = [c["time"] for c in candles]
    assert times == sorted(times)
    assert candles[-1]["closed"] is False


def test_closed_only(api):
    client, _ = api
    response = client.get("/market/candles", params=candles_params(closed_only="true"))
    candles = response.json()["candles"]
    assert len(candles) == 5
    assert all(c["closed"] for c in candles)


def test_repeated_requests_hit_the_cache(api):
    client, provider = api
    client.get("/market/candles", params=candles_params())
    client.get("/market/candles", params=candles_params())
    assert len(provider.calls) == 1


def test_unknown_symbol_is_404(api):
    client, _ = api
    response = client.get("/market/candles", params=candles_params(symbol="DOGE/USDT"))
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown instrument"


def test_unsupported_timeframe_is_422(api):
    client, _ = api
    response = client.get("/market/candles", params=candles_params(timeframe="1m"))
    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        candles_params(limit=0),
        candles_params(limit=1001),
        candles_params(timeframe="2h"),
        {"timeframe": "1h"},
    ],
)
def test_bad_parameters_are_422(api, params):
    client, _ = api
    assert client.get("/market/candles", params=params).status_code == 422


def test_provider_failure_is_502_without_leaking_details(api):
    client, provider = api
    provider.fail = True
    response = client.get("/market/candles", params=candles_params())
    assert response.status_code == 502
    assert response.json()["detail"] == "Market data is temporarily unavailable"
    assert "secret" not in response.text


def test_login_is_required():
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/market/instruments").status_code == 401
        assert client.get("/market/candles", params=candles_params()).status_code == 401
