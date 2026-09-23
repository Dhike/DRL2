from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.liquidity_sweep import LiquidityReturn, LiquiditySweep
from app.scanner.liquidity_sweep_adapter import advance_liquidity_sweep
from app.scanner.models import ScannerStrategy
from app.scanner.state_machine import Scope, SetupState, SetupStateMachine
from app.scanner.structure import (
    BreakOfStructure,
    ChangeOfCharacter,
    ExternalStructure,
    MarketState,
    StructureLabel,
    StructureScope,
    SwingPoint,
    SwingType,
)
from app.scanner.structure_tracker import StructureTracker

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
LS = ScannerStrategy.LIQUIDITY_SWEEP
EXT = StructureScope.EXTERNAL

# Same hand-built downtrend reversal fixture verified in Step 85's signal
# tests and again by dry run here: sweep at 9, return at 10, CHoCH at 13.
BASE_ROWS = [
    (108, 107, 109, 106), (107, 106, 108, 105), (106, 105, 107, 104),
    (105, 104, 106, 103), (104, 103, 105, 102), (103, 102, 104, 101),
    (102, 101, 103, 100), (101, 102, 103, 100.5), (102, 104, 105, 101),
    (104, 99, 104.5, 98), (99, 100.5, 101, 99), (100.5, 102, 103, 100),
    (102, 104, 105, 101.5), (104, 135, 135.5, 103.5),
]


def make_candles(rows):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=o, high=h, low=low, close=c, volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def make_external():
    protected_high = SwingPoint(
        2, BASE + timedelta(hours=2), 130.0, SwingType.HIGH, StructureLabel.HH, EXT
    )
    return ExternalStructure(
        direction=MarketState.DOWNTREND,
        protected_high=protected_high,
        protected_low=None,
        external_high=None,
        external_low=None,
    )


def run_through(rows, max_expiry_bars=20):
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", LS))
    tracker = StructureTracker()
    external = make_external()
    first_seen_at: dict[SetupState, int] = {}
    candles = make_candles(rows)
    for i, candle in enumerate(candles):
        tracker.add_candle(candle)
        advance_liquidity_sweep(
            machine, tracker, candle, i, external, max_expiry_bars=max_expiry_bars
        )
        if machine.state not in first_seen_at:
            first_seen_at[machine.state] = i
    return machine, first_seen_at


def test_real_recognition_reaches_break_detected():
    """Dry-run verified: the CHoCH and matching sell-side return are
    genuinely recognized at candle 13, driven entirely by real candles
    through StructureTracker (only `external` is supplied directly --
    see the adapter's documented limitation on deriving it causally)."""
    machine, first_seen_at = run_through(BASE_ROWS)
    assert first_seen_at[SetupState.BREAK_DETECTED] == 13
    choch, matching_return = machine.context
    assert choch.direction == "bullish"
    assert choch.broken_level == 130.0
    assert matching_return.side == "sell_side"
    assert matching_return.liquidity_price == 100


def test_level_loss_invalidates_from_break_detected():
    """Dry-run verified: candle 14 (a natural pullback to 128) closes
    back below the 130.0 protected level right after CHoCH."""
    rows = BASE_ROWS + [(130, 128, 131, 127)]
    machine, first_seen_at = run_through(rows)

    assert first_seen_at[SetupState.BREAK_DETECTED] == 13
    assert machine.state is SetupState.INVALIDATED
    assert "level 130.0 lost" in machine.history[-1].reason


def test_expiry_after_max_bars_without_a_bos():
    """Dry-run verified: flat candles holding above 130.0 forever never
    form a new swing, so no post-CHoCH BOS ever appears; expires at
    exactly 13 + 20 = 33."""
    rows = BASE_ROWS + [(135.0, 135.0, 136.0, 134.0)] * 25
    machine, first_seen_at = run_through(rows, max_expiry_bars=20)

    assert first_seen_at[SetupState.BREAK_DETECTED] == 13
    assert machine.state is SetupState.EXPIRED
    assert first_seen_at[SetupState.EXPIRED] == 33
    assert "expired after 20 candles without a BOS" in machine.history[-1].reason


def test_no_choch_stays_idle():
    """A flat, swing-free series has no CHoCH at all."""
    flat_rows = [(100.0, 100.0, 100.5, 99.5) for _ in range(15)]
    machine, _ = run_through(flat_rows)
    assert machine.state is SetupState.IDLE
    assert machine.history == []


# --- RETEST_WAITING / VALID_SETUP mechanics, tested via direct-context
# construction. A real, organic path from BREAK_DETECTED to a confirmed
# post-CHoCH BOS needs several more candles than swing confirmation
# allows to test cleanly (2 bars each side, per detect_confirmed_swings) --
# same limitation and same resolution as Step 91b's direct-context tests
# for Trend Continuation.

def _fake_bos_context():
    choch = ChangeOfCharacter(
        direction="bullish", broken_level=130.0, candle_index=13,
        candle_timestamp=BASE + timedelta(hours=13),
        previous_direction=MarketState.DOWNTREND,
    )
    matching_return = LiquidityReturn(
        side="sell_side", liquidity_price=100, sweep_index=9, return_index=10,
        candle=make_candles(BASE_ROWS)[10],
        sweep=LiquiditySweep(
            side="sell_side", liquidity_price=100, candle_index=9,
            candle=make_candles(BASE_ROWS)[9], swing_index=6, scope=EXT,
        ),
        scope=EXT,
    )
    bos = BreakOfStructure("bullish", 133.0, 18, BASE + timedelta(hours=18))
    return choch, matching_return, bos


def test_level_loss_invalidates_from_retest_waiting():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", LS))
    choch, matching_return, bos = _fake_bos_context()
    machine.state = SetupState.RETEST_WAITING
    machine.context = (bos, matching_return)
    machine.state_entered_at = 18

    tracker = StructureTracker()
    for candle in make_candles(BASE_ROWS)[:14]:
        tracker.add_candle(candle)
    losing_candle = Candle(
        timestamp=BASE + timedelta(hours=19), open=132, high=132.5, low=125, close=125,
        volume=1.0,
    )
    tracker.add_candle(losing_candle)
    advance_liquidity_sweep(machine, tracker, losing_candle, 19, make_external())

    assert machine.state is SetupState.INVALIDATED
    assert "level 133.0 lost" in machine.history[-1].reason


def test_no_expiry_before_max_bars_from_retest_waiting():
    machine = SetupStateMachine(Scope("BTC/USDT", "1h", LS))
    choch, matching_return, bos = _fake_bos_context()
    machine.state = SetupState.RETEST_WAITING
    machine.context = (bos, matching_return)
    machine.state_entered_at = 18

    tracker = StructureTracker()
    for candle in make_candles(BASE_ROWS)[:14]:
        tracker.add_candle(candle)
    not_yet_candle = Candle(
        timestamp=BASE + timedelta(hours=37), open=134, high=135, low=133.5, close=134.5,
        volume=1.0,
    )
    tracker.add_candle(not_yet_candle)
    advance_liquidity_sweep(
        machine, tracker, not_yet_candle, 37, make_external(), max_expiry_bars=20
    )

    assert machine.state is SetupState.RETEST_WAITING
