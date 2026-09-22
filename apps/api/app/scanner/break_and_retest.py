from dataclasses import dataclass
from enum import StrEnum

from app.market.models import Candle
from app.scanner.confirmation import detect_pattern_confirmation
from app.scanner.structure import (
    BreakOfStructure,
    StructureScope,
    SwingPoint,
    SwingType,
)


class BreakAndRetestState(StrEnum):
    WAITING_FOR_BREAK = "waiting_for_break"
    WAITING_FOR_BULLISH_RETEST = "waiting_for_bullish_retest"
    WAITING_FOR_BEARISH_RETEST = "waiting_for_bearish_retest"
    WAITING_FOR_BULLISH_CONFIRMATION = "waiting_for_bullish_confirmation"
    WAITING_FOR_BEARISH_CONFIRMATION = "waiting_for_bearish_confirmation"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class BreakAndRetestRetest:
    direction: str
    break_level: float
    break_index: int
    retest_index: int
    candle: Candle
    bos: BreakOfStructure
    structure_scope: StructureScope


@dataclass(frozen=True)
class BreakAndRetestSetup:
    direction: str
    break_level: float
    break_index: int
    break_timestamp: object
    retest_index: int
    retest_timestamp: object
    structure_scope: StructureScope
    bos: BreakOfStructure
    retest: BreakAndRetestRetest


@dataclass(frozen=True)
class BreakAndRetestSignal:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    break_level: float
    confirmation_pattern: str
    reason: str
    structure_scope: StructureScope = StructureScope.UNDEFINED


@dataclass(frozen=True)
class BreakAndRetestResult:
    state: BreakAndRetestState
    setup: BreakAndRetestSetup | None
    signal: BreakAndRetestSignal | None = None


def _find_broken_structure(
    swings: list[SwingPoint],
    bos: BreakOfStructure,
) -> SwingPoint | None:
    candidates = [
        swing
        for swing in swings
        if swing.label is not None
        and swing.index < bos.candle_index
        and swing.price == bos.broken_level
        and (
            (
                bos.direction == "bullish"
                and swing.swing_type == SwingType.HIGH
            )
            or (
                bos.direction == "bearish"
                and swing.swing_type == SwingType.LOW
            )
        )
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda swing: swing.index)


def _detect_bullish_retest(
    candles: list[Candle],
    bos: BreakOfStructure,
    structure_scope: StructureScope,
) -> BreakAndRetestRetest | None:
    for candle_index in range(bos.candle_index + 1, len(candles)):
        candle = candles[candle_index]

        if candle.low > bos.broken_level:
            continue

        if candle.close < bos.broken_level:
            continue

        return BreakAndRetestRetest(
            direction="bullish",
            break_level=bos.broken_level,
            break_index=bos.candle_index,
            retest_index=candle_index,
            candle=candle,
            bos=bos,
            structure_scope=structure_scope,
        )

    return None


def _detect_bearish_retest(
    candles: list[Candle],
    bos: BreakOfStructure,
    structure_scope: StructureScope,
) -> BreakAndRetestRetest | None:
    for candle_index in range(bos.candle_index + 1, len(candles)):
        candle = candles[candle_index]

        if candle.high < bos.broken_level:
            continue

        if candle.close > bos.broken_level:
            continue

        return BreakAndRetestRetest(
            direction="bearish",
            break_level=bos.broken_level,
            break_index=bos.candle_index,
            retest_index=candle_index,
            candle=candle,
            bos=bos,
            structure_scope=structure_scope,
        )

    return None


def detect_retest(
    candles: list[Candle],
    bos: BreakOfStructure,
    structure_scope: StructureScope,
) -> BreakAndRetestRetest | None:
    """Detect the first post-BOS retest that respects the broken level."""
    if not candles:
        return None

    if bos.candle_index < 0 or bos.candle_index >= len(candles):
        return None

    if bos.direction == "bullish":
        return _detect_bullish_retest(
            candles,
            bos,
            structure_scope,
        )

    if bos.direction == "bearish":
        return _detect_bearish_retest(
            candles,
            bos,
            structure_scope,
        )

    return None


def _candidate_bos_events(
    swings: list[SwingPoint],
    bos_events: list[BreakOfStructure],
) -> list[tuple[BreakOfStructure, SwingPoint]]:
    candidates: list[tuple[BreakOfStructure, SwingPoint]] = []

    for bos in bos_events:
        broken_structure = _find_broken_structure(swings, bos)

        if broken_structure is None:
            continue

        candidates.append((bos, broken_structure))

    return candidates


def detect_break_and_retest(
    candles: list[Candle],
    swings: list[SwingPoint],
    bos_events: list[BreakOfStructure],
) -> BreakAndRetestResult:
    """
    Detect the independent Break & Retest lifecycle.

    Sequence:
        confirmed structure
        -> valid BOS
        -> broken structural level
        -> structure scope
        -> retest
        -> retest validation
        -> confirmation state

    Confirmation-pattern detection is handled by the later
    shared confirmation step.

    This engine does not require:
        - market trend state
        - a strong BOS candle
        - liquidity sweep
        - Trend Continuation
        - a mandatory POI
    """
    if not candles or not swings or not bos_events:
        return BreakAndRetestResult(
            state=BreakAndRetestState.WAITING_FOR_BREAK,
            setup=None,
        )

    candidates = _candidate_bos_events(
        swings,
        bos_events,
    )

    if not candidates:
        return BreakAndRetestResult(
            state=BreakAndRetestState.WAITING_FOR_BREAK,
            setup=None,
        )

    for bos, broken_structure in reversed(candidates):
        retest = detect_retest(
            candles=candles,
            bos=bos,
            structure_scope=broken_structure.scope,
        )

        if retest is None:
            continue

        if bos.direction == "bullish":
            state = BreakAndRetestState.WAITING_FOR_BULLISH_CONFIRMATION
        else:
            state = BreakAndRetestState.WAITING_FOR_BEARISH_CONFIRMATION

        setup = BreakAndRetestSetup(
            direction=bos.direction,
            break_level=bos.broken_level,
            break_index=bos.candle_index,
            break_timestamp=bos.candle_timestamp,
            retest_index=retest.retest_index,
            retest_timestamp=retest.candle.timestamp,
            structure_scope=broken_structure.scope,
            bos=bos,
            retest=retest,
        )

        return BreakAndRetestResult(
            state=state,
            setup=setup,
        )

    latest_bos, _ = candidates[-1]

    if latest_bos.direction == "bullish":
        state = BreakAndRetestState.WAITING_FOR_BULLISH_RETEST
    else:
        state = BreakAndRetestState.WAITING_FOR_BEARISH_RETEST

    return BreakAndRetestResult(
        state=state,
        setup=None,
    )


def detect_break_and_retest_signal(
    candles: list[Candle],
    swings: list[SwingPoint],
    bos_events: list[BreakOfStructure],
) -> BreakAndRetestResult:
    """
    Run the independent Break & Retest lifecycle through to confirmation.

    Adds the shared candlestick confirmation step after a valid retest:
    entry = confirmation close, stop = the lowest low (bullish) or highest
    high (bearish) of the retest and confirmation candles, no take profit.
    """
    result = detect_break_and_retest(candles, swings, bos_events)

    if result.setup is None:
        return result

    if result.state not in (
        BreakAndRetestState.WAITING_FOR_BULLISH_CONFIRMATION,
        BreakAndRetestState.WAITING_FOR_BEARISH_CONFIRMATION,
    ):
        return result

    setup = result.setup
    confirmation = detect_pattern_confirmation(
        candles,
        setup.direction,
        setup.break_level,
        setup.retest_index + 1,
    )

    if confirmation is None:
        return result

    retest_candle = setup.retest.candle

    if setup.direction == "bullish":
        stop_loss = min(retest_candle.low, confirmation.candle.low)
    else:
        stop_loss = max(retest_candle.high, confirmation.candle.high)

    signal = BreakAndRetestSignal(
        direction=setup.direction,
        entry_price=confirmation.candle.close,
        stop_loss=stop_loss,
        take_profit=None,
        break_level=setup.break_level,
        confirmation_pattern=confirmation.pattern,
        reason=(
            f"Independent break confirmed, level {setup.break_level} "
            f"retested, and {confirmation.pattern} confirmed the retest."
        ),
        structure_scope=setup.structure_scope,
    )

    return BreakAndRetestResult(
        state=BreakAndRetestState.CONFIRMED,
        setup=setup,
        signal=signal,
    )
