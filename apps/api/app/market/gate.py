import asyncio
from datetime import datetime, timezone

import httpx

from app.market.models import (
    Candle,
    DataCapability,
    MarketInstrument,
    MarketType,
    Timeframe,
)
from app.market.provider import MarketDataError, MarketDataProvider

MAX_LIMIT = 1000

_INSTRUMENTS = [
    MarketInstrument(MarketType.CRYPTO, "BTC/USDT", "BTC_USDT"),
    MarketInstrument(MarketType.CRYPTO, "ETH/USDT", "ETH_USDT"),
    MarketInstrument(MarketType.CRYPTO, "SOL/USDT", "SOL_USDT"),
]


class GateProvider(MarketDataProvider):
    """Public spot candles from Gate.io (no API key needed)."""

    name = "gate"
    capabilities = frozenset({DataCapability.HISTORICAL_CANDLES})

    def __init__(
        self,
        base_url: str = "https://api.gateio.ws/api/v4",
        client: httpx.AsyncClient | None = None,
        retries: int = 2,
        retry_delay: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=20.0)
        )
        self._retries = retries
        self._retry_delay = retry_delay

    def instruments(self) -> list[MarketInstrument]:
        return list(_INSTRUMENTS)

    def timeframes(self) -> list[Timeframe]:
        return list(Timeframe)

    async def get_candles(
        self,
        instrument: MarketInstrument,
        timeframe: Timeframe,
        limit: int = 200,
    ) -> list[Candle]:
        if not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        response = await self._get(
            "/spot/candlesticks",
            {
                "currency_pair": instrument.provider_symbol,
                "interval": timeframe.value,
                "limit": limit,
            },
        )
        if response.status_code != 200:
            raise MarketDataError(
                f"Gate.io returned HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            rows = response.json()
        except ValueError as exc:
            raise MarketDataError("Gate.io returned invalid JSON") from exc
        if not isinstance(rows, list):
            raise MarketDataError(f"Gate.io returned an unexpected response: {rows!r}")
        candles = [self._parse_row(row) for row in rows]
        return sorted(candles, key=lambda candle: candle.timestamp)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict) -> httpx.Response:
        attempts = self._retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return await self._client.get(f"{self._base_url}{path}", params=params)
            except httpx.TransportError as exc:
                if attempt == attempts:
                    raise MarketDataError(
                        f"Gate.io is unreachable ({exc.__class__.__name__}) "
                        f"after {attempts} attempts"
                    ) from exc
                await asyncio.sleep(self._retry_delay * attempt)
            except httpx.HTTPError as exc:
                raise MarketDataError(
                    f"Gate.io request failed ({exc.__class__.__name__})"
                ) from exc
        raise MarketDataError("Gate.io request failed")

    @staticmethod
    def _parse_row(row: object) -> Candle:
        # Gate.io row: [time_s, quote_volume, close, high, low, open, base_volume, closed]
        try:
            return Candle(
                timestamp=datetime.fromtimestamp(int(row[0]), tz=timezone.utc),
                open=float(row[5]),
                high=float(row[3]),
                low=float(row[4]),
                close=float(row[2]),
                volume=float(row[6]),
                closed=str(row[7]).lower() == "true",
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                f"Gate.io returned a malformed candle: {row!r}"
            ) from exc
