import pytest

from app.market.models import Timeframe
from app.scanner.mtf import (
    AUTO_PROFILE,
    PRESET_PROFILES,
    MTFProfile,
    MTFProfileError,
    MTFRole,
    profile_from_dict,
    profile_from_values,
)

TF = Timeframe


def test_presets_are_the_three_specified_profiles():
    assert list(PRESET_PROFILES) == ["1d-4h-30m", "4h-1h-15m", "1h-30m-5m"]
    p = PRESET_PROFILES["1d-4h-30m"]
    assert (p.bias, p.structure, p.execution) == ((TF.D1,), (TF.H4,), (TF.M30,))
    p = PRESET_PROFILES["4h-1h-15m"]
    assert (p.bias, p.structure, p.execution) == ((TF.H4,), (TF.H1,), (TF.M15,))
    p = PRESET_PROFILES["1h-30m-5m"]
    assert (p.bias, p.structure, p.execution) == ((TF.H1,), (TF.M30,), (TF.M5,))


def test_auto_profile_matches_specification():
    assert AUTO_PROFILE.name == "auto"
    assert AUTO_PROFILE.bias == (TF.D1, TF.H4, TF.H2)
    assert AUTO_PROFILE.structure == (TF.H1, TF.M30, TF.M15)
    assert AUTO_PROFILE.execution == (TF.M5, TF.M2, TF.M1)


def test_timeframes_are_normalised_longest_first():
    p = profile_from_values("c", ["2h", "1d", "4h"], ["15m", "1h"], ["1m", "5m"])
    assert p.bias == (TF.D1, TF.H4, TF.H2)
    assert p.structure == (TF.H1, TF.M15)
    assert p.execution == (TF.M5, TF.M1)


def test_all_timeframes_longest_first_without_duplicates():
    assert AUTO_PROFILE.all_timeframes == (
        TF.D1, TF.H4, TF.H2, TF.H1, TF.M30, TF.M15, TF.M5, TF.M2, TF.M1,
    )
    seconds = [tf.seconds for tf in AUTO_PROFILE.all_timeframes]
    assert seconds == sorted(set(seconds), reverse=True)


def test_timeframes_for_role():
    p = PRESET_PROFILES["4h-1h-15m"]
    assert p.timeframes_for(MTFRole.BIAS) == (TF.H4,)
    assert p.timeframes_for(MTFRole.STRUCTURE) == (TF.H1,)
    assert p.timeframes_for(MTFRole.EXECUTION) == (TF.M15,)


@pytest.mark.parametrize("role", ["bias", "structure", "execution"])
def test_empty_role_rejected(role):
    roles = {"bias": ["1d"], "structure": ["1h"], "execution": ["5m"]}
    roles[role] = []
    with pytest.raises(MTFProfileError, match=f"{role}: at least one"):
        profile_from_values("x", **roles)


def test_duplicate_within_role_rejected():
    with pytest.raises(MTFProfileError, match="duplicate"):
        profile_from_values("x", ["1d", "1d"], ["1h"], ["5m"])


def test_same_timeframe_in_two_roles_rejected():
    with pytest.raises(MTFProfileError, match="structure timeframe must be shorter"):
        profile_from_values("x", ["4h"], ["4h"], ["5m"])


def test_structure_longer_than_bias_rejected():
    with pytest.raises(MTFProfileError, match="structure timeframe must be shorter"):
        profile_from_values("x", ["1h", "4h"], ["2h"], ["5m"])


def test_execution_longer_than_structure_rejected():
    with pytest.raises(MTFProfileError, match="execution timeframe must be shorter"):
        profile_from_values("x", ["1d"], ["15m", "1h"], ["30m"])


def test_unknown_timeframe_rejected():
    with pytest.raises(MTFProfileError, match="unknown timeframe '45m'"):
        profile_from_values("x", ["1d"], ["45m"], ["5m"])


def test_blank_name_rejected():
    with pytest.raises(MTFProfileError, match="name"):
        profile_from_values("  ", ["1d"], ["1h"], ["5m"])


def test_valid_custom_profile_accepted():
    p = profile_from_values("mine", ["1d"], ["1h"], ["1m"])
    assert p.all_timeframes == (TF.D1, TF.H1, TF.M1)


def test_dict_roundtrip():
    data = AUTO_PROFILE.to_dict()
    assert data == {
        "name": "auto",
        "bias": ["1d", "4h", "2h"],
        "structure": ["1h", "30m", "15m"],
        "execution": ["5m", "2m", "1m"],
    }
    assert profile_from_dict(data) == AUTO_PROFILE


@pytest.mark.parametrize("bad", [{}, {"name": "x"}, {"name": "x", "bias": 5,
                                                      "structure": ["1h"],
                                                      "execution": ["5m"]}])
def test_malformed_dict_rejected(bad):
    with pytest.raises(MTFProfileError):
        profile_from_dict(bad)


def test_profile_is_immutable():
    with pytest.raises(AttributeError):
        AUTO_PROFILE.name = "other"


def test_direct_construction_is_validated_too():
    with pytest.raises(MTFProfileError):
        MTFProfile("x", (TF.H1,), (TF.H4,), (TF.M5,))
