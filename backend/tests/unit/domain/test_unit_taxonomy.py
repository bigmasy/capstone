"""Tests of the closed dictionaries of the taxonomy."""

import re

import pytest

from app.domain import taxonomy
from app.domain.taxonomy import (
    CATEGORIES,
    DISTRICTS,
    EQUIPMENT,
    LEVELS,
    SPORTS,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
# Words of the response format; a taxonomy code equal to one of them would make
# "the response contains no codes" checks ambiguous
RESERVED = {
    "distance",
    "sport",
    "functional",
    "intensity",
    "score",
    "profile",
    "low",
    "medium",
    "high",
}
# Heuristic guard against diagnosis-like wording in names and descriptions
DIAGNOSIS_WORDS = (
    "diabet",
    "amput",
    "paraly",
    "paraple",
    "tetraple",
    "cerebral",
    "palsy",
    "sclerosis",
    "autis",
    "epilep",
    "blind",
    "deaf",
    "disease",
    "syndrome",
    "disorder",
    "injury",
    "cancer",
    "dystrophy",
    "scolio",
    "arthritis",
    "stroke",
)
ALL_LISTS = {
    "sports": SPORTS,
    "categories": CATEGORIES,
    "equipment": EQUIPMENT,
    "districts": DISTRICTS,
}
CODE_ENUMS = {
    "sports": SportCode,
    "categories": CategoryCode,
    "equipment": EquipmentCode,
    "districts": DistrictCode,
}


@pytest.mark.parametrize("name", ALL_LISTS)
def test_codes_are_unique_snake_case_and_fit_the_column(name):
    # Arrange
    codes = [item.code for item in ALL_LISTS[name]]

    # Act / Assert
    assert len(codes) == len(set(codes))
    for code in codes:
        assert CODE_PATTERN.match(code), code
        assert len(code) <= 50
        assert code not in RESERVED


@pytest.mark.parametrize("name", ALL_LISTS)
def test_enum_members_are_exactly_the_listed_codes_in_order(name):
    # Arrange
    listed = [item.code for item in ALL_LISTS[name]]

    # Act
    members = [member.value for member in CODE_ENUMS[name]]

    # Assert
    assert members == listed


def test_equipment_applies_to_existing_categories():
    known = {c.code for c in CATEGORIES}
    for item in EQUIPMENT:
        assert item.categories
        assert set(item.categories) <= known


def test_version_is_semver_and_lists_have_minimum_size():
    assert re.match(r"^\d+\.\d+\.\d+$", taxonomy.TAXONOMY_VERSION)
    assert len(SPORTS) >= 10
    assert len(DISTRICTS) >= 1
    assert len(LEVELS) == 5


def test_taxonomy_version_golden():
    # Golden: bumping the version is a deliberate act, see the module docstring
    assert taxonomy.TAXONOMY_VERSION == "1.0.0"


def test_capability_levels_span_zero_to_four():
    assert [level.value for level in LEVELS] == [0, 1, 2, 3, 4]
    assert taxonomy.MIN_CAPABILITY_LEVEL == 0
    assert taxonomy.MAX_CAPABILITY_LEVEL == 4


def test_intensity_range_is_one_to_five():
    assert (taxonomy.MIN_INTENSITY, taxonomy.MAX_INTENSITY) == (1, 5)


def test_skill_levels_are_ordered_from_beginner_to_advanced():
    assert [s.rank for s in SkillLevel] == [0, 1, 2]
    assert SkillLevel.BEGINNER.rank < SkillLevel.INTERMEDIATE.rank < SkillLevel.ADVANCED.rank


def test_names_and_descriptions_have_no_diagnosis_like_words():
    texts = [item.name for lst in ALL_LISTS.values() for item in lst]
    texts += [c.description for c in CATEGORIES] + [level.label for level in LEVELS]
    for text in texts:
        for word in DIAGNOSIS_WORDS:
            assert word not in text.lower(), (word, text)


def test_equipment_by_code_indexes_every_item():
    assert set(taxonomy.EQUIPMENT_BY_CODE) == set(EquipmentCode)
    assert taxonomy.EQUIPMENT_BY_CODE[EquipmentCode.HANDCYCLE].categories == (
        CategoryCode.MOBILITY_LOWER,
    )
