"""Tests of the weighted baseline scorer."""

from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.functional import FunctionalLevel
from app.domain.matching.scorer import Candidate, RankSource, Scored, Scorer
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_TABLES, DEFAULT_WEIGHTS, ScoringTables, Weights
from app.domain.privacy import BAND_LIMITS_KM, DistanceBand, band_for
from app.domain.taxonomy import CATEGORIES, SPORTS
from tests.unit.domain.builders import CENTER_LAT, make_profile
from tests.unit.domain.strategies import profiles

CATEGORY_CODES = [c.code for c in CATEGORIES]
LEVEL_ORDER = [FunctionalLevel.LOW, FunctionalLevel.MEDIUM, FunctionalLevel.HIGH]
SCORER = WeightedScorer(DEFAULT_WEIGHTS)
W = DEFAULT_WEIGHTS


def explain(viewer, other, scorer=SCORER) -> Scored:
    """Score one pair, measuring the distance between the cells."""
    return scorer.score(viewer, [Candidate.between(viewer, other)])[0]


def tenths(points: float) -> int:
    """Convert points to integer tenths."""
    return round(points * 10)


def parts_in_tenths(result: Scored) -> int:
    """Sum the parts of a breakdown in tenths, adding the points of the functional level."""
    b = result.breakdown
    functional = W.functional * 10 * DEFAULT_TABLES.functional_share[b.functional_level]
    return tenths(b.sport) + tenths(b.distance) + tenths(b.intensity) + round(functional)


def test_weighted_scorer_satisfies_the_scorer_port():
    scorer: Scorer = WeightedScorer(DEFAULT_WEIGHTS)
    assert scorer.name == "weighted"
    assert scorer.version
    assert scorer.rank_source is RankSource.BASELINE


def test_the_baseline_keeps_only_positive_scores():
    viewer = make_profile(1, ["swimming"])
    shared = explain(viewer, make_profile(2, ["swimming"]))
    nothing = explain(viewer, make_profile(3, ["archery"]))

    assert SCORER.keeps(shared)
    assert not SCORER.keeps(nothing)


def test_the_breakdown_total_equals_the_score():
    viewer = make_profile(1, ["swimming", "archery"], intensity=2)
    result = explain(viewer, make_profile(2, ["swimming"], intensity=4, lat=CENTER_LAT + 0.1))

    assert result.breakdown.total == result.score
    assert 0 < result.breakdown.total < 100


def test_score_returns_one_result_per_candidate_in_the_given_order():
    viewer = make_profile(1)
    others = [make_profile(n) for n in (5, 3, 4)]
    result = SCORER.score(viewer, [Candidate.between(viewer, o) for o in others])
    assert [r.candidate.profile.id for r in result] == [o.id for o in others]


def test_empty_candidate_list_gives_empty_result():
    assert SCORER.score(make_profile(1), []) == []


def test_no_shared_sport_gives_zero_with_empty_breakdown():
    a, b = make_profile(1, ["swimming"]), make_profile(2, ["archery"])
    result = explain(a, b)
    assert result.score == 0
    assert (result.breakdown.sport, result.breakdown.distance, result.breakdown.intensity) == (
        0,
        0,
        0,
    )
    assert result.rank_influence is None


def test_identical_profiles_give_maximum():
    caps = [("mobility_lower", 2, "wheelchair_active")]
    a, b = make_profile(1, caps=caps), make_profile(2, caps=caps)
    assert explain(a, b).score == 100


def test_pair_without_capabilities_scores_with_neutral_functional_part():
    # Golden: no comparable functional data counts as medium, half of the functional weight
    result = explain(make_profile(1), make_profile(2))
    assert result.breakdown.functional_level is FunctionalLevel.MEDIUM
    assert result.score == 100 - W.functional / 2 == 87.5


def test_score_decreases_with_distance():
    me = make_profile(1)
    near = make_profile(2, lat=CENTER_LAT + 0.01)
    far = make_profile(3, lat=CENTER_LAT + 0.15)
    assert explain(me, near).score > explain(me, far).score


def test_score_decreases_with_intensity_gap():
    me = make_profile(1, intensity=3)
    close = make_profile(2, intensity=3)
    gap = make_profile(3, intensity=5)
    assert explain(me, close).score > explain(me, gap).score


def test_distance_part_is_zero_beyond_the_last_band_but_other_parts_remain():
    caps = [("mobility_lower", 2, "wheelchair_active")]
    me = make_profile(1, caps=caps)
    # 0.5 degrees of latitude is about 55 km, more than the last band limit
    far = make_profile(2, lat=CENTER_LAT + 0.5, caps=caps)
    result = explain(me, far)
    assert result.candidate.distance_km >= BAND_LIMITS_KM[-1]
    assert result.breakdown.distance == 0
    # Golden: sport + intensity + functional weights
    assert result.score == W.sport + W.intensity + W.functional == 70


def test_distance_part_is_full_in_the_same_cell():
    result = explain(make_profile(1), make_profile(2))
    assert result.candidate.distance_km == 0
    assert result.breakdown.distance == W.distance


@pytest.mark.parametrize("limit", BAND_LIMITS_KM)
def test_distance_part_changes_exactly_at_a_band_limit(limit):
    me = make_profile(1)
    other = make_profile(2)
    just_below = SCORER.score(me, [Candidate(other, limit - 1e-9)])[0]
    at_limit = SCORER.score(me, [Candidate(other, limit)])[0]
    assert just_below.breakdown.distance > at_limit.breakdown.distance


def test_intensity_extremes():
    one, five = make_profile(1, intensity=1), make_profile(2, intensity=5)
    assert explain(one, five).breakdown.intensity == 0
    assert explain(one, make_profile(3, intensity=1)).breakdown.intensity == W.intensity


def test_one_sport_against_ten_sports():
    ten = [s.code for s in SPORTS[:10]]
    result = explain(make_profile(1, ["swimming"]), make_profile(2, ten))
    assert result.breakdown.sport == W.sport / 10


def test_sport_part_never_decreases_with_larger_overlap():
    mine = [s.code for s in SPORTS[:4]]
    others = [s.code for s in SPORTS[4:8]]
    me = make_profile(1, mine)
    parts = [
        explain(me, make_profile(2, mine[:shared] + others[: 4 - shared])).breakdown.sport
        for shared in range(1, 5)
    ]
    assert parts == sorted(parts)
    assert parts[-1] == W.sport


def test_skill_levels_do_not_change_the_baseline_score():
    # The baseline compares sports by code only; skill is a feature for the learned ranker
    me = make_profile(1, [("swimming", "beginner")])
    other = make_profile(2, [("swimming", "advanced")])
    twin = make_profile(3, [("swimming", "beginner")])
    assert explain(me, other).score == explain(me, twin).score


@pytest.mark.parametrize("category", CATEGORY_CODES)
def test_functional_level_never_drops_when_candidate_moves_toward_viewer(category):
    me = make_profile(1, caps=[(category, 4, None)])
    levels = [
        explain(me, make_profile(2, caps=[(category, level, None)])).breakdown.functional_level
        for level in range(5)
    ]
    ranks = [LEVEL_ORDER.index(level) for level in levels]
    assert ranks == sorted(ranks)
    assert levels[0] is FunctionalLevel.LOW
    assert levels[-1] is FunctionalLevel.HIGH


def test_functional_data_changes_only_the_functional_part_and_the_score_by_its_points():
    me = make_profile(1, caps=[("endurance", 4, None)])
    close = make_profile(2, caps=[("endurance", 4, None)])
    far = make_profile(3, caps=[("endurance", 0, None)])
    rc, rf = explain(me, close), explain(me, far)
    assert (rc.breakdown.sport, rc.breakdown.distance, rc.breakdown.intensity) == (
        rf.breakdown.sport,
        rf.breakdown.distance,
        rf.breakdown.intensity,
    )
    assert rc.score - rf.score == pytest.approx(W.functional)


def test_viewer_with_all_categories_against_candidate_without_any_is_neutral():
    me = make_profile(1, caps=[(c, 1, None) for c in CATEGORY_CODES])
    assert explain(me, make_profile(2)).breakdown.functional_level is FunctionalLevel.MEDIUM


def test_level_zero_against_four_in_every_category_is_low():
    me = make_profile(1, caps=[(c, 0, None) for c in CATEGORY_CODES])
    other = make_profile(2, caps=[(c, 4, None) for c in CATEGORY_CODES])
    assert explain(me, other).breakdown.functional_level is FunctionalLevel.LOW


def test_same_level_with_different_equipment_is_still_high():
    me = make_profile(1, caps=[("mobility_lower", 3, "handcycle")])
    other = make_profile(2, caps=[("mobility_lower", 3, "wheelchair_active")])
    assert explain(me, other).breakdown.functional_level is FunctionalLevel.HIGH


def test_score_takes_at_most_three_values_as_private_data_varies():
    # The score reveals no more of the functional data than the three-valued level
    me = make_profile(1, ["swimming", "archery"], caps=[("mobility_lower", 3, "wheelchair_active")])
    scores = set()
    for level_a in range(5):
        for level_b in range(5):
            caps = [("mobility_lower", level_a, None), ("vision", level_b, None)]
            scores.add(explain(me, make_profile(2, ["swimming"], intensity=2, caps=caps)).score)
    assert 1 < len(scores) <= 3


def test_two_probes_in_one_band_at_different_distances_are_indistinguishable():
    me = make_profile(1)
    # 0.05 and 0.07 degrees of latitude are about 5.6 km and 7.8 km, both in the 5-10 km band
    near = explain(me, make_profile(2, lat=CENTER_LAT + 0.05))
    farther = explain(me, make_profile(3, lat=CENTER_LAT + 0.07))
    assert near.candidate.distance_km != farther.candidate.distance_km
    assert near.candidate.distance_band is farther.candidate.distance_band
    assert near.candidate.distance_band is DistanceBand.FROM_5_TO_10_KM
    assert near.breakdown.distance == farther.breakdown.distance
    assert near.score == farther.score


def test_distance_points_depend_only_on_the_distance_band():
    me = make_profile(1)
    seen = set()
    for step in range(0, 90, 3):
        result = explain(me, make_profile(2, lat=CENTER_LAT + step * 0.01))
        band = band_for(result.candidate.distance_km)
        assert result.breakdown.distance == W.distance * float(DEFAULT_TABLES.distance_share[band])
        seen.add(result.breakdown.distance)
    assert len(seen) == len(DistanceBand)


def test_custom_weights_and_tables_are_used():
    weights = Weights(sport=100, distance=0, functional=0, intensity=0)
    scorer = WeightedScorer(weights)
    result = explain(make_profile(1), make_profile(2, intensity=5), scorer)
    assert result.score == 100
    tables = ScoringTables(
        distance_share={band: Fraction(1, 2) for band in DistanceBand},
        functional_share={level: Fraction(1) for level in FunctionalLevel},
    )
    half = WeightedScorer(DEFAULT_WEIGHTS, tables)
    assert explain(make_profile(1), make_profile(2), half).breakdown.distance == W.distance / 2


def test_scoring_ignores_the_order_of_sport_and_capability_entries():
    a = make_profile(
        1, ["swimming", "archery", "rowing"], caps=[("vision", 1, None), ("hearing", 2, None)]
    )
    b = make_profile(2, ["rowing", "swimming"], caps=[("hearing", 3, None), ("vision", 0, None)])
    reordered_a = make_profile(
        1, ["rowing", "archery", "swimming"], caps=[("hearing", 2, None), ("vision", 1, None)]
    )
    assert explain(a, b) == explain(reordered_a, b)


# Properties over generated profiles


@given(profiles(number=1), profiles(number=2))
def test_score_is_within_bounds_and_parts_are_within_weights(a, b):
    result = explain(a, b)
    assert 0 <= result.score <= 100
    p = result.breakdown
    assert 0 <= p.sport <= W.sport
    assert 0 <= p.distance <= W.distance
    assert 0 <= p.intensity <= W.intensity
    if a.sport_codes & b.sport_codes:
        assert result.score > 0


@given(profiles(number=1), profiles(number=2))
def test_parts_add_up_to_the_score_exactly_in_tenths(a, b):
    result = explain(a, b)
    if result.score == 0:
        assert (
            result.breakdown.sport == result.breakdown.distance == result.breakdown.intensity == 0
        )
    else:
        assert parts_in_tenths(result) == tenths(result.score)


@given(profiles(number=1), profiles(number=2))
def test_score_is_symmetric(a, b):
    ab, ba = explain(a, b), explain(b, a)
    assert ab.score == ba.score
    assert ab.breakdown == ba.breakdown


@given(profiles(number=1), profiles(number=2))
def test_no_shared_sport_always_gives_zero(a, b):
    if not a.sport_codes & b.sport_codes:
        assert explain(a, b).score == 0


@given(
    profiles(number=1),
    profiles(number=2),
    st.floats(min_value=0, max_value=60, allow_nan=False),
    st.floats(min_value=0, max_value=60, allow_nan=False),
)
def test_score_never_increases_with_distance(viewer, other, x, y):
    near, far = sorted((x, y))
    s_near = SCORER.score(viewer, [Candidate(other, near)])[0].score
    s_far = SCORER.score(viewer, [Candidate(other, far)])[0].score
    assert s_far <= s_near


@given(profiles(number=1), profiles(number=2), st.integers(1, 5), st.integers(1, 5))
def test_score_never_increases_with_intensity_gap(viewer, other, i, j):
    def with_intensity(value: int):
        return replace(other, intensity=value)

    gap_i, gap_j = abs(i - viewer.intensity), abs(j - viewer.intensity)
    score_i = explain(viewer, with_intensity(i)).score
    score_j = explain(viewer, with_intensity(j)).score
    if gap_i <= gap_j:
        assert score_i >= score_j
    else:
        assert score_i <= score_j


@given(profiles(number=1), profiles(number=2))
def test_sport_overlap_is_a_jaccard_share(a, b):
    shared = a.sport_codes & b.sport_codes
    result = explain(a, b)
    if shared:
        union = a.sport_codes | b.sport_codes
        assert tenths(result.breakdown.sport) == round(
            Fraction(W.sport * 10 * len(shared), len(union))
        )
