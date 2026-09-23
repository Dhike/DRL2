from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import Scope, SetupState, SetupStateMachine
from app.scanner.structure_tracker import StructureTracker
from app.scanner.trend_continuation_adapter import advance_trend_continuation

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
TC = ScannerStrategy.TREND_CONTINUATION

# Same fixture used throughout: the real break/retest/confirmation are at
# candles 11/14/17, but market_state doesn't causally confirm UPTREND
# until candle 18 (4 labeled swings needed) -- confirmed by dry run. So a
# strictly causal system can only RECOGNIZE all three once it looks back
# at candle 18, resolving IDLE -> BREAK_DETECTED -> RETEST_WAITING ->
# VALID_SETUP across candles 18, 19, 20. This fixture cannot exercise
# genuine multi-candle waiting (nothing is left to wait for once
# recognition happens) -- that is covered separately in Step 91b with a
# purpose-built fixture.
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


def run_through(candles):
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    tracker = StructureTracker()
    first_seen_at: dict[SetupState, int] = {}

    for i, candle in enumerate(candles):
        tracker.add_candle(candle)
        advance_trend_continuation(machine, tracker, candle, i)
        if machine.state not in first_seen_at:
            first_seen_at[machine.state] = i

    return machine, first_seen_at


def test_full_lifecycle_matches_the_causally_verified_recognition_points():
    machine, first_seen_at = run_through(setup_candles())

    assert machine.state is SetupState.VALID_SETUP
    # Confirmed by dry run: recognition can't happen before market_state
    # becomes UPTREND at candle 18, at which point everything already
    # sitting in the past resolves immediately.
    assert first_seen_at[SetupState.BREAK_DETECTED] == 18
    assert first_seen_at[SetupState.RETEST_WAITING] == 19
    assert first_seen_at[SetupState.VALID_SETUP] == 20

    confirmation = machine.context
    assert confirmation.pattern == "bullish_marubozu"
    assert confirmation.candle.close == 112.4
    # The event object retains its own true, original candle index even
    # though recognition happened later.
    assert confirmation.confirmation_index == 17
    assert confirmation.retest.retest_index == 14


def test_confirmation_waiting_appears_in_history_even_though_momentary():
    machine, _ = run_through(setup_candles())

    reasons = [record.new_state for record in machine.history]
    assert SetupState.CONFIRMATION_WAITING in reasons
    idx = reasons.index(SetupState.CONFIRMATION_WAITING)
    assert reasons[idx + 1] == SetupState.VALID_SETUP


def test_no_setup_stays_idle():
    plain = [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=p, high=p + 1.0, low=p - 1.0, close=p, volume=1.0,
        )
        for i, p in enumerate(UP_PRICES)
    ]
    machine, _ = run_through(plain)
    assert machine.state is SetupState.IDLE
    assert machine.history == []


def test_resolved_states_are_left_alone():
    """Once a setup is VALID_SETUP, further calls must not touch it."""
    machine, _ = run_through(setup_candles())
    assert machine.state is SetupState.VALID_SETUP
    history_len = len(machine.history)

    tracker = StructureTracker()
    for candle in setup_candles():
        tracker.add_candle(candle)
    extra_candle = Candle(
        timestamp=BASE + timedelta(hours=29), open=1, high=2, low=0.5, close=1,
        volume=1.0,
    )
    tracker.add_candle(extra_candle)
    advance_trend_continuation(machine, tracker, extra_candle, 29)

    assert machine.state is SetupState.VALID_SETUP
    assert len(machine.history) == history_len
