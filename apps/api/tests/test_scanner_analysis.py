from datetime import datetime, timedelta, timezone

import pytest

from app.market.models import Candle
from app.scanner.analysis import analyze_structure, closed_candles
from app.scanner.structure import MarketState, StructureLabel, StructureScope, SwingType

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
HIGH, LOW = SwingType.HIGH, SwingType.LOW
HH, HL, LH, LL = (
    StructureLabel.HH,
    StructureLabel.HL,
    StructureLabel.LH,
    StructureLabel.LL,
)
EXT, INT = StructureScope.EXTERNAL, StructureScope.INTERNAL

# Zigzag verified in the structure tests: peaks at 4, 12, 20; troughs at 8, 16, 24.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]
DOWN_PRICES = [240.0 - price for price in UP_PRICES]


def candles_from_prices(prices):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=price,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1.0,
        )
        for i, price in enumerate(prices)
    ]


def summary(analysis):
    return [
        (s.index, s.swing_type, s.price, s.label, s.scope) for s in analysis.swings
    ]


def test_uptrend_analysis():
    analysis = analyze_structure(candles_from_prices(UP_PRICES))
    assert analysis.market_state is MarketState.UPTREND
    assert [(e.direction, e.broken_level, e.candle_index) for e in analysis.bos_events] == [
        ("bullish", 111.0, 11)
    ]
    assert summary(analysis) == [
        (4, HIGH, 111.0, HH, EXT),
        (8, LOW, 103.0, HL, EXT),
        (12, HIGH, 117.0, HH, EXT),
        (16, LOW, 107.0, HL, EXT),
        (20, HIGH, 123.0, HH, EXT),
        (24, LOW, 111.0, HL, INT),
    ]
    external = analysis.external
    assert external.direction is MarketState.UPTREND
    assert (external.external_high.index, external.protected_low.index) == (4, 8)
    assert external.protected_high is None
    assert external.external_low is None
    assert isinstance(analysis.swings, tuple)
    assert isinstance(analysis.bos_events, tuple)


def test_downtrend_analysis():
    analysis = analyze_structure(candles_from_prices(DOWN_PRICES))
    assert analysis.market_state is MarketState.DOWNTREND
    assert [(e.direction, e.broken_level, e.candle_index) for e in analysis.bos_events] == [
        ("bearish", 129.0, 11)
    ]
    assert summary(analysis) == [
        (4, LOW, 129.0, HL, EXT),
        (8, HIGH, 137.0, HH, EXT),
        (12, LOW, 123.0, LL, EXT),
        (16, HIGH, 133.0, LH, EXT),
        (20, LOW, 117.0, LL, EXT),
        (24, HIGH, 129.0, LH, INT),
    ]
    external = analysis.external
    assert external.direction is MarketState.DOWNTREND
    assert (external.external_low.index, external.protected_high.index) == (4, 8)
    assert external.protected_low is None
    assert external.external_high is None


@pytest.mark.parametrize(
    "prices",
    [pytest.param([], id="no-candles"), pytest.param([100, 101, 102], id="too-few-candles")],
)
def test_short_input_gives_an_empty_analysis(prices):
    analysis = analyze_structure(candles_from_prices(prices))
    assert analysis.market_state is MarketState.UNDEFINED
    assert analysis.swings == ()
    assert analysis.bos_events == ()
    assert analysis.external.direction is MarketState.UNDEFINED
    assert analysis.external.protected_high is None
    assert analysis.external.protected_low is None
    assert analysis.external.external_high is None
    assert analysis.external.external_low is None


def test_closed_candles_drops_the_forming_bar():
    candles = candles_from_prices([100, 101, 102])
    forming = Candle(
        timestamp=BASE + timedelta(hours=3),
        open=102.0,
        high=104.0,
        low=101.0,
        close=103.0,
        volume=1.0,
        closed=False,
    )
    result = closed_candles(candles + [forming])
    assert result == candles
    assert all(candle.closed for candle in result)
