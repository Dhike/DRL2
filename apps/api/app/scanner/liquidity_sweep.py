from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.confirmation import detect_pattern_confirmation
from app.scanner.structure import (
    BreakOfStructure,
    ChangeOfCharacter,
    ExternalStructure,
    StructureScope,
    SwingPoint,
    SwingType,
    detect_bos,
    detect_choch_after_protection,
)


@dataclass(frozen=True)
class LiquidityLevel:
    side: str
    price: float
    swing_index: int
    scope: StructureScope = StructureScope.UNDEFINED


def detect_liquidity_levels(
    candles: list[Candle],
    swings: tuple[SwingPoint, ...],
    scope: StructureScope | None = None,
) -> tuple[LiquidityLevel, ...]:
    """Detect buy-side and sell-side liquidity from confirmed swing points.

    When `scope` is given, only swings with that structure scope are used.
    """
    levels: list[LiquidityLevel] = []

    for swing in swings:
        if swing.index >= len(candles):
            continue

        if scope is not None and swing.scope != scope:
            continue

        if swing.swing_type == SwingType.HIGH:
            levels.append(
                LiquidityLevel(
                    side="buy_side",
                    price=swing.price,
                    swing_index=swing.index,
                    scope=swing.scope,
                )
            )

        elif swing.swing_type == SwingType.LOW:
            levels.append(
                LiquidityLevel(
                    side="sell_side",
                    price=swing.price,
                    swing_index=swing.index,
                    scope=swing.scope,
                )
            )

    return tuple(levels)


@dataclass(frozen=True)
class LiquiditySweep:
    side: str
    liquidity_price: float
    candle_index: int
    candle: Candle
    swing_index: int
    scope: StructureScope = StructureScope.UNDEFINED


def detect_liquidity_sweeps(
    candles: list[Candle],
    liquidity_levels: tuple[LiquidityLevel, ...],
) -> tuple[LiquiditySweep, ...]:
    """Detect the first sweep of each identified liquidity level."""
    sweeps: list[LiquiditySweep] = []
    consumed_levels: set[tuple[str, int]] = set()

    for candle_index, candle in enumerate(candles):
        for level in liquidity_levels:
            level_key = (level.side, level.swing_index)

            if level_key in consumed_levels:
                continue

            if candle_index <= level.swing_index:
                continue

            if level.side == "buy_side" and candle.high > level.price:
                sweeps.append(
                    LiquiditySweep(
                        side="buy_side",
                        liquidity_price=level.price,
                        candle_index=candle_index,
                        candle=candle,
                        swing_index=level.swing_index,
                        scope=level.scope,
                    )
                )
                consumed_levels.add(level_key)

            elif level.side == "sell_side" and candle.low < level.price:
                sweeps.append(
                    LiquiditySweep(
                        side="sell_side",
                        liquidity_price=level.price,
                        candle_index=candle_index,
                        candle=candle,
                        swing_index=level.swing_index,
                        scope=level.scope,
                    )
                )
                consumed_levels.add(level_key)

    return tuple(sweeps)


def detect_post_choch_bos(
    candles: list[Candle],
    swings: list[SwingPoint],
    choch: ChangeOfCharacter,
) -> BreakOfStructure | None:
    """Detect the first BOS confirming the CHoCH direction."""

    bos_events = detect_bos(candles, swings)

    for bos in bos_events:
        if bos.candle_index <= choch.candle_index:
            continue

        if bos.direction != choch.direction:
            continue

        return bos

    return None


@dataclass(frozen=True)
class LiquidityReturn:
    side: str
    liquidity_price: float
    sweep_index: int
    return_index: int
    candle: Candle
    sweep: LiquiditySweep
    scope: StructureScope = StructureScope.UNDEFINED


def detect_liquidity_returns(
    candles: list[Candle],
    sweeps: tuple[LiquiditySweep, ...],
) -> tuple[LiquidityReturn, ...]:
    """Detect price returning to a liquidity level after a sweep."""
    returns: list[LiquidityReturn] = []

    for sweep in sweeps:
        for candle_index in range(sweep.candle_index + 1, len(candles)):
            candle = candles[candle_index]

            if sweep.side == "buy_side":
                if candle.low <= sweep.liquidity_price:
                    returns.append(
                        LiquidityReturn(
                            side="buy_side",
                            liquidity_price=sweep.liquidity_price,
                            sweep_index=sweep.candle_index,
                            return_index=candle_index,
                            candle=candle,
                            sweep=sweep,
                            scope=sweep.scope,
                        )
                    )
                    break

            elif sweep.side == "sell_side":
                if candle.high >= sweep.liquidity_price:
                    returns.append(
                        LiquidityReturn(
                            side="sell_side",
                            liquidity_price=sweep.liquidity_price,
                            sweep_index=sweep.candle_index,
                            return_index=candle_index,
                            candle=candle,
                            sweep=sweep,
                            scope=sweep.scope,
                        )
                    )
                    break

    return tuple(returns)


@dataclass(frozen=True)
class LiquiditySweepSignal:
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    swept_level: float
    confirmation_pattern: str
    reason: str
    structure_scope: StructureScope = StructureScope.UNDEFINED


def detect_liquidity_sweep_signal(
    candles: list[Candle],
    swings: list[SwingPoint],
    external: ExternalStructure,
    scope: StructureScope | None = None,
) -> LiquiditySweepSignal | None:
    """
    Run the full Liquidity Sweep lifecycle through to confirmation.

    Sequence: a liquidity level is swept, price returns to it, a change of
    character confirms the reversal, a same-direction break of structure
    follows, and the shared candlestick library confirms it.

    entry = confirmation close, stop = beyond the swept candle's extreme
    (its high for a buy-side sweep, its low for a sell-side sweep), no
    take profit. Confirmation is checked starting on the BOS candle itself.
    """
    choch = detect_choch_after_protection(candles, external)

    if choch is None:
        return None

    expected_side = "buy_side" if choch.direction == "bearish" else "sell_side"

    levels = detect_liquidity_levels(candles, tuple(swings), scope)
    sweeps = detect_liquidity_sweeps(candles, levels)
    returns = detect_liquidity_returns(candles, sweeps)

    matching_return = None
    for candidate in returns:
        if candidate.side != expected_side:
            continue
        if candidate.return_index >= choch.candle_index:
            continue
        matching_return = candidate

    if matching_return is None:
        return None

    bos = detect_post_choch_bos(candles, swings, choch)

    if bos is None:
        return None

    confirmation = detect_pattern_confirmation(
        candles, bos.direction, bos.broken_level, bos.candle_index
    )

    if confirmation is None:
        return None

    sweep = matching_return.sweep
    stop_loss = sweep.candle.high if sweep.side == "buy_side" else sweep.candle.low

    return LiquiditySweepSignal(
        direction=bos.direction,
        entry_price=confirmation.candle.close,
        stop_loss=stop_loss,
        take_profit=None,
        swept_level=sweep.liquidity_price,
        confirmation_pattern=confirmation.pattern,
        reason=(
            f"{sweep.side} liquidity at {sweep.liquidity_price} swept, price "
            f"returned, change of character confirmed, structure broke "
            f"{bos.direction}, and {confirmation.pattern} confirmed continuation."
        ),
        structure_scope=sweep.scope,
    )
