import pytest

from app.scanner.risk import compute_take_profit


def test_bullish_default_1_to_2():
    # risk = 112 - 110 = 2; target = 112 + 2*2 = 116
    tp = compute_take_profit("bullish", entry_price=112.0, stop_loss=110.0)
    assert tp == 116.0


def test_bearish_default_1_to_2():
    # risk = 100 - 98 = 2; target = 98 - 2*2 = 94
    tp = compute_take_profit("bearish", entry_price=98.0, stop_loss=100.0)
    assert tp == 94.0


def test_bullish_custom_ratio():
    # risk = 10; target = 100 + 10*3 = 130
    tp = compute_take_profit("bullish", entry_price=100.0, stop_loss=90.0, risk_reward=3.0)
    assert tp == 130.0


def test_bearish_custom_ratio():
    tp = compute_take_profit("bearish", entry_price=100.0, stop_loss=110.0, risk_reward=1.5)
    assert tp == 85.0


def test_ratio_of_one_equals_the_risk_distance():
    tp = compute_take_profit("bullish", entry_price=100.0, stop_loss=95.0, risk_reward=1.0)
    assert tp == 105.0


@pytest.mark.parametrize(
    "direction, entry, stop",
    [
        pytest.param("bullish", 100.0, 100.0, id="bullish-zero-risk"),
        pytest.param("bullish", 100.0, 105.0, id="bullish-inverted-stop"),
        pytest.param("bearish", 100.0, 100.0, id="bearish-zero-risk"),
        pytest.param("bearish", 100.0, 95.0, id="bearish-inverted-stop"),
    ],
)
def test_non_positive_risk_raises(direction, entry, stop):
    with pytest.raises(ValueError, match="stop_loss must be"):
        compute_take_profit(direction, entry, stop)


def test_unknown_direction_raises():
    with pytest.raises(ValueError, match="Unknown direction"):
        compute_take_profit("sideways", 100.0, 95.0)


@pytest.mark.parametrize("bad_ratio", [0, -1.0, -0.5])
def test_non_positive_risk_reward_raises(bad_ratio):
    with pytest.raises(ValueError, match="risk_reward must be positive"):
        compute_take_profit("bullish", 100.0, 95.0, risk_reward=bad_ratio)
