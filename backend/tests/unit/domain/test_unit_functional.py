"""Tests of the functional level of a pair of profiles."""

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.functional import (
    EQUIPMENT_SHARE,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    MIN_SHARED_CATEGORIES,
    FunctionalLevel,
    functional_level,
    has_enough_shared_categories,
    shield_insufficient_overlap,
    similarity_index,
)
from app.domain.profile import CapabilityEntry, FunctionalProfile
from app.domain.taxonomy import CATEGORIES, CategoryCode, EquipmentCode
from tests.unit.domain.builders import make_functional as caps

ALL = [c.code for c in CATEGORIES]


def test_identical_capabilities_give_maximum():
    a = caps(("mobility_lower", 2, "wheelchair_active"), ("endurance", 3, None))
    copy = caps(("mobility_lower", 2, "wheelchair_active"), ("endurance", 3, None))
    assert similarity_index(a, copy) == 1
    assert functional_level(a, copy) is FunctionalLevel.HIGH


def test_index_is_symmetric_over_all_level_pairs():
    for la in range(5):
        for lb in range(5):
            for ea, eb in [(None, None), ("handcycle", None), ("handcycle", "wheelchair_active")]:
                a, b = caps(("mobility_lower", la, ea)), caps(("mobility_lower", lb, eb))
                assert similarity_index(a, b) == similarity_index(b, a)
                assert functional_level(a, b) == functional_level(b, a)


@pytest.mark.parametrize("category", ALL)
def test_larger_level_gap_never_raises_the_index(category):
    base = caps((category, 4, None))
    indexes = [similarity_index(base, caps((category, level, None))) for level in (4, 3, 2, 1, 0)]
    assert indexes == sorted(indexes, reverse=True)
    assert indexes[0] == 1
    assert indexes[-1] == 0


def test_level_gap_of_every_category_spans_the_full_range():
    for category in ALL:
        low, high = caps((category, 0, None)), caps((category, 4, None))
        assert similarity_index(low, high) == 0
        assert functional_level(low, high) is FunctionalLevel.LOW


def test_same_equipment_is_not_worse_than_different_equipment():
    a = caps(("mobility_lower", 2, "wheelchair_active"))
    same = caps(("mobility_lower", 2, "wheelchair_active"))
    other = caps(("mobility_lower", 2, "handcycle"))
    assert similarity_index(a, same) > similarity_index(a, other)
    assert similarity_index(a, other) == 1 - EQUIPMENT_SHARE


def test_equipment_on_one_side_only_is_ignored():
    a = caps(("mobility_lower", 2, "wheelchair_active"))
    b = caps(("mobility_lower", 2, None))
    assert similarity_index(a, b) == 1
    assert similarity_index(b, a) == 1


def test_only_common_categories_are_compared():
    a = caps(("mobility_lower", 3, None), ("vision", 0, None))
    b = caps(("mobility_lower", 3, None), ("hearing", 4, None))
    assert similarity_index(a, b) == 1


@pytest.mark.parametrize(
    "a,b",
    [
        (caps(), caps()),
        (caps(), caps(("vision", 1, None))),
        (caps(("vision", 1, None)), caps()),
        (caps(("vision", 1, None)), caps(("hearing", 4, "hearing_aid"))),
    ],
    ids=["both-empty", "left-empty", "right-empty", "disjoint"],
)
def test_missing_comparable_data_is_neutral(a, b):
    assert similarity_index(a, b) is None
    assert functional_level(a, b) is FunctionalLevel.MEDIUM


def test_missing_data_cases_are_indistinguishable():
    viewer = caps(("vision", 1, None), ("endurance", 3, None))
    empty = functional_level(viewer, caps())
    disjoint = functional_level(viewer, caps(("hearing", 0, None), ("dexterity", 4, None)))
    assert empty == disjoint == FunctionalLevel.MEDIUM


def test_exact_thresholds_are_included_in_the_higher_level():
    # Two categories with similarities 1 and 1/2 give exactly 3/4
    a = caps(("endurance", 4, None), ("vision", 4, None))
    b = caps(("endurance", 4, None), ("vision", 2, None))
    assert similarity_index(a, b) == HIGH_THRESHOLD
    assert functional_level(a, b) is FunctionalLevel.HIGH
    # Gap of 2 levels in one category gives exactly 1/2
    c, d = caps(("endurance", 4, None)), caps(("endurance", 2, None))
    assert similarity_index(c, d) == MEDIUM_THRESHOLD
    assert functional_level(c, d) is FunctionalLevel.MEDIUM


def test_index_just_below_a_threshold_gives_the_lower_level():
    # Gap of 1 level is 3/4 exactly; with different equipment it drops below the threshold
    a = caps(("mobility_lower", 4, "handcycle"))
    b = caps(("mobility_lower", 3, "wheelchair_active"))
    index = similarity_index(a, b)
    assert isinstance(index, Fraction)
    assert index < HIGH_THRESHOLD
    assert functional_level(a, b) is FunctionalLevel.MEDIUM


def test_level_is_independent_of_entry_order():
    entries = [("vision", 1, None), ("endurance", 3, None), ("hearing", 2, None)]
    b = caps(("hearing", 4, None), ("vision", 0, None), ("endurance", 1, None))
    assert similarity_index(caps(*entries), b) == similarity_index(caps(*reversed(entries)), b)


def test_level_rank_is_zero_one_two():
    assert [
        level.rank for level in (FunctionalLevel.LOW, FunctionalLevel.MEDIUM, FunctionalLevel.HIGH)
    ] == [
        0,
        1,
        2,
    ]


def test_thresholds_are_three_quarters_and_one_half():
    # Golden: author's uncalibrated assumptions of the reference implementation
    assert HIGH_THRESHOLD == Fraction(3, 4)
    assert MEDIUM_THRESHOLD == Fraction(1, 2)
    assert EQUIPMENT_SHARE == Fraction(1, 4)


entries_strategy = st.dictionaries(
    st.sampled_from(list(CategoryCode)),
    st.tuples(st.integers(0, 4), st.booleans()),
    max_size=7,
)


def build(raw):
    """Build a profile from drawn data; equipment is the wheelchair on the lower mobility."""
    return FunctionalProfile(
        capabilities=frozenset(
            CapabilityEntry(
                category,
                level,
                EquipmentCode.WHEELCHAIR_ACTIVE
                if with_equipment and category == CategoryCode.MOBILITY_LOWER
                else None,
            )
            for category, (level, with_equipment) in raw.items()
        )
    )


@given(entries_strategy, entries_strategy)
def test_level_is_symmetric_for_any_profiles(raw_a, raw_b):
    a, b = build(raw_a), build(raw_b)
    assert functional_level(a, b) == functional_level(b, a)


@given(entries_strategy)
def test_a_profile_with_declared_capabilities_is_fully_compatible_with_itself(raw):
    a = build(raw)
    if a.capabilities:
        assert functional_level(a, a) is FunctionalLevel.HIGH


def codes(*names: str) -> frozenset[CategoryCode]:
    return frozenset(CategoryCode(name) for name in names)


def test_the_default_minimum_is_two_shared_categories():
    assert MIN_SHARED_CATEGORIES == 2


def test_one_shared_category_is_not_enough_by_default():
    viewer = codes("vision", "hearing")
    candidate = codes("vision", "endurance")

    assert has_enough_shared_categories(viewer, candidate) is False


def test_two_shared_categories_are_enough_by_default():
    viewer = codes("vision", "hearing", "endurance")
    candidate = codes("vision", "hearing")

    assert has_enough_shared_categories(viewer, candidate) is True


def test_nothing_declared_is_never_enough():
    assert has_enough_shared_categories(frozenset(), frozenset()) is False
    assert has_enough_shared_categories(codes("vision"), frozenset(), minimum=1) is False


def test_the_minimum_can_be_changed():
    assert has_enough_shared_categories(codes("vision"), codes("vision"), minimum=1) is True
    assert (
        has_enough_shared_categories(codes("vision", "hearing"), codes("vision", "hearing"), 3)
        is False
    )


@pytest.mark.parametrize("minimum", [0, -1])
def test_a_minimum_below_one_is_rejected(minimum):
    with pytest.raises(ValueError, match="minimum"):
        has_enough_shared_categories(codes("vision"), codes("vision"), minimum=minimum)


@given(
    st.frozensets(st.sampled_from(ALL)),
    st.frozensets(st.sampled_from(ALL)),
    st.integers(min_value=1, max_value=4),
)
def test_the_rule_is_symmetric_and_monotonic_in_the_minimum(left, right, minimum):
    result = has_enough_shared_categories(left, right, minimum)

    assert result == has_enough_shared_categories(right, left, minimum)
    assert result == (len(left & right) >= minimum)
    if result:
        assert has_enough_shared_categories(left, right, max(1, minimum - 1))


def test_overlap_below_the_minimum_is_shielded_to_an_empty_profile():
    viewer = caps(("vision", 4, None), ("hearing", 1, None))
    other = caps(("vision", 0, None), ("endurance", 3, None))

    shielded = shield_insufficient_overlap(viewer, other)

    assert shielded == FunctionalProfile.empty()
    assert functional_level(viewer, shielded) is FunctionalLevel.MEDIUM


def test_enough_overlap_passes_the_profile_through_unchanged():
    viewer = caps(("vision", 4, None), ("hearing", 1, None))
    other = caps(("vision", 0, None), ("hearing", 1, None), ("endurance", 3, None))

    assert shield_insufficient_overlap(viewer, other) is other


@given(st.lists(st.sampled_from(ALL), unique=True), st.lists(st.sampled_from(ALL), unique=True))
def test_a_shielded_comparison_never_depends_on_a_single_shared_category(mine, theirs):
    viewer = caps(*[(c, 4, None) for c in mine])
    low = caps(*[(c, 0, None) for c in theirs])
    high = caps(*[(c, 4, None) for c in theirs])
    if len(set(mine) & set(theirs)) >= MIN_SHARED_CATEGORIES:
        return

    # A viewer with at most one shared category sees the same level whatever the other declared
    assert functional_level(viewer, shield_insufficient_overlap(viewer, low)) is (
        functional_level(viewer, shield_insufficient_overlap(viewer, high))
    )
