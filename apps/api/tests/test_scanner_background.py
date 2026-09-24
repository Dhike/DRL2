import asyncio
from datetime import datetime, timedelta, timezone

from app.market.cache import CandleCache
from app.market.models import Candle, DataCapability, MarketInstrument, MarketType, Timeframe
from app.market.provider import MarketDataProvider
from app.market.service import MarketService
from app.scanner.background import ScannerLoop
from app.scanner.live_scanner import LiveScanner
from app.scanner.models import ScannerStrategy

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeProvider(MarketDataProvider):
    name = "fake"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(self, candles):
        self.candles = candles
        self.calls = 0

    def instruments(self):
        return [MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT")]

    def timeframes(self):
        return [Timeframe.H1]

    async def get_candles(self, instrument, timeframe, limit=200):
        self.calls += 1
        return self.candles


def make_candles(n, start=0):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=start + i),
            open=100.0 + i, high=101.0 + i, low=99.0 + i, close=100.5 + i,
            volume=1.0, closed=True,
        )
        for i in range(n)
    ]


def make_loop_with_provider(provider: FakeProvider, scanner: LiveScanner) -> ScannerLoop:
    loop = ScannerLoop(
        symbols=["BTC/USDT"], timeframe="1h",
        strategies=["trend_continuation"], poll_seconds=60,
    )
    # Route through a real MarketService pointed at the fake provider,
    # same shape production code uses, without touching the module-level
    # provider registry.
    service = MarketService(provider, CandleCache())
    loop._get_service_override = lambda: service  # not used by ScannerLoop directly
    return loop


def test_poll_once_processes_new_candles(monkeypatch):
    candles = make_candles(5)
    provider = FakeProvider(candles)
    service = MarketService(provider, CandleCache())
    monkeypatch.setattr(
        "app.scanner.background.get_market_service", lambda: service
    )

    loop = ScannerLoop(
        symbols=["BTC/USDT"], timeframe="1h",
        strategies=["trend_continuation"], poll_seconds=60,
    )

    import app.scanner.background as bg
    bg._scanner = LiveScanner()

    asyncio.run(loop._poll_once())

    tracker = bg._scanner._tracker_for("BTC/USDT", "1h")
    assert len(tracker.candles) == 5
    assert loop._last_seen["BTC/USDT"] == candles[-1].timestamp


def test_second_poll_skips_already_seen_candles(monkeypatch):
    """The exact bug an earlier manual test hit: re-fetching the same
    candles on a later poll must NOT re-add them to the tracker."""
    candles = make_candles(5)
    provider = FakeProvider(candles)
    service = MarketService(provider, CandleCache())
    monkeypatch.setattr(
        "app.scanner.background.get_market_service", lambda: service
    )

    loop = ScannerLoop(
        symbols=["BTC/USDT"], timeframe="1h",
        strategies=["trend_continuation"], poll_seconds=60,
    )
    import app.scanner.background as bg
    bg._scanner = LiveScanner()

    asyncio.run(loop._poll_once())
    asyncio.run(loop._poll_once())  # same 5 candles again, nothing new

    tracker = bg._scanner._tracker_for("BTC/USDT", "1h")
    assert len(tracker.candles) == 5  # NOT 10


def test_second_poll_adds_only_genuinely_new_candles(monkeypatch):
    """
    Tested against a minimal fake service that returns whatever candle
    list it is currently given, bypassing MarketService's own cache
    (120s TTL for 1h candles) -- that cache is real, correct production
    behavior, but it would make this specific test's two immediate,
    real-time-adjacent polls return a stale cached answer regardless of
    what the underlying provider returns, which is not what this test
    is measuring: ScannerLoop's OWN new-candle dedup logic.
    """
    class GrowingFakeService:
        def __init__(self, candles):
            self.candles = candles

        async def get_candles(self, symbol, timeframe, limit=200, closed_only=False):
            return self.candles

    fake_service = GrowingFakeService(make_candles(5))
    monkeypatch.setattr(
        "app.scanner.background.get_market_service", lambda: fake_service
    )

    loop = ScannerLoop(
        symbols=["BTC/USDT"], timeframe="1h",
        strategies=["trend_continuation"], poll_seconds=60,
    )
    import app.scanner.background as bg
    bg._scanner = LiveScanner()

    asyncio.run(loop._poll_once())

    # Service now returns 5 old candles plus 2 genuinely new ones.
    fake_service.candles = make_candles(7)
    asyncio.run(loop._poll_once())

    tracker = bg._scanner._tracker_for("BTC/USDT", "1h")
    assert len(tracker.candles) == 7


def test_one_symbol_fetch_failure_does_not_abort_the_cycle(monkeypatch):
    class FailingThenWorkingService:
        def __init__(self):
            self.calls = []

        async def get_candles(self, symbol, timeframe, limit=200, closed_only=False):
            self.calls.append(symbol)
            if symbol == "BAD/USDT":
                raise RuntimeError("simulated provider failure")
            return make_candles(3)

    fake_service = FailingThenWorkingService()
    monkeypatch.setattr(
        "app.scanner.background.get_market_service", lambda: fake_service
    )

    loop = ScannerLoop(
        symbols=["BAD/USDT", "BTC/USDT"], timeframe="1h",
        strategies=["trend_continuation"], poll_seconds=60,
    )
    import app.scanner.background as bg
    bg._scanner = LiveScanner()

    asyncio.run(loop._poll_once())  # must not raise

    assert fake_service.calls == ["BAD/USDT", "BTC/USDT"]
    tracker = bg._scanner._tracker_for("BTC/USDT", "1h")
    assert len(tracker.candles) == 3
    assert "BAD/USDT" not in loop._last_seen


def test_start_and_stop_cycle(monkeypatch):
    """start() schedules a background task; stop() cancels it cleanly."""
    provider = FakeProvider(make_candles(1))
    service = MarketService(provider, CandleCache())
    monkeypatch.setattr(
        "app.scanner.background.get_market_service", lambda: service
    )

    async def run():
        loop = ScannerLoop(
            symbols=["BTC/USDT"], timeframe="1h",
            strategies=["trend_continuation"], poll_seconds=0.01,
        )
        loop.start()
        await asyncio.sleep(0.05)
        await loop.stop()
        assert loop._task is None

    asyncio.run(run())
