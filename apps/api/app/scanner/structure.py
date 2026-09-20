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


@dataclass(frozen=True)
class BreakOfStructure:
    direction: str
    broken_level: float
    candle_index: int
    candle_timestamp: object


def detect_choch(
    candles: list[Candle],
    external: ExternalStructure,
) -> ChangeOfCharacter | None:
    """Detect a change of character by closing through the protected external level."""

    if not candles:
        return None

    if external.direction == MarketState.UPTREND:
        protected_low = external.protected_low

        if protected_low is None:
            return None

        for candle_index, candle in enumerate(candles):
            if candle.close < protected_low.price:
                return ChangeOfCharacter(
                    direction="bearish",
                    broken_level=protected_low.price,
                    candle_index=candle_index,
                    candle_timestamp=candle.timestamp,
                    previous_direction=MarketState.UPTREND,
                )

    elif external.direction == MarketState.DOWNTREND:
        protected_high = external.protected_high

        if protected_high is None:
            return None

        for candle_index, candle in enumerate(candles):
            if candle.close > protected_high.price:
                return ChangeOfCharacter(
                    direction="bullish",
                    broken_level=protected_high.price,
                    candle_index=candle_index,
                    candle_timestamp=candle.timestamp,
                    previous_direction=MarketState.DOWNTREND,
                )

    return None


def detect_bos(
    candles: list[Candle],
    swings: list[SwingPoint],
) -> list[BreakOfStructure]:
    bos_events: list[BreakOfStructure] = []

    confirmed_swings = [
        swing
        for swing in swings
        if swing.label is not None
    ]

    if not confirmed_swings:
        return bos_events

    available_swings: list[SwingPoint] = []

    last_bos_direction: str | None = None
    waiting_for_new_structure = False

    consumed_levels: set[int] = set()

    for candle_index, candle in enumerate(candles):

        known_indices = {
            swing.index
            for swing in available_swings
        }

        newly_available = [
            swing
            for swing in confirmed_swings
            if (
                swing.index < candle_index
                and swing.index not in known_indices
            )
        ]

        available_swings.extend(newly_available)

        if not available_swings:
            continue

        if waiting_for_new_structure:

            if last_bos_direction == "bullish":
                has_new_low = any(
                    swing.swing_type == SwingType.LOW
                    and bos_events
                    and swing.index > bos_events[-1].candle_index
                    and swing.index < candle_index
                    for swing in available_swings
                )

                if has_new_low:
                    waiting_for_new_structure = False

            elif last_bos_direction == "bearish":
                has_new_high = any(
                    swing.swing_type == SwingType.HIGH
                    and bos_events
                    and swing.index > bos_events[-1].candle_index
                    and swing.index < candle_index
                    for swing in available_swings
                )

                if has_new_high:
                    waiting_for_new_structure = False

            if waiting_for_new_structure:
                continue

        latest_highs = [
            swing
            for swing in available_swings
            if (
                swing.swing_type == SwingType.HIGH
                and swing.index < candle_index
                and swing.index not in consumed_levels
            )
        ]

        latest_lows = [
            swing
            for swing in available_swings
            if (
                swing.swing_type == SwingType.LOW
                and swing.index < candle_index
                and swing.index not in consumed_levels
            )
        ]

        latest_high = (
            max(latest_highs, key=lambda swing: swing.index)
            if latest_highs
            else None
        )

        latest_low = (
            max(latest_lows, key=lambda swing: swing.index)
            if latest_lows
            else None
        )

        if (
            latest_high is not None
            and last_bos_direction != "bullish"
            and candle.close > latest_high.price
        ):
            bos_events.append(
                BreakOfStructure(
                    direction="bullish",
                    broken_level=latest_high.price,
                    candle_index=candle_index,
                    candle_timestamp=candle.timestamp,
                )
            )

            consumed_levels.add(latest_high.index)
            last_bos_direction = "bullish"
            waiting_for_new_structure = True

            continue

        if (
            latest_low is not None
            and last_bos_direction != "bearish"
            and candle.close < latest_low.price
        ):
            bos_events.append(
                BreakOfStructure(
                    direction="bearish",
                    broken_level=latest_low.price,
                    candle_index=candle_index,
                    candle_timestamp=candle.timestamp,
                )
            )

            consumed_levels.add(latest_low.index)
            last_bos_direction = "bearish"
            waiting_for_new_structure = True

            continue

    return bos_events


def find_external_structure(
    swings: list[SwingPoint],
    bos_events: list[BreakOfStructure],
    market_state: MarketState,
) -> ExternalStructure:
    """Find the current external structural anchors."""

    if not swings or not bos_events:
        return ExternalStructure(
            direction=market_state,
            protected_high=None,
            protected_low=None,
            external_high=None,
            external_low=None,
        )

    latest_bos = bos_events[-1]

    if latest_bos.direction == "bullish":
        broken_high = next(
            (
                swing
                for swing in reversed(swings)
                if (
                    swing.swing_type == SwingType.HIGH
                    and swing.price == latest_bos.broken_level
                )
            ),
            None,
        )

        protected_low = next(
            (
                swing
                for swing in reversed(swings)
                if (
                    swing.swing_type == SwingType.LOW
                    and swing.index < latest_bos.candle_index
                )
            ),
            None,
        )

        return ExternalStructure(
            direction=MarketState.UPTREND,
            protected_high=None,
            protected_low=protected_low,
            external_high=broken_high,
            external_low=None,
        )

    if latest_bos.direction == "bearish":
        broken_low = next(
            (
                swing
                for swing in reversed(swings)
                if (
                    swing.swing_type == SwingType.LOW
                    and swing.price == latest_bos.broken_level
                )
            ),
            None,
        )

        protected_high = next(
            (
                swing
                for swing in reversed(swings)
                if (
                    swing.swing_type == SwingType.HIGH
                    and swing.index < latest_bos.candle_index
                )
            ),
            None,
        )

        return ExternalStructure(
            direction=MarketState.DOWNTREND,
            protected_high=protected_high,
            protected_low=None,
            external_high=None,
            external_low=broken_low,
        )

    return ExternalStructure(
        direction=market_state,
        protected_high=None,
        protected_low=None,
        external_high=None,
        external_low=None,
    )


def should_promote_to_external(
    swing: SwingPoint,
    external: ExternalStructure,
) -> bool:
    """Determine whether a confirmed swing should become a new external anchor."""
    if external.direction == MarketState.UPTREND:
        if (
            swing.swing_type == SwingType.HIGH
            and external.external_high is not None
        ):
            return swing.price > external.external_high.price

        return False

    if external.direction == MarketState.DOWNTREND:
        if (
            swing.swing_type == SwingType.LOW
            and external.external_low is not None
        ):
            return swing.price < external.external_low.price

        return False

    return False


def classify_structure_scope(
    candles: list[Candle],
    swings: list[SwingPoint],
    bos_events: list[BreakOfStructure],
) -> tuple[SwingPoint, ...]:
    """Classify confirmed swings using the current external structure."""

    if not swings:
        return tuple()

    market_state = classify_market_state(swings)

    external = find_external_structure(
        swings,
        bos_events,
        market_state,
    )

    scopes: dict[int, StructureScope] = {
        swing.index: StructureScope.UNDEFINED
        for swing in swings
    }

    external_indices = {
        swing.index
        for swing in (
            external.protected_high,
            external.protected_low,
            external.external_high,
            external.external_low,
        )
        if swing is not None
    }

    for index in external_indices:
        scopes[index] = StructureScope.EXTERNAL

    if not bos_events:
        return tuple(
            SwingPoint(
                index=swing.index,
                timestamp=swing.timestamp,
                price=swing.price,
                swing_type=swing.swing_type,
                label=swing.label,
                scope=scopes[swing.index],
            )
            for swing in swings
        )

    latest_bos = bos_events[-1]

    if latest_bos.direction == "bullish":
        current_external_high = external.external_high
        candidate_low: SwingPoint | None = None

        for swing in swings:
            if swing.index <= latest_bos.candle_index:
                continue

            if swing.swing_type == SwingType.LOW:
                candidate_low = swing
                scopes[swing.index] = StructureScope.INTERNAL

            elif swing.swing_type == SwingType.HIGH:
                if (
                    current_external_high is not None
                    and swing.price > current_external_high.price
                ):
                    scopes[swing.index] = StructureScope.EXTERNAL

                    if candidate_low is not None:
                        scopes[candidate_low.index] = StructureScope.EXTERNAL

                    current_external_high = swing
                    candidate_low = None
                else:
                    scopes[swing.index] = StructureScope.INTERNAL

    elif latest_bos.direction == "bearish":
        current_external_low = external.external_low
        candidate_high: SwingPoint | None = None

        for swing in swings:
            if swing.index <= latest_bos.candle_index:
                continue

            if swing.swing_type == SwingType.HIGH:
                candidate_high = swing
                scopes[swing.index] = StructureScope.INTERNAL

            elif swing.swing_type == SwingType.LOW:
                if (
                    current_external_low is not None
                    and swing.price < current_external_low.price
                ):
                    scopes[swing.index] = StructureScope.EXTERNAL

                    if candidate_high is not None:
                        scopes[candidate_high.index] = StructureScope.EXTERNAL

                    current_external_low = swing
                    candidate_high = None
                else:
                    scopes[swing.index] = StructureScope.INTERNAL

    return tuple(
        SwingPoint(
            index=swing.index,
            timestamp=swing.timestamp,
            price=swing.price,
            swing_type=swing.swing_type,
            label=swing.label,
            scope=scopes[swing.index],
        )
        for swing in swings
    )
