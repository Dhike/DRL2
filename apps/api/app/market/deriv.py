"""Deriv market data provider (public WebSocket, no authentication).

Uses Deriv's current public endpoint. The legacy hosts (ws.derivws.com,
ws.binaryws.com) reject connections with HTTP 520 and are not used.
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

from app.market.models import (
    Candle,
    DataCapability,
    MarketInstrument,
    MarketType,
    Timeframe,
)
from app.market.provider import MarketDataError, MarketDataProvider

logger = logging.getLogger("drl2.market.deriv")

DEFAULT_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
MAX_LIMIT = 1000

# Deriv granularity is the bar length in seconds, which equals Timeframe.seconds.
_TIMEFRAMES = [
    Timeframe.M1,
    Timeframe.M2,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
    Timeframe.H1,
    Timeframe.H2,
    Timeframe.H4,
    Timeframe.D1,
]

_MARKETS = {
    "forex": MarketType.FOREX,
    "commodities": MarketType.COMMODITIES,
    "cryptocurrency": MarketType.CRYPTO,
    "indices": MarketType.INDICES,
    "synthetic_index": MarketType.SYNTHETIC,
}


async def _default_connect(url: str) -> Any:
    return await websockets.connect(url, open_timeout=25)


def _display_symbol(raw: str) -> str:
    if raw.startswith("frx") and len(raw) == 9 and raw[3:].isalpha():
        return f"{raw[3:6]}/{raw[6:]}"
    if (
        raw.startswith("cry")
        and len(raw) > 6
        and raw[3:].isalpha()
        and raw.endswith("USD")
    ):
        return f"{raw[3:-3]}/USD"
    return raw


class DerivProvider(MarketDataProvider):
    """Public candles from Deriv's current WebSocket API (no token needed)."""

    name = "deriv"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(
        self,
        url: str = DEFAULT_URL,
        connect: Callable[[str], Awaitable[Any]] | None = None,
        retries: int = 2,
        retry_delay: float = 0.5,
        request_timeout: float = 20.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._url = url
        self._connect = connect or _default_connect
        self._retries = retries
        self._retry_delay = retry_delay
        self._request_timeout = request_timeout
        self._clock = clock
        self._ws: Any = None
        self._lock = asyncio.Lock()
        self._instruments: list[MarketInstrument] = []

    def instruments(self) -> list[MarketInstrument]:
        return list(self._instruments)

    def timeframes(self) -> list[Timeframe]:
        return list(_TIMEFRAMES)

    async def refresh_instruments(self) -> int:
        msg = await self._request({"active_symbols": "brief"}, "active_symbols")
        rows = msg.get("active_symbols")
        if not isinstance(rows, list):
            raise MarketDataError("Deriv returned malformed active_symbols")
        instruments: list[MarketInstrument] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            market = _MARKETS.get(row.get("market"))
            raw = row.get("underlying_symbol")
            if market is None or not raw or not isinstance(raw, str):
                continue
            symbol = _display_symbol(raw)
            if symbol in seen:
                symbol = raw
            if symbol in seen:
                continue
            seen.add(symbol)
            instruments.append(MarketInstrument(market, symbol, raw))
        if not instruments:
            raise MarketDataError("Deriv returned no supported instruments")
        self._instruments = instruments
        logger.info("Deriv instruments refreshed: %d", len(instruments))
        return len(instruments)

    async def get_candles(
        self,
        instrument: MarketInstrument,
        timeframe: Timeframe,
        limit: int = 200,
    ) -> list[Candle]:
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        if timeframe not in _TIMEFRAMES:
            raise ValueError(f"Deriv does not support timeframe {timeframe.value}")
        msg = await self._request(
            {
                "ticks_history": instrument.provider_symbol,
                "style": "candles",
                "granularity": timeframe.seconds,
                "count": limit,
                "end": "latest",
            },
            "candles",
        )
        rows = msg.get("candles")
        if not isinstance(rows, list):
            raise MarketDataError("Deriv returned malformed candles")
        now = self._clock()
        by_timestamp: dict[datetime, Candle] = {}
        for row in rows:
            candle = self._parse_candle(row, timeframe.seconds, now)
            by_timestamp[candle.timestamp] = candle
        return [by_timestamp[key] for key in sorted(by_timestamp)]

    async def aclose(self) -> None:
        async with self._lock:
            await self._drop_connection()

    async def _drop_connection(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                logger.debug("Deriv socket close failed", exc_info=True)

    async def _request(self, payload: dict, expect: str) -> dict:
        attempts = self._retries + 1
        last: Exception | None = None
        async with self._lock:
            for attempt in range(1, attempts + 1):
                try:
                    if self._ws is None:
                        self._ws = await self._connect(self._url)
                    await self._ws.send(json.dumps(payload))
                    return await asyncio.wait_for(
                        self._read_until(self._ws, expect), self._request_timeout
                    )
                except MarketDataError:
                    raise
                except (OSError, WebSocketException, TimeoutError) as exc:
                    last = exc
                    await self._drop_connection()
                    if attempt < attempts:
                        await asyncio.sleep(self._retry_delay * attempt)
        raise MarketDataError(
            f"Deriv is unreachable ({last.__class__.__name__}) "
            f"after {attempts} attempts"
        ) from last

    @staticmethod
    async def _read_until(ws: Any, expect: str) -> dict:
        while True:
            raw = await ws.recv()
            try:
                msg = json.loads(raw)
            except ValueError as exc:
                raise MarketDataError("Deriv returned invalid JSON") from exc
            if not isinstance(msg, dict):
                raise MarketDataError("Deriv returned an unexpected response")
            error = msg.get("error")
            if error:
                code = error.get("code", "?") if isinstance(error, dict) else "?"
                text = error.get("message", "") if isinstance(error, dict) else ""
                raise MarketDataError(f"Deriv error {code}: {str(text)[:200]}")
            if expect in msg:
                return msg
            if msg.get("msg_type") == expect:
                raise MarketDataError(f"Deriv returned a malformed {expect} response")

    @staticmethod
    def _parse_candle(row: object, seconds: int, now: float) -> Candle:
        try:
            epoch = int(row["epoch"])
            return Candle(
                timestamp=datetime.fromtimestamp(epoch, tz=timezone.utc),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=0.0,
                closed=epoch + seconds <= now,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                f"Deriv returned a malformed candle: {row!r}"
            ) from exc
