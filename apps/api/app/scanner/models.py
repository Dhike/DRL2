from dataclasses import dataclass
from enum import StrEnum

from app.scanner.structure import StructureScope


class ScannerStrategy(StrEnum):
    LIQUIDITY_SWEEP = "liquidity_sweep"
    TREND_CONTINUATION = "trend_continuation"
    BREAK_AND_RETEST = "break_and_retest"


class ScannerStatus(StrEnum):
    WAITING = "waiting"
    SCANNING = "scanning"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ScannerRequest:
    market: str
    symbol: str
    timeframe: str
    strategies: tuple[ScannerStrategy, ...]


@dataclass(frozen=True)
class ScannerSignal:
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
    structure_scope: StructureScope = StructureScope.UNDEFINED


@dataclass(frozen=True)
class ScannerResult:
    status: ScannerStatus
    signals: tuple[ScannerSignal, ...]
