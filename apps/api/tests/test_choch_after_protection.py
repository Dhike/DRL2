from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.structure import (
    ExternalStructure,
    MarketState,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
    detect_choch_after_protection,
)
from app.scanner.structure_tracker import StructureTracker

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXT = StructureScope.EXTERNAL


def candles_from(rows):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


# Exact fixture and real, causally-derived external structure that
# exposed the index-0 false-CHoCH bug (Step 93/94 diagnostics).
ROWS = [
    (108, 107, 109, 106), (107, 106, 108, 105), (106, 105, 107, 104),
    (105, 104, 106, 103), (104, 103, 105, 102), (103, 102, 104, 101),
    (102, 101, 103, 100), (101, 102, 103, 100.5), (102, 104, 105, 101),
    (104, 99, 104.5, 98), (99, 100.5, 101, 99), (100.5, 102, 103, 100),
    (102, 104, 105, 101.5), (104, 135, 135.5, 103.5),
]


def real_causal_external():
    candles = candles_from(ROWS)
    tracker = StructureTracker()
    analysis = None
    for candle in candles:
        analysis = tracker.add_candle(candle)
    return candles, analysis.external


def test_skips_the_false_break_that_predates_the_protected_swing():
    """
    The real bug this fixes: with real causal structure, candle 0's
    close (107) is already above the protected_high (105, confirmed
    only at candle 8) simply because candle 0 predates that swing
    entirely -- not because a real reversal happened. The wrapper must
    skip ahead to the genuine reversal at candle 13.
    """
    candles, external = real_causal_external()
    assert external.protected_high.index == 8
    assert external.protected_high.price == 105

    result = detect_choch_after_protection(candles, external)

    assert result is not None
    assert result.candle_index == 13
    assert result.broken_level == 105
    assert result.direction == "bullish"


def test_matches_plain_detect_choch_when_there_is_no_false_break():
    """When the protected level is high enough that no candle before it
    closes past it, the wrapper's result equals detect_choch's."""
    protected_high = SwingPoint(
        2, BASE + timedelta(hours=2), 130.0, SwingType.HIGH, StructureLabel.HH, EXT
    )
    external = ExternalStructure(
        direction=MarketState.DOWNTREND, protected_high=protected_high,
        protected_low=None, external_high=None, external_low=None,
    )
    candles = candles_from(ROWS)

    result = detect_choch_after_protection(candles, external)

    assert result is not None
    assert result.candle_index == 13
    assert result.broken_level == 130.0


def test_returns_none_without_a_protected_level():
    external = ExternalStructure(
        direction=MarketState.UPTREND, protected_high=None,
        protected_low=None, external_high=None, external_low=None,
    )
    candles = candles_from(ROWS)
    assert detect_choch_after_protection(candles, external) is None


def test_returns_none_with_no_candles():
    protected_high = SwingPoint(
        0, BASE, 130.0, SwingType.HIGH, StructureLabel.HH, EXT
    )
    external = ExternalStructure(
        direction=MarketState.DOWNTREND, protected_high=protected_high,
        protected_low=None, external_high=None, external_low=None,
    )
    assert detect_choch_after_protection([], external) is None


def test_returns_none_when_nothing_breaks_after_the_protection_point():
    protected_high = SwingPoint(
        2, BASE + timedelta(hours=2), 200.0, SwingType.HIGH, StructureLabel.HH, EXT
    )
    external = ExternalStructure(
        direction=MarketState.DOWNTREND, protected_high=protected_high,
        protected_low=None, external_high=None, external_low=None,
    )
    candles = candles_from(ROWS)
    assert detect_choch_after_protection(candles, external) is None
