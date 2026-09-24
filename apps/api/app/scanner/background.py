"""Background scanning loop: periodically feeds live candles from the
configured market provider into one shared LiveScanner instance.

Off by default (DRL_SCANNER_ENABLED). Each (symbol, timeframe) pair
tracks the timestamp of the last candle it fed into LiveScanner, so a
poll cycle only ever advances the tracker with genuinely NEW candles --
re-feeding an already-processed candle would corrupt the causal candle
count LiveScanner relies on (the same mistake an early manual test made
before this module existed). One symbol's fetch failure is caught and
logged per pair, never aborting the whole cycle.
"""

import asyncio
import logging

from app.config import settings
from app.market.models import Candle, Timeframe
from app.market.service import get_market_service
from app.scanner.live_scanner import LiveScanner
from app.scanner.models import ScannerStrategy

logger = logging.getLogger("drl2.scanner.background")

_STRATEGY_BY_VALUE = {s.value: s for s in ScannerStrategy}

_scanner = LiveScanner()


def get_live_scanner() -> LiveScanner:
    return _scanner


class ScannerLoop:
    def __init__(
        self,
        symbols: list[str],
        timeframe: str,
        strategies: list[str],
        poll_seconds: int,
    ) -> None:
        self._symbols = symbols
        self._timeframe = Timeframe(timeframe)
        self._strategies = [_STRATEGY_BY_VALUE[s] for s in strategies]
        self._poll_seconds = poll_seconds
        self._last_seen: dict[str, object] = {}
        self._task: asyncio.Task | None = None

    async def _poll_once(self) -> None:
        service = get_market_service()
        for symbol in self._symbols:
            try:
                candles = await service.get_candles(
                    symbol, self._timeframe, limit=200, closed_only=True
                )
            except Exception:
                logger.exception("Scanner fetch failed for %s %s", symbol, self._timeframe.value)
                continue

            last_seen = self._last_seen.get(symbol)
            new_candles = [
                c for c in candles if last_seen is None or c.timestamp > last_seen
            ]
            if not new_candles:
                continue

            for candle in new_candles:
                _scanner.process_candle(
                    symbol, self._timeframe.value, candle, self._strategies
                )
            self._last_seen[symbol] = new_candles[-1].timestamp

    async def _run(self) -> None:
        while True:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("Scanner poll cycle failed")
            await asyncio.sleep(self._poll_seconds)

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


_loop: ScannerLoop | None = None


def start_scanner_loop() -> None:
    global _loop
    if not settings.scanner_enabled:
        return
    if _loop is not None:
        return
    _loop = ScannerLoop(
        symbols=settings.scanner_symbols,
        timeframe=settings.scanner_timeframe,
        strategies=settings.scanner_strategies,
        poll_seconds=settings.scanner_poll_seconds,
    )
    _loop.start()


async def stop_scanner_loop() -> None:
    global _loop
    if _loop is not None:
        await _loop.stop()
        _loop = None
