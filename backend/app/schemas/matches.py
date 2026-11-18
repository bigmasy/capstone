"""Response models of the matching feed.

An item holds the public profile fields, the distance as a band, the baseline breakdown and, for
a learned ranking, the qualitative influence of each criterion. It deliberately has no
coordinate, no exact distance, no capability or equipment, no numeric functional contribution
and no raw learned score: the functional criterion appears only as the level low, medium or high.
"""

from enum import IntEnum
from typing import Self

from pydantic import BaseModel, ConfigDict

from app.domain.functional import FunctionalLevel
from app.domain.matching.scorer import Criterion, RankInfluence, RankSource
from app.domain.matching.source import MatchEntry, MatchPage
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.privacy import DistanceBand
from app.schemas.profiles import ProfilePublic, SportItem


class SearchRadius(IntEnum):
    """Search radius a caller may ask for: one of the distance bands of the API, in kilometres."""

    WITHIN_5_KM = 5
    WITHIN_10_KM = 10
    WITHIN_25_KM = 25


class MatchBreakdown(BaseModel):
    """Points of each criterion of the baseline formula, with 0.1 resolution.

    ``functional`` is a level, not points. ``total`` is the baseline score from 0 to 100; it is
    shown even when a learned ranker ordered the feed, so it need not decrease down the list.
    """

    model_config = ConfigDict(from_attributes=True)

    sport: float
    distance: float
    intensity: float
    functional: FunctionalLevel
    total: float


class MatchMaxPoints(BaseModel):
    """Highest points of the criteria whose points are shown, from the default baseline weights.

    There is deliberately no entry for the functional criterion: it is reported as a level only,
    and a number next to it would invite reading its points back out of the total.
    """

    sport: int
    distance: int
    intensity: int

    @classmethod
    def from_default_weights(cls) -> Self:
        """Build the maxima from the weights of the baseline formula.

        :return: The maxima of the sport, distance and intensity criteria.
        """
        return cls(
            sport=DEFAULT_WEIGHTS.sport,
            distance=DEFAULT_WEIGHTS.distance,
            intensity=DEFAULT_WEIGHTS.intensity,
        )


class MatchRankInfluence(BaseModel):
    """How each criterion moved a candidate in a learned ranking, compared with the others."""

    model_config = ConfigDict(from_attributes=True)

    sport: RankInfluence
    distance: RankInfluence
    functional: RankInfluence
    intensity: RankInfluence


class MatchItem(ProfilePublic):
    """A candidate in the feed: public fields plus the reasons for the position."""

    distance_band: DistanceBand
    breakdown: MatchBreakdown
    rank_source: RankSource
    rank_influence: MatchRankInfluence | None

    @classmethod
    def from_entry(cls, entry: MatchEntry, rank_source: RankSource) -> Self:
        """Build an item from a feed entry.

        :param entry: The scored candidate with its public name.
        :param rank_source: Strategy that ordered the feed.
        :return: The response item; the learned score is not part of it.
        """
        scored = entry.scored
        profile = scored.candidate.profile
        breakdown = scored.breakdown
        influence = scored.rank_influence
        return cls(
            id=profile.id,
            display_name=entry.display_name,
            has_photo=entry.has_photo,
            district_code=profile.district,
            intensity=profile.intensity,
            sports=[
                SportItem(sport=item.sport, skill=item.skill)
                for item in sorted(profile.sports, key=lambda item: item.sport.value)
            ],
            distance_band=scored.candidate.distance_band,
            breakdown=MatchBreakdown(
                sport=breakdown.sport,
                distance=breakdown.distance,
                intensity=breakdown.intensity,
                functional=breakdown.functional_level,
                total=breakdown.total,
            ),
            rank_source=rank_source,
            rank_influence=(
                None
                if influence is None
                else MatchRankInfluence(
                    sport=influence[Criterion.SPORT],
                    distance=influence[Criterion.DISTANCE],
                    functional=influence[Criterion.FUNCTIONAL],
                    intensity=influence[Criterion.INTENSITY],
                )
            ),
        )


class MatchFeed(BaseModel):
    """One page of the caller's feed.

    ``total`` is the length of the whole ranked feed (at most the configured maximum), so a
    client can tell whether another page exists. ``max_points`` are the denominators of the
    points in every item's breakdown.
    """

    items: list[MatchItem]
    skip: int
    limit: int
    total: int
    max_points: MatchMaxPoints

    @classmethod
    def from_page(cls, page: MatchPage) -> Self:
        """Build the response from a page of the feed.

        :param page: The page returned by the matching service.
        :return: The response model.
        """
        return cls(
            items=[MatchItem.from_entry(entry, page.rank_source) for entry in page.entries],
            skip=page.skip,
            limit=page.limit,
            total=page.total,
            max_points=MatchMaxPoints.from_default_weights(),
        )
