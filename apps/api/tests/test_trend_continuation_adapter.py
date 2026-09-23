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


# --- Level loss and expiry, tested directly against the adapter's
# BREAK_DETECTED / RETEST_WAITING branches. These checks only ever read
# machine.context's break_level/direction, so we construct that context
# directly (same principle as Step 89's direct-state-setting tests)
# rather than fighting a naturalistic fixture through every BOS
# alternation rule just to reach these states causally.

from app.market.models import Candle
from app.scanner.structure import BreakOfStructure, StructureScope
from app.scanner.trend_continuation import TrendContinuationBreak, TrendContinuationRetest


def _break_candle():
    return Candle(
        timestamp=BASE + timedelta(hours=10), open=110, high=112, low=109, close=111.5,
        volume=1.0,
    )


def _fake_break(level=111.0, direction="bullish"):
    return TrendContinuationBreak(
        direction=direction,
        break_level=level,
        candle_index=10,
        candle=_break_candle(),
        bos=BreakOfStructure(direction, level, 10, BASE + timedelta(hours=10)),
        structure_scope=StructureScope.EXTERNAL,
    )


def _fake_retest(level=111.0, direction="bullish"):
    return TrendContinuationRetest(
        direction=direction,
        break_level=level,
        break_index=10,
        retest_index=14,
        candle=_break_candle(),
        bos=BreakOfStructure(direction, level, 10, BASE + timedelta(hours=10)),
        structure_scope=StructureScope.EXTERNAL,
    )


def _tracker_of(n):
    tracker = StructureTracker()
    for i in range(n):
        tracker.add_candle(
            Candle(
                timestamp=BASE + timedelta(hours=i),
                open=111, high=112, low=110, close=111, volume=1.0,
            )
        )
    return tracker


def test_level_loss_invalidates_from_break_detected():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    machine.state = SetupState.BREAK_DETECTED
    machine.context = _fake_break()
    machine.state_entered_at = 10
    tracker = _tracker_of(11)

    losing_candle = Candle(
        timestamp=BASE + timedelta(hours=11), open=110, high=110.5, low=105, close=105,
        volume=1.0,
    )
    tracker.add_candle(losing_candle)
    advance_trend_continuation(machine, tracker, losing_candle, 11)

    assert machine.state is SetupState.INVALIDATED
    assert "level 111.0 lost" in machine.history[-1].reason


def test_level_loss_invalidates_from_retest_waiting():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    machine.state = SetupState.RETEST_WAITING
    machine.context = _fake_retest()
    machine.state_entered_at = 14
    tracker = _tracker_of(15)

    losing_candle = Candle(
        timestamp=BASE + timedelta(hours=15), open=110, high=110.5, low=105, close=105,
        volume=1.0,
    )
    tracker.add_candle(losing_candle)
    advance_trend_continuation(machine, tracker, losing_candle, 15)

    assert machine.state is SetupState.INVALIDATED
    assert "level 111.0 lost" in machine.history[-1].reason


def test_no_invalidation_while_the_level_holds():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    machine.state = SetupState.BREAK_DETECTED
    machine.context = _fake_break()
    machine.state_entered_at = 10
    tracker = _tracker_of(11)

    holding_candle = Candle(
        timestamp=BASE + timedelta(hours=11), open=111.5, high=112, low=111.3, close=111.8,
        volume=1.0,
    )
    tracker.add_candle(holding_candle)
    advance_trend_continuation(machine, tracker, holding_candle, 11)

    assert machine.state is SetupState.BREAK_DETECTED


def test_expiry_fires_after_max_bars_from_break_detected():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    machine.state = SetupState.BREAK_DETECTED
    machine.context = _fake_break()
    machine.state_entered_at = 10
    tracker = _tracker_of(30)

    stale_candle = Candle(
        timestamp=BASE + timedelta(hours=30), open=111, high=112, low=110.5, close=111.2,
        volume=1.0,
    )
    tracker.add_candle(stale_candle)
    advance_trend_continuation(machine, tracker, stale_candle, 30, max_expiry_bars=20)

    assert machine.state is SetupState.EXPIRED
    assert "expired after 20 candles without a retest" in machine.history[-1].reason


def test_no_expiry_before_max_bars_from_retest_waiting():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", TC))
    machine.state = SetupState.RETEST_WAITING
    machine.context = _fake_retest()
    machine.state_entered_at = 14
    tracker = _tracker_of(33)

    not_yet_candle = Candle(
        timestamp=BASE + timedelta(hours=33), open=111, high=112, low=110.5, close=111.2,
        volume=1.0,
    )
    tracker.add_candle(not_yet_candle)
    advance_trend_continuation(machine, tracker, not_yet_candle, 33, max_expiry_bars=20)

    assert machine.state is SetupState.RETEST_WAITING
