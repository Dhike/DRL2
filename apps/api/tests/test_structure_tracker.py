from datetime import datetime, timedelta, timezone

from app.market.models import Candle
from app.scanner.analysis import analyze_structure
from app.scanner.structure_tracker import StructureTracker

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

# Same zigzag verified throughout the structure tests, extended with the
# Liquidity Sweep reversal candles from Step 85's fixture -- a good
# candidate precisely because that fixture already required trend,
# multiple BOS events, and scope reclassification along the way.
UP_PRICES = [
    100, 102.5, 105, 107.5, 110, 108.5, 107, 105.5, 104, 107,
    110, 113, 116, 114, 112, 110, 108, 111.5, 115, 118.5,
    122, 119.5, 117, 114.5, 112, 113.5, 115, 116.5, 118,
]


def candles_from(rows):
    return [
        Candle(
            timestamp=BASE + timedelta(hours=i),
            open=float(o), high=float(h), low=float(low), close=float(c),
            volume=1.0,
        )
        for i, (o, c, h, low) in enumerate(rows)
    ]


def plain_rows(prices):
    return [(p, p, p + 1.0, p - 1.0) for p in prices]


def test_tracker_matches_batch_analysis_after_every_single_candle():
    """
    Strongest guarantee available: after each incrementally-added candle,
    the tracker's result must exactly equal a fresh batch analyze_structure
    call on the identical prefix of candles. Not just the final result --
    every intermediate step, independently cross-checked.
    """
    candles = candles_from(plain_rows(UP_PRICES))
    tracker = StructureTracker()

    for i, candle in enumerate(candles):
        incremental_result = tracker.add_candle(candle)
        batch_result = analyze_structure(candles[: i + 1])
        assert incremental_result == batch_result, f"mismatch at candle index {i}"


def test_earlier_snapshots_never_change_retroactively():
    """
    The actual bug this tracker fixes: once the tracker has reported an
    analysis for the candles seen so far, adding MORE candles later must
    never change what that earlier analysis was. We can't rewind the
    tracker, so we instead prove the snapshot we recorded matches what a
    fresh batch call on that same prefix says, even after far more
    candles have since been added to the tracker.
    """
    rows = plain_rows(UP_PRICES)
    rows[11] = (112.3, 113.8, 114.0, 112.0)  # matches the strong-break fixture
    all_candles = candles_from(rows)

    tracker = StructureTracker()
    snapshot_at_15 = None
    for i, candle in enumerate(all_candles):
        result = tracker.add_candle(candle)
        if i == 15:
            snapshot_at_15 = result

    # Confirm more candles were in fact added after the snapshot.
    assert len(tracker.candles) == len(all_candles)
    assert len(all_candles) > 16

    # The snapshot taken at candle 15 must still match a fresh batch call
    # on exactly the first 16 candles -- unaffected by everything added
    # to the tracker afterward.
    assert snapshot_at_15 == analyze_structure(all_candles[:16])


def test_tracker_starts_empty_and_grows_one_candle_at_a_time():
    tracker = StructureTracker()
    assert tracker.candles == []

    candles = candles_from(plain_rows(UP_PRICES[:3]))
    for i, candle in enumerate(candles, start=1):
        tracker.add_candle(candle)
        assert len(tracker.candles) == i


def test_current_analysis_does_not_add_a_candle():
    tracker = StructureTracker()
    candles = candles_from(plain_rows(UP_PRICES[:5]))
    for candle in candles:
        tracker.add_candle(candle)

    before = tracker.current_analysis()
    again = tracker.current_analysis()

    assert len(tracker.candles) == 5
    assert before == again == analyze_structure(candles)
