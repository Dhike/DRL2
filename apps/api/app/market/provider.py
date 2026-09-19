from abc import ABC, abstractmethod
from typing import ClassVar

from app.market.models import Candle, DataCapability, MarketInstrument, Timeframe


class MarketDataError(Exception):
    """A provider could not return the requested data."""


class MarketDataProvider(ABC):
    name: ClassVar[str]
    capabilities: ClassVar[frozenset[DataCapability]]

    @abstractmethod
    def instruments(self) -> list[MarketInstrument]:
        """The instruments this provider can serve."""

    @abstractmethod
    def timeframes(self) -> list[Timeframe]:
        """The timeframes this provider can serve."""

    @abstractmethod
    async def get_candles(
        self,
        instrument: MarketInstrument,
        timeframe: Timeframe,
        limit: int = 200,
    ) -> list[Candle]:
        """Return up to `limit` candles, oldest first."""

    async def aclose(self) -> None:
        """Release network resources. Providers holding none can keep this."""
