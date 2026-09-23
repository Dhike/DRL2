from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import Scope, SetupState, SetupStateMachine
from app.scanner.structure_tracker import StructureTracker
from app.scanner.break_and_retest_adapter import advance_break_and_retest

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
BR = ScannerStrategy.BREAK_AND_RETEST

# Same zigzag used throughout. Break & Retest does not depend on
# market_state, so unlike Trend Continuation its states progress
# causally without a recognition-lag issue (confirmed by dry run).
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def make_candles(rows):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def run_through(candles, max_expiry_bars=20):
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", BR))
    tracker = StructureTracker()
    first_seen_at: dict[SetupState, int] = {}
    for i, candle in enumerate(candles):
        tracker.add_candle(candle)
        advance_break_and_retest(machine, tracker, candle, i, max_expiry_bars=max_expiry_bars)
        if machine.state not in first_seen_at:
            first_seen_at[machine.state] = i
    return machine, first_seen_at


def test_full_lifecycle_reaches_valid_setup():
    """Dry-run verified: candles 15-16 adjusted so their CLOSE stays above
    the 111.0 level (strict policy only checks the close), letting the
    setup survive to the confirmation at candle 17."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[15] = (111.2, 111.2, 112.0, 111.0)
    rows[16] = (111.5, 111.5, 112.5, 111.2)
    rows[17] = (110.6, 112.4, 112.5, 110.5)

    machine, first_seen_at = run_through(make_candles(rows))

    assert machine.state is SetupState.VALID_SETUP
    assert first_seen_at[SetupState.BREAK_DETECTED] == 11
    assert first_seen_at[SetupState.RETEST_WAITING] == 14
    assert first_seen_at[SetupState.VALID_SETUP] == 17

    signal = machine.context
    assert signal.confirmation_pattern == "bullish_marubozu"
    assert signal.entry_price == 112.4
    assert signal.stop_loss == 110.5
    assert signal.take_profit is None
    assert signal.structure_scope.value == "external"


def test_confirmation_waiting_appears_momentarily():
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[15] = (111.2, 111.2, 112.0, 111.0)
    rows[16] = (111.5, 111.5, 112.5, 111.2)
    rows[17] = (110.6, 112.4, 112.5, 110.5)

    machine, _ = run_through(make_candles(rows))
    reasons = [record.new_state for record in machine.history]
    assert SetupState.CONFIRMATION_WAITING in reasons
    idx = reasons.index(SetupState.CONFIRMATION_WAITING)
    assert reasons[idx + 1] == SetupState.VALID_SETUP


def test_no_setup_stays_idle():
    """A genuinely flat price series has no swings at all, so no BOS
    and no break is ever possible -- distinct from UP_PRICES, which
    (as proven above) DOES break and then gets invalidated."""
    flat_rows = [(100.0, 100.0, 100.5, 99.5) for _ in range(20)]
    machine, _ = run_through(make_candles(flat_rows))
    assert machine.state is SetupState.IDLE
    assert machine.history == []


def test_level_loss_invalidates_during_break_detected():
    """Dry-run verified: candle 12 crashes well below the 111.0 level
    while still waiting for the retest."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES[:13]]
    rows[12] = (108, 100, 108, 99)

    machine, _ = run_through(make_candles(rows))

    assert machine.state is SetupState.INVALIDATED
    assert "level 111.0 lost" in machine.history[-1].reason
    assert machine.history[-2].new_state is SetupState.BREAK_DETECTED


def test_level_loss_invalidates_during_retest_waiting():
    """Dry-run verified: the unmodified zigzag's own candle 15 closes
    back below 111.0 right after the retest, before any confirmation."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[17] = (110.6, 112.4, 112.5, 110.5)

    machine, first_seen_at = run_through(make_candles(rows))

    assert first_seen_at[SetupState.RETEST_WAITING] == 14
    assert machine.state is SetupState.INVALIDATED
    assert "level 111.0 lost" in machine.history[-1].reason
    assert machine.history[-2].new_state is SetupState.RETEST_WAITING


def test_expiry_after_max_bars_without_a_retest():
    """Dry-run verified: break recognized at 11, then flat candles that
    never dip to retest 111.0, expiring exactly at 11 + 20 = 31."""
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES[:12]]
    rows += [(115.0, 115.0, 116.0, 113.0)] * 25

    machine, first_seen_at = run_through(make_candles(rows), max_expiry_bars=20)

    assert first_seen_at[SetupState.BREAK_DETECTED] == 11
    assert machine.state is SetupState.EXPIRED
    assert first_seen_at[SetupState.EXPIRED] == 31
    assert "expired after 20 candles without a retest" in machine.history[-1].reason


def test_resolved_states_are_left_alone():
    rows = [(p, p, p + 1.0, p - 1.0) for p in UP_PRICES]
    rows[15] = (111.2, 111.2, 112.0, 111.0)
    rows[16] = (111.5, 111.5, 112.5, 111.2)
    rows[17] = (110.6, 112.4, 112.5, 110.5)

    machine, _ = run_through(make_candles(rows))
    assert machine.state is SetupState.VALID_SETUP
    history_len = len(machine.history)

    tracker = StructureTracker()
    for candle in make_candles(rows):
        tracker.add_candle(candle)
    extra = Candle(
        timestamp=BASE + timedelta(hours=29), open=1, high=2, low=0.5, close=1, volume=1.0,
    )
    tracker.add_candle(extra)
    advance_break_and_retest(machine, tracker, extra, 29)

    assert machine.state is SetupState.VALID_SETUP
    assert len(machine.history) == history_len
