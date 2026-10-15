from app.scanner.poi_matching import POIMatch
from app.scanner.scoring import (
    compute_score,
    confirmation_score,
    poi_score,
    risk_reward_score,
    structure_score,
)
from app.scanner.structure import StructureScope

EXT, INT, UND = StructureScope.EXTERNAL, StructureScope.INTERNAL, StructureScope.UNDEFINED


def match(overlap=False, near=False):
    return POIMatch(
        poi=None, poi_type="Fake", direction=None, status=None,
        overlap=overlap, near=near, distance_atr=None,
        interaction="NONE", match_context="CONFIRMATION",
    )


def test_structure_score_values():
    assert structure_score(EXT) == 100.0
    assert structure_score(INT) == 50.0
    assert structure_score(UND) == 0.0


def test_poi_score_overlap_beats_near_beats_none():
    assert poi_score([match(overlap=True)]) == 100.0
    assert poi_score([match(near=True)]) == 70.0
    assert poi_score([match(overlap=True), match(near=True)]) == 100.0
    assert poi_score([]) == 0.0
    assert poi_score([match()]) == 0.0


def test_risk_reward_score_capped_at_1_to_5():
    # risk=10, reward=40 -> rr=4 -> 4/5*100=80
    assert risk_reward_score("bullish", 110, 100, 150) == 80.0
    # risk=1, reward=100 -> rr=100, capped at 100
    assert risk_reward_score("bullish", 100, 99, 200) == 100.0


def test_risk_reward_score_none_take_profit_is_zero():
    assert risk_reward_score("bullish", 110, 100, None) == 0.0


def test_risk_reward_score_invalid_risk_or_reward_is_zero():
    # stop on the wrong side for a bullish setup -> risk<=0
    assert risk_reward_score("bullish", 100, 105, 120) == 0.0
    # take_profit below entry for a bullish setup -> reward<=0
    assert risk_reward_score("bullish", 100, 95, 90) == 0.0


def test_risk_reward_score_bearish_direction():
    # entry=100, stop=110 (risk=10), take_profit=60 (reward=40) -> rr=4 -> 80
    assert risk_reward_score("bearish", 100, 110, 60) == 80.0


def test_confirmation_score_known_and_unknown_patterns():
    assert confirmation_score("bullish_engulfing") == 100.0
    assert confirmation_score("bullish_marubozu") == 90.0
    assert confirmation_score("hammer") == 75.0
    assert confirmation_score("bullish_pin_bar") == 65.0
    assert confirmation_score("not_a_real_pattern") == 50.0


def test_compute_score_external_overlap_strong_rr_engulfing():
    score = compute_score(
        EXT, [match(overlap=True)], "bullish", 110, 100, 150, "bullish_engulfing"
    )
    assert score == 95.0


def test_compute_score_internal_no_poi_no_tp_pin_bar():
    score = compute_score(INT, [], "bearish", 100, 110, None, "bearish_pin_bar")
    assert score == 24.75


def test_compute_score_external_near_only_hammer():
    score = compute_score(
        EXT, [match(near=True)], "bullish", 100, 95, 120, "hammer"
    )
    assert score == 82.25


def test_compute_score_is_clamped_to_a_sensible_range():
    # best possible: all four factors maxed out
    best = compute_score(
        EXT, [match(overlap=True)], "bullish", 100, 90, 1000, "bullish_engulfing"
    )
    assert best == 100.0
    # worst possible: all four factors zeroed
    worst = compute_score(UND, [], "sideways", 100, 100, None, "unknown_pattern")
    assert worst == 7.5  # only the default confirmation score contributes: 50*0.15
