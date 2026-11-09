"""Tests of the coarse pair features used by the learned ranker."""

import ast
import dataclasses
import inspect
from fractions import Fraction

from hypothesis import given

from app.domain.functional import FunctionalLevel
from app.domain.matching import features as features_module
from app.domain.matching.features import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    PairFeatures,
    pair_features,
)
from app.domain.matching.scorer import Candidate
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_TABLES, DEFAULT_WEIGHTS, ScoringTables, Weights
from app.domain.privacy import DistanceBand
from app.domain.taxonomy import SkillLevel
from tests.unit.domain.builders import CENTER_LAT, make_profile
from tests.unit.domain.strategies import profiles

EXPECTED_NAMES = (
    "n_shared_sports",
    "sport_jaccard",
    "min_skill_gap_shared",
    "viewer_n_sports",
    "cand_n_sports",
    "distance_band",
    "viewer_intensity",
    "cand_intensity",
    "intensity_diff_signed",
    "intensity_diff_abs",
    "functional_level",
)


def features_of(viewer, other) -> PairFeatures:
    """Compute the features of a pair, measuring the distance between the cells."""
    return pair_features(viewer, Candidate.between(viewer, other))


def baseline_from_features(
    f: PairFeatures, weights: Weights = DEFAULT_WEIGHTS, tables: ScoringTables = DEFAULT_TABLES
) -> float:
    """Recompute the weighted score from the features alone, independently of the scorer."""
    if f.n_shared_sports == 0:
        return 0.0
    union = f.viewer_n_sports + f.cand_n_sports - f.n_shared_sports
    band = list(DistanceBand)[f.distance_band]
    level = list(FunctionalLevel)[f.functional_level]
    parts = [
        (weights.sport, Fraction(f.n_shared_sports, union)),
        (weights.distance, tables.distance_share[band]),
        (weights.intensity, 1 - Fraction(f.intensity_diff_abs, 4)),
        (weights.functional, tables.functional_share[level]),
    ]
    return sum(round(Fraction(w * 10) * share) for w, share in parts) / 10


def test_feature_names_are_fixed_and_match_the_dataclass_fields():
    assert FEATURE_NAMES == EXPECTED_NAMES
    assert tuple(f.name for f in dataclasses.fields(PairFeatures)) == FEATURE_NAMES


def test_schema_version_is_a_positive_integer():
    assert isinstance(FEATURE_SCHEMA_VERSION, int)
    assert FEATURE_SCHEMA_VERSION >= 1


def test_features_of_a_known_pair():
    # Golden: pins the definition of every feature
    viewer = make_profile(
        1, [("swimming", SkillLevel.BEGINNER), ("archery", SkillLevel.ADVANCED)], intensity=2
    )
    other = make_profile(
        2,
        [("swimming", SkillLevel.ADVANCED), ("archery", SkillLevel.ADVANCED), "rowing"],
        lat=CENTER_LAT + 0.07,
        intensity=5,
    )

    f = features_of(viewer, other)

    assert f == PairFeatures(
        n_shared_sports=2,
        sport_jaccard=2 / 3,
        min_skill_gap_shared=0,
        viewer_n_sports=2,
        cand_n_sports=3,
        distance_band=1,
        viewer_intensity=2,
        cand_intensity=5,
        intensity_diff_signed=3,
        intensity_diff_abs=3,
        functional_level=1,
    )


def test_min_skill_gap_is_the_smallest_gap_over_shared_sports():
    viewer = make_profile(1, [("swimming", "beginner"), ("archery", "beginner")])
    other = make_profile(2, [("swimming", "advanced"), ("archery", "intermediate")])
    assert features_of(viewer, other).min_skill_gap_shared == 1


def test_min_skill_gap_ignores_sports_that_are_not_shared():
    viewer = make_profile(1, [("swimming", "beginner"), ("archery", "beginner")])
    other = make_profile(2, [("swimming", "beginner"), ("rowing", "advanced")])
    assert features_of(viewer, other).min_skill_gap_shared == 0


def test_min_skill_gap_reaches_two_for_beginner_against_advanced():
    viewer = make_profile(1, [("swimming", "beginner")])
    other = make_profile(2, [("swimming", "advanced")])
    assert features_of(viewer, other).min_skill_gap_shared == 2


def test_signed_intensity_difference_is_candidate_minus_viewer():
    viewer, other = make_profile(1, intensity=4), make_profile(2, intensity=1)
    f = features_of(viewer, other)
    assert (f.intensity_diff_signed, f.intensity_diff_abs) == (-3, 3)


def test_distance_band_is_encoded_by_position():
    viewer = make_profile(1)
    near = features_of(viewer, make_profile(2))
    far = features_of(viewer, make_profile(3, lat=CENTER_LAT + 0.5))
    assert (near.distance_band, far.distance_band) == (0, 3)


def test_functional_level_is_encoded_by_rank():
    viewer = make_profile(1, caps=[("endurance", 4, None)])
    levels = [
        features_of(viewer, make_profile(2, caps=[("endurance", level, None)])).functional_level
        for level in (0, 2, 4)
    ]
    assert levels == [0, 1, 2]


def test_vector_follows_the_fixed_feature_order():
    viewer, other = make_profile(1), make_profile(2, intensity=5)
    f = features_of(viewer, other)
    assert f.as_vector() == tuple(float(getattr(f, name)) for name in FEATURE_NAMES)


def test_features_are_numbers_only():
    f = features_of(make_profile(1, caps=[("vision", 2, None)]), make_profile(2))
    for name in FEATURE_NAMES:
        value = getattr(f, name)
        assert isinstance(value, int | float)
        assert not isinstance(value, bool)


def test_whitelist_no_coordinate_id_name_or_district_enters_the_features():
    # Arrange: two worlds that differ in every excluded attribute but not in the features
    viewer_a = make_profile(1, ["swimming"], lat=50.45, lon=30.52, district="kyiv_podilskyi")
    viewer_b = make_profile(9, ["swimming"], lat=49.95, lon=30.00, district="kyiv_darnytskyi")
    cand_a = make_profile(2, ["swimming"], lat=50.47, lon=30.52, district="kyiv_obolonskyi")
    cand_b = make_profile(8, ["swimming"], lat=49.97, lon=30.00, district=None)

    # Act
    fa = pair_features(viewer_a, Candidate(cand_a, 2.2))
    fb = pair_features(viewer_b, Candidate(cand_b, 2.2))

    # Assert
    assert fa == fb


def test_features_module_never_reads_private_or_identifying_attributes():
    forbidden = {"latitude", "longitude", "cell", "district", "id", "capabilities", "equipment"}
    tree = ast.parse(inspect.getsource(features_module))
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attributes & forbidden


def test_features_do_not_change_when_private_values_change_within_a_level():
    # Arrange: the level gap changes (0 vs 1 against 4), but both stay LOW
    viewer = make_profile(1, caps=[("mobility_lower", 4, None), ("endurance", 4, None)])
    low_a = make_profile(2, caps=[("mobility_lower", 0, None), ("endurance", 0, None)])
    low_b = make_profile(2, caps=[("mobility_lower", 1, "handcycle"), ("endurance", 0, None)])
    assert features_of(viewer, low_a).functional_level == 0

    # Act / Assert
    assert features_of(viewer, low_a) == features_of(viewer, low_b)


def test_features_change_when_the_functional_level_changes():
    viewer = make_profile(1, caps=[("endurance", 4, None)])
    low = make_profile(2, caps=[("endurance", 0, None)])
    high = make_profile(2, caps=[("endurance", 4, None)])
    assert features_of(viewer, low) != features_of(viewer, high)


def test_pair_without_shared_sport_has_zero_overlap_features():
    f = features_of(make_profile(1, ["swimming"]), make_profile(2, ["archery"]))
    assert (f.n_shared_sports, f.sport_jaccard, f.min_skill_gap_shared) == (0, 0.0, 0)


def test_baseline_derived_from_features_equals_the_weighted_scorer_on_a_known_pair():
    viewer = make_profile(1, ["swimming", "archery"], intensity=2, caps=[("vision", 3, None)])
    other = make_profile(
        2, ["swimming"], lat=CENTER_LAT + 0.1, intensity=4, caps=[("vision", 1, None)]
    )
    scorer = WeightedScorer(DEFAULT_WEIGHTS)
    scored = scorer.score(viewer, [Candidate.between(viewer, other)])[0]
    assert baseline_from_features(features_of(viewer, other)) == scored.score


@given(profiles(number=1), profiles(number=2))
def test_baseline_derived_from_features_equals_the_weighted_scorer(viewer, other):
    # The features carry everything the baseline uses, so a learned model on them can at
    # least reproduce the baseline
    scorer = WeightedScorer(DEFAULT_WEIGHTS)
    scored = scorer.score(viewer, [Candidate.between(viewer, other)])[0]
    assert baseline_from_features(features_of(viewer, other)) == scored.score


@given(profiles(number=1), profiles(number=2))
def test_feature_ranges(viewer, other):
    f = features_of(viewer, other)
    assert 0 <= f.n_shared_sports <= min(f.viewer_n_sports, f.cand_n_sports)
    assert 0.0 <= f.sport_jaccard <= 1.0
    assert 0 <= f.min_skill_gap_shared <= 2
    assert 0 <= f.distance_band <= 3
    assert 1 <= f.viewer_intensity <= 5
    assert 1 <= f.cand_intensity <= 5
    assert f.intensity_diff_abs == abs(f.intensity_diff_signed)
    assert f.functional_level in (0, 1, 2)
