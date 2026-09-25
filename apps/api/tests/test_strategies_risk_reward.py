from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.models import ScannerRequest, ScannerStrategy
from app.scanner.strategies import run_strategies

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
TC = ScannerStrategy.TREND_CONTINUATION

UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def setup_candles():
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[11] = (112.3, 113.8, 114.0, 112.0)
    rows[17] = (110.6, 112.4, 112.5, 110.5)
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def request():
    return ScannerRequest(
        market="crypto", symbol="BTC/USDT", timeframe="1h", strategies=(TC,),
    )


def test_no_risk_reward_leaves_take_profit_none():
    signals = run_strategies(request(), setup_candles())
    assert len(signals) == 1
    assert signals[0].take_profit is None


def test_default_scanning_ratio_fills_in_take_profit():
    """entry=112.4, stop=110.5 (known from earlier steps' fixtures);
    risk=1.9; 1:2 target = 112.4 + 1.9*2 = 116.2."""
    signals = run_strategies(request(), setup_candles(), risk_reward=2.0)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.entry_price == 112.4
    assert signal.stop_loss == 110.5
    assert round(signal.take_profit, 6) == 116.2


def test_a_different_ratio_produces_a_different_target():
    signals = run_strategies(request(), setup_candles(), risk_reward=3.0)
    # risk=1.9; 1:3 target = 112.4 + 1.9*3 = 118.1
    assert round(signals[0].take_profit, 6) == 118.1
