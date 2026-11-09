"""Tests of the feed: eligibility of candidates and deterministic ordering."""

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.functional import FunctionalLevel
from app.domain.matching.feed import eligible_candidates, rank, shield_functional
from app.domain.matching.scorer import Breakdown, Candidate, Criterion, RankInfluence, Scored
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from tests.unit.domain.builders import make_id, make_profile
from tests.unit.domain.strategies import profile_pools

SCORER = WeightedScorer(DEFAULT_WEIGHTS)
EMPTY = Breakdown(0.0, 0.0, 0.0, FunctionalLevel.LOW, 0.0)


def scored(number: int, score: float) -> Scored:
    """Build a scored entry with a given id and score."""
    candidate = Candidate(make_profile(number), distance_km=0.0)
    return Scored(candidate=candidate, score=score, breakdown=EMPTY)


def ids(entries: list[Scored]) -> list:
    """Return the profile ids of scored entries."""
    return [entry.candidate.profile.id for entry in entries]


def feed_for(viewer, pool, limit=100):
    """Run the full feed: eligibility, scoring, ranking."""
    candidates = eligible_candidates(viewer, pool)
    return rank(SCORER.score(viewer, candidates), limit, SCORER.keeps)


def test_eligible_candidates_exclude_self_hidden_and_unrelated():
    me = make_profile(1, ["swimming"])
    best = make_profile(2, ["swimming"])
    worse = make_profile(3, ["swimming", "archery"], intensity=1)
    hidden = make_profile(4, ["swimming"], visible=False)
    other = make_profile(5, ["archery"])

    result = eligible_candidates(me, [me, best, worse, hidden, other])

    assert [c.profile.id for c in result] == [best.id, worse.id]


def test_eligible_candidates_carry_the_distance_between_cells():
    me = make_profile(1, lat=50.45)
    other = make_profile(2, lat=50.46)
    (candidate,) = eligible_candidates(me, [other])
    assert candidate.distance_km == pytest.approx(1.11, abs=0.01)


def test_eligible_candidates_of_nothing_is_nothing():
    me = make_profile(1)
    assert eligible_candidates(me, []) == []
    assert eligible_candidates(me, [me]) == []


def test_rank_orders_by_descending_score():
    entries = [scored(1, 50.0), scored(2, 90.0), scored(3, 70.0)]
    assert ids(rank(entries, 10)) == [make_id(2), make_id(3), make_id(1)]


def test_rank_applies_the_keep_rule_of_the_baseline_scorer():
    entries = [scored(1, 0.0), scored(2, 10.0), scored(3, -1.0)]
    assert ids(rank(entries, 10, SCORER.keeps)) == [make_id(2)]


def test_rank_keeps_negative_scores_when_the_scorer_says_so():
    entries = [scored(1, -2.0), scored(2, 1.5), scored(3, -0.5)]
    assert ids(rank(entries, 10, lambda _: True)) == [make_id(2), make_id(3), make_id(1)]


def test_rank_without_a_rule_drops_nothing():
    entries = [scored(1, 0.0), scored(2, -1.0)]
    assert ids(rank(entries, 10)) == [make_id(1), make_id(2)]


def test_equal_scores_are_ordered_by_id():
    entries = [scored(n, 80.0) for n in (3, 1, 4, 2)]
    assert ids(rank(entries, 10)) == [make_id(n) for n in (1, 2, 3, 4)]
    assert ids(rank(list(reversed(entries)), 10)) == [make_id(n) for n in (1, 2, 3, 4)]


def test_limit_applies_after_ordering():
    entries = [scored(n, 10.0 * n) for n in range(1, 6)]
    assert ids(rank(entries, 2)) == [make_id(5), make_id(4)]


def test_limit_zero_gives_an_empty_feed_and_negative_limit_is_rejected():
    assert rank([scored(1, 10.0)], 0) == []
    with pytest.raises(ValueError, match="limit"):
        rank([scored(1, 10.0)], -1)


def test_rank_does_not_modify_its_input():
    entries = [scored(2, 10.0), scored(1, 20.0)]
    snapshot = list(entries)
    rank(entries, 10)
    assert entries == snapshot


def test_feed_edge_cases():
    me = make_profile(1)
    assert feed_for(me, []) == []
    assert feed_for(me, [me]) == []
    hidden = [make_profile(10 + i, visible=False) for i in range(3)]
    assert feed_for(me, hidden) == []
    unrelated = [make_profile(20 + i, ["archery"]) for i in range(3)]
    assert feed_for(me, unrelated) == []
    pool = [make_profile(30 + i) for i in range(3)]
    assert len(feed_for(me, pool, limit=50)) == 3
    assert ids(feed_for(me, pool, limit=1)) == [make_id(30)]


def test_far_candidates_stay_in_the_feed_when_a_sport_is_shared():
    me = make_profile(1)
    # About 110 km away: a binary distance filter would drop it, the continuous list keeps it
    far = make_profile(2, lat=51.45)
    (entry,) = feed_for(me, [far])
    assert entry.candidate.distance_km > 25
    assert entry.breakdown.distance == 0
    assert entry.score > 0


@given(profile_pools(), st.randoms(use_true_random=False))
def test_feed_does_not_depend_on_the_order_of_candidates(pool, rng):
    # Arrange
    if not pool:
        return
    viewer = dataclasses.replace(pool[0], is_visible=True)
    expected = ids(feed_for(viewer, pool))
    shuffled = list(pool)
    rng.shuffle(shuffled)

    # Act
    actual = ids(feed_for(viewer, shuffled))

    # Assert
    assert actual == expected


@given(profile_pools())
def test_feed_holds_only_visible_other_profiles_sharing_a_sport(pool):
    if not pool:
        return
    viewer = pool[0]
    for entry in feed_for(viewer, pool):
        other = entry.candidate.profile
        assert other.id != viewer.id
        assert other.is_visible
        assert other.sport_codes & viewer.sport_codes
        assert entry.score > 0


@given(profile_pools())
def test_feed_is_sorted_by_descending_score_then_id(pool):
    if not pool:
        return
    feed = feed_for(pool[0], pool)
    keys = [(-entry.score, entry.candidate.profile.id) for entry in feed]
    assert keys == sorted(keys)


def test_candidate_representation_hides_the_distance_and_the_location():
    candidate = Candidate(make_profile(1), distance_km=12.3456)

    text = repr(candidate)

    assert "12.3456" not in text
    assert "distance" not in text
    assert str(candidate.profile.cell.latitude) not in text


def functional_level_of(viewer, other):
    """Functional level shown for a pair after the shared-categories rule."""
    candidate = shield_functional(viewer, Candidate.between(viewer, other))
    return SCORER.score(viewer, [candidate])[0].breakdown.functional_level


def test_one_shared_category_gives_the_neutral_level_whatever_the_candidate_declared():
    me = make_profile(1, caps=[("vision", 4, None), ("hearing", 4, None)])
    low = make_profile(2, caps=[("vision", 0, None), ("endurance", 0, None)])
    high = make_profile(3, caps=[("vision", 4, None), ("endurance", 4, None)])

    assert functional_level_of(me, low) is FunctionalLevel.MEDIUM
    assert functional_level_of(me, high) is FunctionalLevel.MEDIUM


def test_two_shared_categories_allow_the_real_level():
    me = make_profile(1, caps=[("vision", 4, None), ("hearing", 4, None)])
    low = make_profile(2, caps=[("vision", 0, None), ("hearing", 0, None)])
    high = make_profile(3, caps=[("vision", 4, None), ("hearing", 4, None)])

    assert functional_level_of(me, low) is FunctionalLevel.LOW
    assert functional_level_of(me, high) is FunctionalLevel.HIGH


def test_shielding_keeps_the_candidate_in_the_feed_and_the_distance():
    me = make_profile(1, caps=[("vision", 4, None)])
    other = make_profile(2, lat=50.46, caps=[("vision", 0, None)])
    candidate = Candidate.between(me, other)

    shielded = shield_functional(me, candidate)

    assert shielded.profile.id == other.id
    assert shielded.distance_km == candidate.distance_km
    assert shielded.profile.functional.capabilities == frozenset()


def test_shielding_leaves_a_viewer_without_functional_data_unchanged():
    me = make_profile(1)
    other = make_profile(2, caps=[("vision", 0, None)])

    assert functional_level_of(me, other) is FunctionalLevel.MEDIUM


def test_scored_makes_the_influence_mapping_read_only():
    candidate = Candidate(make_profile(1), distance_km=0.0)
    source = {c: RankInfluence.NEUTRAL for c in Criterion}

    entry = Scored(candidate, 1.0, EMPTY, rank_influence=source)
    source[Criterion.SPORT] = RankInfluence.RAISES

    assert entry.rank_influence[Criterion.SPORT] is RankInfluence.NEUTRAL
    with pytest.raises(TypeError):
        entry.rank_influence[Criterion.SPORT] = RankInfluence.LOWERS  # type: ignore[index]
