from pydantic import BaseModel

from app.market.models import Timeframe
from app.scanner.models import ScannerSignal, ScannerStatus, ScannerStrategy
from app.scanner.structure import StructureScope


class ScannerScanRequest(BaseModel):
    symbol: str
    timeframe: Timeframe
    strategies: list[ScannerStrategy]
    scope: StructureScope | None = None


class ScannerSignalOut(BaseModel):
    market: str
    symbol: str
    timeframe: str
    strategy: ScannerStrategy
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    score: float
    reason: str
    structure_scope: StructureScope

    @classmethod
    def from_signal(cls, signal: ScannerSignal) -> "ScannerSignalOut":
        return cls(
            market=signal.market,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            strategy=signal.strategy,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            score=signal.score,
            reason=signal.reason,
            structure_scope=signal.structure_scope,
        )


class ScannerScanResult(BaseModel):
    status: ScannerStatus
    signals: list[ScannerSignalOut]
