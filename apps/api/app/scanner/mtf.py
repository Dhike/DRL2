"""Multi-timeframe (MTF) profiles.

A profile assigns timeframes to three roles:

* bias      - the higher-timeframe trend direction
* structure - where setups and structure are found
* execution - where entries are timed

Roles are strictly ordered: every execution timeframe is shorter than every
structure timeframe, which is shorter than every bias timeframe. Within a role
timeframes are normalised longest-first.
"""

from dataclasses import dataclass
from enum import Enum

from app.market.models import Timeframe


class MTFRole(str, Enum):
    BIAS = "bias"
    STRUCTURE = "structure"
    EXECUTION = "execution"


class MTFProfileError(ValueError):
    """The requested multi-timeframe profile is not valid."""


def _normalised(role: MTFRole, values: tuple[Timeframe, ...]) -> tuple[Timeframe, ...]:
    if not values:
        raise MTFProfileError(f"{role.value}: at least one timeframe is required")
    if len(set(values)) != len(values):
        raise MTFProfileError(f"{role.value}: duplicate timeframes are not allowed")
    return tuple(sorted(values, key=lambda tf: tf.seconds, reverse=True))


@dataclass(frozen=True, slots=True)
class MTFProfile:
    name: str
    bias: tuple[Timeframe, ...]
    structure: tuple[Timeframe, ...]
    execution: tuple[Timeframe, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise MTFProfileError("profile name is required")
        bias = _normalised(MTFRole.BIAS, tuple(self.bias))
        structure = _normalised(MTFRole.STRUCTURE, tuple(self.structure))
        execution = _normalised(MTFRole.EXECUTION, tuple(self.execution))
        if structure[0].seconds >= bias[-1].seconds:
            raise MTFProfileError(
                "every structure timeframe must be shorter than every bias timeframe"
            )
        if execution[0].seconds >= structure[-1].seconds:
            raise MTFProfileError(
                "every execution timeframe must be shorter than every "
                "structure timeframe"
            )
        object.__setattr__(self, "bias", bias)
        object.__setattr__(self, "structure", structure)
        object.__setattr__(self, "execution", execution)

    def timeframes_for(self, role: MTFRole) -> tuple[Timeframe, ...]:
        return getattr(self, role.value)

    @property
    def all_timeframes(self) -> tuple[Timeframe, ...]:
        """Every timeframe the profile needs, longest first, no duplicates."""
        return self.bias + self.structure + self.execution

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "bias": [tf.value for tf in self.bias],
            "structure": [tf.value for tf in self.structure],
            "execution": [tf.value for tf in self.execution],
        }


def _parse(role: MTFRole, values: list[str] | tuple[str, ...]) -> tuple[Timeframe, ...]:
    parsed: list[Timeframe] = []
    for value in values:
        try:
            parsed.append(Timeframe(value))
        except ValueError:
            valid = ", ".join(tf.value for tf in Timeframe)
            raise MTFProfileError(
                f"{role.value}: unknown timeframe {value!r} (valid: {valid})"
            ) from None
    return tuple(parsed)


def profile_from_values(
    name: str,
    bias: list[str] | tuple[str, ...],
    structure: list[str] | tuple[str, ...],
    execution: list[str] | tuple[str, ...],
) -> MTFProfile:
    return MTFProfile(
        name=name,
        bias=_parse(MTFRole.BIAS, bias),
        structure=_parse(MTFRole.STRUCTURE, structure),
        execution=_parse(MTFRole.EXECUTION, execution),
    )


def profile_from_dict(data: dict) -> MTFProfile:
    try:
        return profile_from_values(
            str(data["name"]), data["bias"], data["structure"], data["execution"]
        )
    except (KeyError, TypeError) as exc:
        raise MTFProfileError(
            "profile needs name, bias, structure and execution"
        ) from exc


PRESET_PROFILES: dict[str, MTFProfile] = {
    profile.name: profile
    for profile in (
        profile_from_values("1d-4h-30m", ["1d"], ["4h"], ["30m"]),
        profile_from_values("4h-1h-15m", ["4h"], ["1h"], ["15m"]),
        profile_from_values("1h-30m-5m", ["1h"], ["30m"], ["5m"]),
    )
}

AUTO_PROFILE = profile_from_values(
    "auto",
    bias=["1d", "4h", "2h"],
    structure=["1h", "30m", "15m"],
    execution=["5m", "2m", "1m"],
)
