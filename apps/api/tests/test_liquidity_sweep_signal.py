from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.liquidity_sweep import detect_liquidity_sweep_signal
from app.scanner.structure import (
    ExternalStructure,
    MarketState,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXT, INT = StructureScope.EXTERNAL, StructureScope.INTERNAL


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


def reversal_fixture():
    """
    Sweep of a downtrend's swing low, a return to it, a same-candle CHoCH
    and first bullish BOS, a required bearish BOS (the engine alternates
    direction), a further bullish BOS, and a marubozu confirmation.
    """
    rows = [
        (108, 107, 109, 106),      # 0
        (107, 106, 108, 105),      # 1
        (106, 105, 107, 104),      # 2
        (105, 104, 106, 103),      # 3
        (104, 103, 105, 102),      # 4
        (103, 102, 104, 101),      # 5
        (102, 101, 103, 100),      # 6
        (101, 102, 103, 100.5),    # 7
        (102, 104, 105, 101),      # 8
        (104, 99, 104.5, 98),      # 9  sweeps the 100.0 low
        (99, 100.5, 101, 99),      # 10 returns to 100.0
        (100.5, 102, 103, 100),    # 11
        (102, 104, 105, 101.5),    # 12
        (104, 135, 135.5, 103.5),  # 13 CHoCH + BOS#1 bullish
        (130, 128, 131, 127),      # 14
        (128, 126, 129, 105),      # 15
        (126, 100, 127, 99),       # 16 BOS#2 bearish
        (100, 102, 103, 99),       # 17
        (131.6, 133.4, 133.5, 131.5),  # 18 BOS#3 bullish + marubozu confirmation
    ]
    candles = candles_from(rows)

    swings = [
        SwingPoint(2, BASE + timedelta(hours=2), 130.0, SwingType.HIGH, StructureLabel.HH, EXT),
        SwingPoint(6, BASE + timedelta(hours=6), 100.0, SwingType.LOW, StructureLabel.LL, EXT),
        SwingPoint(15, BASE + timedelta(hours=15), 105.0, SwingType.LOW, StructureLabel.HL, INT),
        SwingPoint(17, BASE + timedelta(hours=17), 132.0, SwingType.HIGH, StructureLabel.HH, INT),
    ]

    external = ExternalStructure(
        direction=MarketState.DOWNTREND,
        protected_high=swings[0],
        protected_low=None,
        external_high=None,
        external_low=None,
    )

    return candles, swings, external


def test_bullish_liquidity_sweep_signal():
    candles, swings, external = reversal_fixture()
    signal = detect_liquidity_sweep_signal(candles, swings, external)
    assert signal is not None
    assert signal.direction == "bullish"
    assert signal.entry_price == 133.4
    assert signal.stop_loss == 98.0
    assert signal.swept_level == 100.0
    assert signal.confirmation_pattern == "bullish_marubozu"
    assert signal.take_profit is None
    assert signal.structure_scope is StructureScope.EXTERNAL


def test_scope_filter_excludes_a_non_matching_level():
    candles, swings, external = reversal_fixture()
    assert detect_liquidity_sweep_signal(candles, swings, external, scope=INT) is None


def test_scope_filter_keeps_a_matching_level():
    candles, swings, external = reversal_fixture()
    signal = detect_liquidity_sweep_signal(candles, swings, external, scope=EXT)
    assert signal is not None
    assert signal.structure_scope is StructureScope.EXTERNAL


def test_no_signal_without_a_choch():
    candles, swings, _ = reversal_fixture()
    flat_external = ExternalStructure(
        direction=MarketState.UPTREND,
        protected_high=None,
        protected_low=None,
        external_high=None,
        external_low=None,
    )
    assert detect_liquidity_sweep_signal(candles, swings, flat_external) is None


def test_no_signal_with_too_few_candles():
    candles, swings, external = reversal_fixture()
    assert detect_liquidity_sweep_signal(candles[:12], swings, external) is None
