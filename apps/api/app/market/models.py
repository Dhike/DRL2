from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    INDICES = "indices"
    SYNTHETIC = "synthetic"


class DataCapability(str, Enum):
    LIVE_PRICE = "live_price"
    HISTORICAL_CANDLES = "historical_candles"
    LIVE_CANDLES = "live_candles"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return _TIMEFRAME_SECONDS[self]


_TIMEFRAME_SECONDS: dict[Timeframe, int] = {
    Timeframe.M1: 60,
    Timeframe.M5: 5 * 60,
    Timeframe.M15: 15 * 60,
    Timeframe.H1: 60 * 60,
    Timeframe.H4: 4 * 60 * 60,
    Timeframe.D1: 24 * 60 * 60,
}


@dataclass(frozen=True, slots=True)
class MarketInstrument:
    market: MarketType
    symbol: str
    provider_symbol: str


@dataclass(frozen=True, slots=True)
class Candle:
    """One price bar. `timestamp` is the bar's open time, timezone-aware (UTC).

    `closed` is False while the bar is still forming. Strategies that work on
    closes must only use closed candles.
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Candle timestamp must be timezone-aware (UTC)")
        if (
            self.low > min(self.open, self.close)
            or self.high < max(self.open, self.close)
            or self.low > self.high
        ):
            raise ValueError(
                "Candle prices are inconsistent: low <= open/close <= high is required"
            )
        if self.volume < 0:
            raise ValueError("Candle volume cannot be negative")
