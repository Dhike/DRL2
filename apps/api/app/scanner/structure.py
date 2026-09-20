from dataclasses import dataclass
from enum import StrEnum

from app.market.models import Candle


class SwingType(StrEnum):
    HIGH = "high"
    LOW = "low"


class StructureLabel(StrEnum):
    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"


class StructureScope(StrEnum):
    EXTERNAL = "external"
    INTERNAL = "internal"
    UNDEFINED = "undefined"


class MarketState(StrEnum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGING = "ranging"
    UNDEFINED = "undefined"


@dataclass(frozen=True)
class SwingPoint:
    index: int
    timestamp: object
    price: float
    swing_type: SwingType
    label: StructureLabel | None
    scope: StructureScope = StructureScope.UNDEFINED


@dataclass(frozen=True)
class MarketStructure:
    state: MarketState
    swings: tuple[SwingPoint, ...]


@dataclass(frozen=True)
class ExternalStructure:
    direction: MarketState
    protected_high: SwingPoint | None
    protected_low: SwingPoint | None
    external_high: SwingPoint | None
    external_low: SwingPoint | None


@dataclass(frozen=True)
class ChangeOfCharacter:
    direction: str
    broken_level: float
    candle_index: int
    candle_timestamp: object
    previous_direction: MarketState


def detect_confirmed_swings(
    candles: list[Candle],
    left_bars: int = 2,
    right_bars: int = 2,
) -> list[SwingPoint]:
    swings: list[SwingPoint] = []

    minimum_candles = left_bars + right_bars + 1

    if len(candles) < minimum_candles:
        return swings

    for index in range(
        left_bars,
        len(candles) - right_bars,
    ):
        candle = candles[index]

        left = candles[index - left_bars:index]
        right = candles[index + 1:index + right_bars + 1]

        surrounding = [*left, *right]

        is_swing_high = all(
            candle.high > other.high
            for other in surrounding
        )

        is_swing_low = all(
            candle.low < other.low
            for other in surrounding
        )

        if is_swing_high:
            swings.append(
                SwingPoint(
                    index=index,
                    timestamp=candle.timestamp,
                    price=candle.high,
                    swing_type=SwingType.HIGH,
                    label=None,
                )
            )

        if is_swing_low:
            swings.append(
                SwingPoint(
                    index=index,
                    timestamp=candle.timestamp,
                    price=candle.low,
                    swing_type=SwingType.LOW,
                    label=None,
                )
            )

    return swings


def classify_swings(
    swings: list[SwingPoint],
) -> list[SwingPoint]:
    classified: list[SwingPoint] = []

    previous_high: float | None = None
    previous_low: float | None = None

    for swing in swings:
        label: StructureLabel

        if swing.swing_type == SwingType.HIGH:
            if previous_high is None:
                label = StructureLabel.HH
            elif swing.price > previous_high:
                label = StructureLabel.HH
            else:
                label = StructureLabel.LH

            previous_high = swing.price

        else:
            if previous_low is None:
                label = StructureLabel.HL
            elif swing.price > previous_low:
                label = StructureLabel.HL
            else:
                label = StructureLabel.LL

            previous_low = swing.price

        classified.append(
            SwingPoint(
                index=swing.index,
                timestamp=swing.timestamp,
                price=swing.price,
                swing_type=swing.swing_type,
                label=label,
            )
        )

    return classified


def classify_market_state(
    swings: list[SwingPoint],
) -> MarketState:

    classified = [
        swing
        for swing in swings
        if swing.label is not None
    ]

    if len(classified) < 4:
        return MarketState.UNDEFINED

    recent = classified[-6:]

    bullish_score = sum(
        1
        for swing in recent
        if swing.label in (
            StructureLabel.HH,
            StructureLabel.HL,
        )
    )

    bearish_score = sum(
        1
        for swing in recent
        if swing.label in (
            StructureLabel.LH,
            StructureLabel.LL,
        )
    )

    if (
        bullish_score >= 3
        and bullish_score > bearish_score
    ):
        return MarketState.UPTREND

    if (
        bearish_score >= 3
        and bearish_score > bullish_score
    ):
        return MarketState.DOWNTREND

    return MarketState.RANGING


def analyze_market_structure(
    candles: list[Candle],
) -> MarketStructure:

    swings = detect_confirmed_swings(candles)

    classified = classify_swings(swings)

    state = classify_market_state(classified)

    return MarketStructure(
        state=state,
        swings=tuple(classified),
    )
