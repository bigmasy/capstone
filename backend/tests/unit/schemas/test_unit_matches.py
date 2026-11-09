"""Tests of the matching feed response models."""

import json

import pytest

from app.domain.functional import FunctionalLevel
from app.domain.matching.scorer import (
    Breakdown,
    Candidate,
    Criterion,
    RankInfluence,
    RankSource,
    Scored,
)
from app.domain.matching.source import MatchEntry, MatchPage
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.privacy import BAND_LIMITS_KM
from app.schemas.matches import MatchFeed, MatchItem, SearchRadius
from tests.unit.domain.builders import make_profile

BREAKDOWN = Breakdown(21.4, 20.0, 11.2, FunctionalLevel.HIGH, 77.6)


def entry(rank_influence=None, score=77.6, distance_km=7.3456) -> MatchEntry:
    candidate = Candidate(
        make_profile(2, ["swimming", "archery"], caps=[("vision", 4, None)]), distance_km
    )
    return MatchEntry("Orest", Scored(candidate, score, BREAKDOWN, rank_influence))


def test_the_search_radii_are_the_distance_bands_of_the_api():
    assert tuple(SearchRadius) == BAND_LIMITS_KM


def test_a_baseline_item_has_the_breakdown_and_no_influence():
    item = MatchItem.from_entry(entry(), RankSource.BASELINE)

    assert item.breakdown.total == 77.6
    assert item.breakdown.functional is FunctionalLevel.HIGH
    assert item.rank_source is RankSource.BASELINE
    assert item.rank_influence is None
    assert item.distance_band.value == "5–10 km"
    assert [s.sport.value for s in item.sports] == ["archery", "swimming"]


def test_a_learned_item_carries_one_qualitative_influence_per_criterion():
    influence = {
        Criterion.SPORT: RankInfluence.RAISES,
        Criterion.DISTANCE: RankInfluence.LOWERS,
        Criterion.FUNCTIONAL: RankInfluence.NEUTRAL,
        Criterion.INTENSITY: RankInfluence.RAISES,
    }

    item = MatchItem.from_entry(entry(influence, score=-1.37), RankSource.LEARNED)

    assert item.rank_influence is not None
    assert item.rank_influence.model_dump(mode="json") == {
        "sport": "raises",
        "distance": "lowers",
        "functional": "neutral",
        "intensity": "raises",
    }


@pytest.mark.parametrize("score", [-1.3719, 0.8421, 123.4567])
def test_the_raw_score_and_the_exact_distance_are_not_serialised(score):
    influence = {c: RankInfluence.NEUTRAL for c in Criterion}
    page = MatchPage(
        [entry(influence, score=score)], skip=0, limit=20, total=1, rank_source=RankSource.LEARNED
    )

    text = json.dumps(MatchFeed.from_page(page).model_dump(mode="json"))

    assert str(score) not in text
    assert "7.3456" not in text
    assert "capabil" not in text and "vision" not in text


def test_the_page_metadata_is_copied():
    page = MatchPage([entry()], skip=5, limit=10, total=42, rank_source=RankSource.BASELINE)

    feed = MatchFeed.from_page(page)

    assert (feed.skip, feed.limit, feed.total, len(feed.items)) == (5, 10, 42, 1)


def test_the_feed_carries_the_maxima_of_the_shown_criteria_from_the_default_weights():
    page = MatchPage([], skip=0, limit=20, total=0, rank_source=RankSource.BASELINE)

    feed = MatchFeed.from_page(page)

    assert feed.max_points.model_dump() == {
        "sport": DEFAULT_WEIGHTS.sport,
        "distance": DEFAULT_WEIGHTS.distance,
        "intensity": DEFAULT_WEIGHTS.intensity,
    }


def test_the_maxima_have_no_functional_entry_and_leave_the_shown_points_within_bounds():
    feed = MatchFeed.from_page(
        MatchPage([entry()], skip=0, limit=20, total=1, rank_source=RankSource.BASELINE)
    )

    assert set(feed.max_points.model_dump()) == {"sport", "distance", "intensity"}
    breakdown = feed.items[0].breakdown
    for name, maximum in feed.max_points.model_dump().items():
        assert 0 <= getattr(breakdown, name) <= maximum
