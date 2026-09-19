from pydantic import BaseModel

from app.market.models import Candle


class InstrumentOut(BaseModel):
    symbol: str
    market: str


class InstrumentsOut(BaseModel):
    provider: str
    instruments: list[InstrumentOut]
    timeframes: list[str]


class CandleOut(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool

    @classmethod
    def from_candle(cls, candle: Candle) -> "CandleOut":
        return cls(
            time=int(candle.timestamp.timestamp()),
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            closed=candle.closed,
        )


class CandlesOut(BaseModel):
    provider: str
    symbol: str
    timeframe: str
    candles: list[CandleOut]
