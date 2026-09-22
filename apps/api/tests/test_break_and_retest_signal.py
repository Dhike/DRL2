from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.analysis import analyze_structure
from app.scanner.break_and_retest import (
    BreakAndRetestState,
    detect_break_and_retest,
    detect_break_and_retest_signal,
)
from app.scanner.structure import StructureScope

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Zigzag verified in the structure tests: peaks at 4, 12, 20; troughs at 8, 16, 24.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]
DOWN_PRICES = [240.0 - price for price in UP_PRICES]


def candles_from(rows):
    """Each row is (open, close, high, low)."""
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(o),
            high=float(h),
            low=float(low),
            close=float(c),
            volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def plain_rows(prices):
    return [(p, p, p + 1.0, p - 1.0) for p in prices]


def bullish_confirmed_candles():
    """Break & Retest doesn't require a strong break, so only the
    confirmation candle at 17 needs to become a marubozu."""
    rows = plain_rows(UP_PRICES)
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return candles_from(rows)


def bearish_confirmed_candles():
    """Mirror of the bullish fixture via the 240 - price transform."""
    rows = plain_rows(DOWN_PRICES)
    rows[17] = (129.4, 127.6, 129.5, 127.5)
    return candles_from(rows)


def run_signal(candles):
    analysis = analyze_structure(candles)
    return detect_break_and_retest_signal(
        candles, list(analysis.swings), list(analysis.bos_events)
    )


def test_bullish_confirmed_signal():
    result = run_signal(bullish_confirmed_candles())
    assert result.state is BreakAndRetestState.CONFIRMED
    signal = result.signal
    assert signal is not None
    assert signal.direction == "bullish"
    assert signal.entry_price == 112.4
    assert signal.stop_loss == 110.5
    assert signal.break_level == 111.0
    assert signal.confirmation_pattern == "bullish_marubozu"
    assert signal.take_profit is None
    assert signal.structure_scope is StructureScope.EXTERNAL


def test_bearish_confirmed_signal():
    result = run_signal(bearish_confirmed_candles())
    assert result.state is BreakAndRetestState.CONFIRMED
    signal = result.signal
    assert signal is not None
    assert signal.direction == "bearish"
    assert signal.entry_price == 127.6
    assert signal.stop_loss == 129.5
    assert signal.break_level == 129.0
    assert signal.confirmation_pattern == "bearish_marubozu"
    assert signal.take_profit is None
    assert signal.structure_scope is StructureScope.EXTERNAL


def test_no_confirmation_yet_keeps_waiting():
    candles = candles_from(plain_rows(UP_PRICES))
    result = run_signal(candles)
    assert result.state is BreakAndRetestState.WAITING_FOR_BULLISH_CONFIRMATION
    assert result.setup is not None
    assert result.signal is None


def test_no_setup_returns_the_original_result_unchanged():
    candles = candles_from(plain_rows(UP_PRICES))[:3]
    analysis = analyze_structure(candles)
    plain_result = detect_break_and_retest(
        candles, list(analysis.swings), list(analysis.bos_events)
    )
    signal_result = detect_break_and_retest_signal(
        candles, list(analysis.swings), list(analysis.bos_events)
    )
    assert signal_result.state == plain_result.state
    assert signal_result.setup == plain_result.setup
    assert signal_result.signal is None
