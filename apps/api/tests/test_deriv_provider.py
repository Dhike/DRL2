import asyncio
import json

import pytest

from app.market.deriv import DerivProvider
from app.market.models import MarketInstrument, MarketType, Timeframe
from app.market.provider import MarketDataError

# 07:30:30 UTC on 2026-10-15 (the moment the real diagnostic ran).
NOW = 1792049430.0
AUDCAD = MarketInstrument(MarketType.FOREX, "AUD/CAD", "frxAUDCAD")


class FakeWS:
    def __init__(self, replies):
        self.sent = []
        self.closed = False
        self._replies = list(replies)

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def recv(self):
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply)

    async def close(self):
        self.closed = True


class HangingWS(FakeWS):
    async def recv(self):
        await asyncio.sleep(10)


def make(*sockets, retries=2, request_timeout=5.0):
    queue = list(sockets)
    calls = {"n": 0}

    async def connect(url):
        calls["n"] += 1
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    provider = DerivProvider(
        connect=connect,
        retries=retries,
        retry_delay=0,
        request_timeout=request_timeout,
        clock=lambda: NOW,
    )
    return provider, calls


def row(epoch, o, h, l, c):
    return {"epoch": epoch, "open": o, "high": h, "low": l, "close": c}


def candles_reply(rows):
    return {"msg_type": "candles", "candles": rows}


def run(coro):
    return asyncio.run(coro)


def test_instruments_empty_before_refresh():
    provider, _ = make()
    assert provider.instruments() == []


def test_refresh_maps_markets_and_symbols():
    rows = [
        {"market": "synthetic_index", "underlying_symbol": "1HZ100V",
         "underlying_symbol_name": "Volatility 100 (1s) Index"},
        {"market": "forex", "underlying_symbol": "frxAUDCAD"},
        {"market": "commodities", "underlying_symbol": "frxXAUUSD"},
        {"market": "cryptocurrency", "underlying_symbol": "cryBTCUSD"},
        {"market": "indices", "underlying_symbol": "OTC_DJI"},
        {"market": "something_new", "underlying_symbol": "XYZ"},
        {"market": "forex"},
    ]
    ws = FakeWS([{"msg_type": "active_symbols", "active_symbols": rows}])
    provider, _ = make(ws)

    count = run(provider.refresh_instruments())

    assert count == 5
    assert ws.sent == [{"active_symbols": "brief"}]
    assert [(i.market, i.symbol, i.provider_symbol) for i in provider.instruments()] == [
        (MarketType.SYNTHETIC, "1HZ100V", "1HZ100V"),
        (MarketType.FOREX, "AUD/CAD", "frxAUDCAD"),
        (MarketType.COMMODITIES, "XAU/USD", "frxXAUUSD"),
        (MarketType.CRYPTO, "BTC/USD", "cryBTCUSD"),
        (MarketType.INDICES, "OTC_DJI", "OTC_DJI"),
    ]


def test_refresh_empty_keeps_previous_instruments():
    good = {"msg_type": "active_symbols",
            "active_symbols": [{"market": "forex", "underlying_symbol": "frxAUDCAD"}]}
    empty = {"msg_type": "active_symbols", "active_symbols": []}
    provider, _ = make(FakeWS([good, empty]))

    async def go():
        await provider.refresh_instruments()
        with pytest.raises(MarketDataError, match="no supported"):
            await provider.refresh_instruments()

    run(go())
    assert [i.symbol for i in provider.instruments()] == ["AUD/CAD"]


def test_candles_request_payload():
    ws = FakeWS([candles_reply([row(1792047600, 0.98628, 0.98638, 0.98552, 0.98615)])])
    provider, _ = make(ws)
    run(provider.get_candles(AUDCAD, Timeframe.M15, 5))
    assert ws.sent == [
        {"ticks_history": "frxAUDCAD", "style": "candles",
         "granularity": 900, "count": 5, "end": "latest"}
    ]


def test_candles_sorted_and_forming_candle_marked_open():
    rows = [
        row(1792047600, 0.98628, 0.98638, 0.98552, 0.98615),  # 07:00, forming
        row(1792040400, 0.98700, 0.98720, 0.98650, 0.98680),  # 05:00
        row(1792044000, 0.98680, 0.98700, 0.98600, 0.98628),  # 06:00
    ]
    provider, _ = make(FakeWS([candles_reply(rows)]))
    candles = run(provider.get_candles(AUDCAD, Timeframe.H1, 3))
    assert [int(c.timestamp.timestamp()) for c in candles] == [
        1792040400, 1792044000, 1792047600,
    ]
    assert [c.closed for c in candles] == [True, True, False]
    assert all(c.volume == 0.0 for c in candles)
    assert candles[-1].close == 0.98615


def test_daily_candle_forming():
    rows = [
        row(1792022400, 0.9916, 0.99194, 0.98552, 0.98616),  # today
        row(1791936000, 0.9900, 0.99300, 0.98900, 0.99160),  # yesterday
    ]
    provider, _ = make(FakeWS([candles_reply(rows)]))
    candles = run(provider.get_candles(AUDCAD, Timeframe.D1, 2))
    assert [c.closed for c in candles] == [True, False]


def test_api_error_is_not_retried():
    ws = FakeWS([{"error": {"code": "InvalidSymbol", "message": "bad symbol"}}])
    provider, calls = make(ws)
    with pytest.raises(MarketDataError, match="InvalidSymbol"):
        run(provider.get_candles(AUDCAD, Timeframe.H1, 3))
    assert calls["n"] == 1
    assert len(ws.sent) == 1


def test_retries_connection_failure_then_succeeds():
    good = FakeWS([candles_reply([row(1792040400, 0.987, 0.9872, 0.9865, 0.9868)])])
    provider, calls = make(OSError("down"), good)
    candles = run(provider.get_candles(AUDCAD, Timeframe.H1, 1))
    assert len(candles) == 1
    assert calls["n"] == 2


def test_all_attempts_fail():
    provider, calls = make(OSError("a"), OSError("b"), OSError("c"))
    with pytest.raises(MarketDataError, match="unreachable"):
        run(provider.get_candles(AUDCAD, Timeframe.H1, 1))
    assert calls["n"] == 3


def test_reconnects_after_dropped_socket():
    bad = FakeWS([OSError("reset")])
    good = FakeWS([candles_reply([row(1792040400, 0.987, 0.9872, 0.9865, 0.9868)])])
    provider, calls = make(bad, good)
    candles = run(provider.get_candles(AUDCAD, Timeframe.H1, 1))
    assert len(candles) == 1
    assert bad.closed is True
    assert calls["n"] == 2


def test_connection_is_reused():
    reply = candles_reply([row(1792040400, 0.987, 0.9872, 0.9865, 0.9868)])
    ws = FakeWS([reply, reply])
    provider, calls = make(ws)

    async def go():
        await provider.get_candles(AUDCAD, Timeframe.H1, 1)
        await provider.get_candles(AUDCAD, Timeframe.H4, 1)

    run(go())
    assert calls["n"] == 1
    assert len(ws.sent) == 2


@pytest.mark.parametrize(
    "bad_row",
    [
        {"epoch": 1792040400, "open": 1, "high": 2, "low": 0.5},
        row(1792040400, 1.0, 0.5, 0.9, 0.95),
    ],
)
def test_malformed_candle_raises(bad_row):
    provider, _ = make(FakeWS([candles_reply([bad_row])]))
    with pytest.raises(MarketDataError, match="malformed candle"):
        run(provider.get_candles(AUDCAD, Timeframe.H1, 1))


def test_ignores_unrelated_messages():
    good = candles_reply([row(1792040400, 0.987, 0.9872, 0.9865, 0.9868)])
    provider, _ = make(FakeWS([{"msg_type": "ping", "ping": "pong"}, good]))
    assert len(run(provider.get_candles(AUDCAD, Timeframe.H1, 1))) == 1


def test_missing_candles_key_raises():
    provider, _ = make(FakeWS([{"msg_type": "candles"}]))
    with pytest.raises(MarketDataError, match="malformed"):
        run(provider.get_candles(AUDCAD, Timeframe.H1, 1))


def test_request_timeout():
    provider, _ = make(HangingWS([]), retries=0, request_timeout=0.01)
    with pytest.raises(MarketDataError, match="unreachable"):
        run(provider.get_candles(AUDCAD, Timeframe.H1, 1))


def test_timeframes_are_pinned():
    provider, _ = make()
    assert provider.timeframes() == [
        Timeframe.M1, Timeframe.M2, Timeframe.M5, Timeframe.M15, Timeframe.M30,
        Timeframe.H1, Timeframe.H2, Timeframe.H4, Timeframe.D1,
    ]


def test_limit_validation():
    provider, _ = make()
    for bad in (0, 1001):
        with pytest.raises(ValueError):
            run(provider.get_candles(AUDCAD, Timeframe.H1, bad))


def test_aclose_closes_socket():
    ws = FakeWS([candles_reply([row(1792040400, 0.987, 0.9872, 0.9865, 0.9868)])])
    provider, _ = make(ws)

    async def go():
        await provider.get_candles(AUDCAD, Timeframe.H1, 1)
        await provider.aclose()

    run(go())
    assert ws.closed is True
