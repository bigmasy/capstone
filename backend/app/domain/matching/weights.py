"""Weights and share tables of the weighted scorer; injectable so calibration can replace them."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import TypeVar

from app.domain.functional import FunctionalLevel
from app.domain.privacy import DistanceBand

WEIGHT_TOTAL = 100

_K = TypeVar("_K")


@dataclass(frozen=True, slots=True)
class Weights:
    """Points of each criterion; the four weights add up to 100.

    Initial weights are the author's assumptions and are not calibrated.

    :param sport: Points for the share of common sports.
    :param distance: Points for proximity, by distance band.
    :param functional: Points for the functional level.
    :param intensity: Points for the closeness of preferred intensity.
    :raises TypeError: If a weight is not an integer (integers keep tenths exact).
    :raises ValueError: If a weight is negative or the weights do not add up to 100.
    """

    sport: int
    distance: int
    functional: int
    intensity: int

    def __post_init__(self) -> None:
        """Validate that the weights are non-negative integers that add up to 100."""
        parts = (self.sport, self.distance, self.functional, self.intensity)
        if not all(type(part) is int for part in parts):
            raise TypeError("weights must be integers")
        if any(part < 0 for part in parts):
            raise ValueError("weights must not be negative")
        if sum(parts) != WEIGHT_TOTAL:
            raise ValueError(f"weights must add up to {WEIGHT_TOTAL}")


def _frozen_shares(
    shares: Mapping[_K, Fraction], keys: tuple[_K, ...], name: str
) -> Mapping[_K, Fraction]:
    """Return a read-only copy of a complete share table, checking range and coverage."""
    if set(shares) != set(keys):
        raise ValueError(f"{name} share table must cover every key exactly once")
    if any(not 0 <= share <= 1 for share in shares.values()):
        raise ValueError(f"{name} shares must be between 0 and 1")
    return MappingProxyType({key: shares[key] for key in keys})


@dataclass(frozen=True, slots=True)
class ScoringTables:
    """Share of the weight earned in each distance band and at each functional level.

    Proximity is scored by the band shown in the API, not by the exact distance: a
    contribution that decreased linearly with the distance would let a caller who compares
    several profiles recover the position of another profile's grid cell. The functional
    criterion likewise enters the score only through its coarse level.

    :param distance_share: Share of the distance weight per band, from 0 to 1.
    :param functional_share: Share of the functional weight per level, from 0 to 1.
    :raises ValueError: If a table misses a key or a share lies outside 0..1.
    """

    distance_share: Mapping[DistanceBand, Fraction]
    functional_share: Mapping[FunctionalLevel, Fraction]

    def __post_init__(self) -> None:
        """Validate the tables and replace them with read-only copies."""
        distance = _frozen_shares(self.distance_share, tuple(DistanceBand), "distance")
        functional = _frozen_shares(self.functional_share, tuple(FunctionalLevel), "functional")
        # frozen=True forbids plain assignment; the copies keep the object immutable
        object.__setattr__(self, "distance_share", distance)
        object.__setattr__(self, "functional_share", functional)


DEFAULT_WEIGHTS = Weights(sport=30, distance=30, functional=25, intensity=15)

# Author's assumptions, not calibrated
DEFAULT_TABLES = ScoringTables(
    distance_share={
        DistanceBand.UNDER_5_KM: Fraction(1),
        DistanceBand.FROM_5_TO_10_KM: Fraction(2, 3),
        DistanceBand.FROM_10_TO_25_KM: Fraction(1, 3),
        DistanceBand.OVER_25_KM: Fraction(0),
    },
    functional_share={
        FunctionalLevel.LOW: Fraction(0),
        FunctionalLevel.MEDIUM: Fraction(1, 2),
        FunctionalLevel.HIGH: Fraction(1),
    },
)
