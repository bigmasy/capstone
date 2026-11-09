"""The weighted baseline scorer: a score from 0 to 100 with a per-criterion breakdown."""

from collections.abc import Sequence
from fractions import Fraction

from app.domain.functional import FunctionalLevel, functional_level
from app.domain.matching.scorer import Breakdown, Candidate, RankSource, Scored
from app.domain.matching.weights import DEFAULT_TABLES, ScoringTables, Weights
from app.domain.profile import ProfileView
from app.domain.taxonomy import MAX_INTENSITY, MIN_INTENSITY

_INTENSITY_RANGE = MAX_INTENSITY - MIN_INTENSITY
_NO_MATCH = Breakdown(
    sport=0.0, distance=0.0, intensity=0.0, functional_level=FunctionalLevel.LOW, total=0.0
)


def _tenths(weight: int, share: Fraction) -> int:
    """Points of a criterion in tenths; integers make the parts add up to the score exactly."""
    return round(Fraction(weight * 10) * share)


class WeightedScorer:
    """Baseline scorer: weighted sum of sport overlap, proximity, functional level, intensity.

    Every contribution is computed in exact rational arithmetic and rounded to integer
    tenths, so the parts add up to the score without floating-point error. A pair without a
    shared sport scores 0.

    :param weights: Points of each criterion.
    :param tables: Shares per distance band and functional level; defaults to the initial
        assumptions.
    """

    name = "weighted"
    version = "1.0.0"
    rank_source = RankSource.BASELINE

    def __init__(self, weights: Weights, tables: ScoringTables = DEFAULT_TABLES) -> None:
        """Create a scorer with the given weights and share tables."""
        self._weights = weights
        self._tables = tables

    def score(self, viewer: ProfileView, candidates: Sequence[Candidate]) -> list[Scored]:
        """Score every candidate for the viewer, in the order given.

        :param viewer: The viewer.
        :param candidates: Candidates to score.
        :return: One result per candidate, in the same order.
        """
        return [self._score_one(viewer, candidate) for candidate in candidates]

    def _score_one(self, viewer: ProfileView, candidate: Candidate) -> Scored:
        """Score one candidate; zero without a shared sport."""
        profile = candidate.profile
        mine, theirs = viewer.sport_codes, profile.sport_codes
        shared = mine & theirs
        if not shared:
            return Scored(candidate=candidate, score=0.0, breakdown=_NO_MATCH)
        level = functional_level(viewer.functional, profile.functional)
        weights, tables = self._weights, self._tables
        sport = _tenths(weights.sport, Fraction(len(shared), len(mine | theirs)))
        distance = _tenths(weights.distance, tables.distance_share[candidate.distance_band])
        gap = abs(viewer.intensity - profile.intensity)
        intensity = _tenths(weights.intensity, 1 - Fraction(gap, _INTENSITY_RANGE))
        functional = _tenths(weights.functional, tables.functional_share[level])
        total = sport + distance + intensity + functional
        breakdown = Breakdown(
            sport=sport / 10,
            distance=distance / 10,
            intensity=intensity / 10,
            functional_level=level,
            total=total / 10,
        )
        return Scored(candidate=candidate, score=total / 10, breakdown=breakdown)

    def keeps(self, scored: Scored) -> bool:
        """Keep a candidate only if the baseline score is positive.

        :param scored: A result of this scorer.
        :return: True if the score is above 0, that is, if a sport is shared.
        """
        return scored.score > 0
