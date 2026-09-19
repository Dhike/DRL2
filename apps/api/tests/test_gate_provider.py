import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.market.gate import GateProvider
from app.market.models import MarketInstrument, MarketType, Timeframe
from app.market.provider import MarketDataError

BTC = MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT")

# Real rows returned by Gate.io for BTC_USDT 1h (oldest first).
BTC_ROWS = [
    ["1789830000", "21307605.88687440", "81637.5", "81944", "81566.7", "81577.6", "260.76008400", "true"],
    ["1789833600", "12964128.86323080", "81836", "81911.6", "81470.2", "81637.5", "158.56612500", "true"],
    ["1789837200", "101512.88692060", "81792.2", "81836.1", "81792.2", "81836.1", "1.24073700", "false"],
]


async def fetch(handler, timeframe=Timeframe.H1, limit=3, retries=2):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GateProvider(client=client, retries=retries, retry_delay=0)
        return await provider.get_candles(BTC, timeframe, limit)


def test_parses_real_gate_rows():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=BTC_ROWS)

    candles = asyncio.run(fetch(handler))

    assert seen["path"] == "/api/v4/spot/candlesticks"
    assert seen["params"] == {
        "currency_pair": "BTC_USDT",
        "interval": "1h",
        "limit": "3",
    }
    assert len(candles) == 3
    first = candles[0]
    assert first.timestamp == datetime.fromtimestamp(1789830000, tz=timezone.utc)
    assert (first.open, first.high, first.low, first.close) == (
        81577.6,
        81944.0,
        81566.7,
        81637.5,
    )
    assert first.volume == 260.760084
    assert first.closed is True
    assert candles[1].open == candles[0].close
    assert candles[2].closed is False


def test_sorts_oldest_first():
    candles = asyncio.run(
        fetch(lambda request: httpx.Response(200, json=list(reversed(BTC_ROWS))))
    )
    times = [candle.timestamp for candle in candles]
    assert times == sorted(times)
    assert len(candles) == 3


def test_http_error_becomes_market_data_error():
    with pytest.raises(MarketDataError, match="HTTP 500"):
        asyncio.run(fetch(lambda request: httpx.Response(500, text="boom")))


def test_unexpected_response_shape_becomes_market_data_error():
    body = {"label": "INVALID_CURRENCY_PAIR", "message": "bad pair"}
    with pytest.raises(MarketDataError, match="unexpected response"):
        asyncio.run(fetch(lambda request: httpx.Response(200, json=body)))


@pytest.mark.parametrize(
    "bad_row",
    [
        ["1789830000", "1", "81637.5"],
        ["1789830000", "1", "81637.5", "81000", "81566.7", "81577.6", "1", "true"],
    ],
)
def test_bad_rows_are_rejected(bad_row):
    with pytest.raises(MarketDataError, match="malformed"):
        asyncio.run(fetch(lambda request: httpx.Response(200, json=[bad_row])))


def test_network_failure_becomes_market_data_error():
    def handler(request):
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(MarketDataError, match="unreachable"):
        asyncio.run(fetch(handler))


def test_retries_transient_network_errors():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise httpx.ConnectTimeout("slow network")
        return httpx.Response(200, json=BTC_ROWS)

    candles = asyncio.run(fetch(handler))
    assert calls["count"] == 3
    assert len(candles) == 3


def test_gives_up_after_all_attempts():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        raise httpx.ConnectTimeout("blocked")

    with pytest.raises(MarketDataError, match="after 3 attempts"):
        asyncio.run(fetch(handler))
    assert calls["count"] == 3


@pytest.mark.parametrize("limit", [0, 1001])
def test_limit_bounds(limit):
    with pytest.raises(ValueError):
        asyncio.run(
            fetch(lambda request: httpx.Response(200, json=BTC_ROWS), limit=limit)
        )


def test_catalog():
    provider = GateProvider()
    assert [i.symbol for i in provider.instruments()] == [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
    ]
    assert [i.provider_symbol for i in provider.instruments()] == [
        "BTC_USDT",
        "ETH_USDT",
        "SOL_USDT",
    ]
    assert provider.timeframes() == list(Timeframe)
