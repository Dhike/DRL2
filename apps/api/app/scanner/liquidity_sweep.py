from dataclasses import dataclass

from app.market.models import Candle
from app.scanner.structure import (
    BreakOfStructure,
    ChangeOfCharacter,
    StructureScope,
    SwingPoint,
    SwingType,
    detect_bos,
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
