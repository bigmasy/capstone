"""The scoring port and the value objects that cross it."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from app.domain.functional import FunctionalLevel
from app.domain.privacy import DistanceBand, band_for, haversine_km
from app.domain.profile import ProfileView


class Criterion(StrEnum):
    """A criterion of the baseline breakdown; also the unit of the learned ranker's explanation."""

    SPORT = "sport"
    DISTANCE = "distance"
    FUNCTIONAL = "functional"
    INTENSITY = "intensity"


class RankSource(StrEnum):
    """Which strategy produced the order of a feed; shown to the caller."""

    BASELINE = "baseline"
    LEARNED = "learned"


class RankInfluence(StrEnum):
    """Qualitative effect of one criterion on the position of a candidate in a learned ranking.

    Shown instead of a raw model score, which is not calibrated and must not be read as a
    percentage.
    """

    RAISES = "raises"
    NEUTRAL = "neutral"
    LOWERS = "lowers"


@dataclass(frozen=True, slots=True)
class Candidate:
    """A profile offered to a viewer, with its distance from the viewer.

    The distance is internal: it may come from the database or from the cell centres, and it
    must reach the caller only as a band, so it is left out of ``repr``.

    :param profile: The candidate profile.
    :param distance_km: Distance from the viewer in kilometres.
    """

    profile: ProfileView
    distance_km: float = field(repr=False)

    @classmethod
    def between(cls, viewer: ProfileView, profile: ProfileView) -> "Candidate":
        """Build a candidate whose distance is measured between the two cell centres.

        :param viewer: The viewer.
        :param profile: The candidate profile.
        :return: The candidate with the haversine distance of the cells.
        """
        return cls(profile=profile, distance_km=haversine_km(viewer.cell, profile.cell))

    @property
    def distance_band(self) -> DistanceBand:
        """Band of the distance, the only form that may be shown."""
        return band_for(self.distance_km)


@dataclass(frozen=True, slots=True)
class Breakdown:
    """Points of each criterion (0.1 resolution) and the coarse functional level.

    The numeric functional contribution is not part of the breakdown on purpose: only its
    level may be shown.

    :param sport: Points for common sports.
    :param distance: Points for proximity (by band).
    :param intensity: Points for closeness of intensity.
    :param functional_level: Coarse functional compatibility.
    :param total: Score of the baseline formula, 0 to 100, in tenths. It is the sum of the three
        shown criteria and the functional contribution, which is never shown on its own.
    """

    sport: float
    distance: float
    intensity: float
    functional_level: FunctionalLevel
    total: float


@dataclass(frozen=True, slots=True)
class Scored:
    """A candidate with its score and the reasons for it.

    :param candidate: The scored candidate.
    :param score: Value that orders the candidates of one list. For the baseline it is the
        score from 0 to 100; for a learned ranker it is a raw, uncalibrated model score that may
        be negative and must never be shown as a percentage.
    :param breakdown: Contribution of each criterion according to the baseline formula.
    :param rank_influence: Effect of each criterion on the position in a learned ranking, or
        None for the baseline. The mapping is read-only.
    """

    candidate: Candidate
    score: float
    breakdown: Breakdown
    rank_influence: Mapping[Criterion, RankInfluence] | None = None

    def __post_init__(self) -> None:
        """Replace the influence mapping by a read-only copy."""
        if self.rank_influence is not None:
            # frozen=True forbids plain assignment; the copy keeps the object immutable
            object.__setattr__(self, "rank_influence", MappingProxyType(dict(self.rank_influence)))


class Scorer(Protocol):
    """Port of a scoring strategy: the weighted baseline or a learned ranker.

    Implementations must be pure with respect to their inputs: the same viewer and
    candidates give the same result, whatever the order of the candidates.
    """

    name: str
    version: str
    rank_source: RankSource

    def score(self, viewer: ProfileView, candidates: Sequence[Candidate]) -> list[Scored]:
        """Score every candidate for the viewer, in the order given.

        :param viewer: The viewer.
        :param candidates: Candidates to score.
        :return: One result per candidate, in the same order.
        """
        ...

    def keeps(self, scored: Scored) -> bool:
        """Tell whether a scored candidate may appear in the feed.

        The rule belongs to the scorer because the meaning of the score does: for the baseline a
        score of 0 means "nothing in common", while a learned score is relative and may be
        negative for a perfectly good candidate.

        :param scored: A result of this scorer.
        :return: True if the candidate stays in the feed.
        """
        ...
