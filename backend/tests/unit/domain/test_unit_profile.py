"""Tests of the profile value objects."""

import dataclasses

import pytest

from app.domain.profile import CapabilityEntry, FunctionalProfile, ProfileView, SportEntry
from app.domain.taxonomy import CategoryCode, EquipmentCode, SkillLevel, SportCode
from tests.unit.domain.builders import make_functional, make_id, make_profile


def test_sport_entry_defaults_to_beginner():
    assert SportEntry(sport=SportCode.SWIMMING).skill is SkillLevel.BEGINNER


@pytest.mark.parametrize("level", [-1, 5])
def test_capability_level_must_be_between_zero_and_four(level):
    with pytest.raises(ValueError, match="level"):
        CapabilityEntry(category=CategoryCode.VISION, level=level)


@pytest.mark.parametrize("level", [0, 4])
def test_capability_level_accepts_the_range_ends(level):
    assert CapabilityEntry(category=CategoryCode.VISION, level=level).level == level


def test_equipment_must_fit_the_category():
    with pytest.raises(ValueError, match="equipment"):
        CapabilityEntry(
            category=CategoryCode.HEARING,
            level=2,
            equipment=EquipmentCode.WHEELCHAIR_ACTIVE,
        )


def test_applicable_equipment_is_accepted():
    entry = CapabilityEntry(
        category=CategoryCode.MOBILITY_LOWER, level=2, equipment=EquipmentCode.HANDCYCLE
    )
    assert entry.equipment is EquipmentCode.HANDCYCLE


def test_functional_profile_rejects_a_duplicate_category():
    with pytest.raises(ValueError, match="category"):
        make_functional(("endurance", 1, None), ("endurance", 3, None))


def test_functional_profile_is_equal_regardless_of_entry_order():
    a = make_functional(("vision", 1, None), ("endurance", 3, None))
    b = make_functional(("endurance", 3, None), ("vision", 1, None))
    assert a == b


def test_functional_profile_looks_up_by_category():
    profile = make_functional(("vision", 1, None))
    assert profile.get(CategoryCode.VISION) == CapabilityEntry(CategoryCode.VISION, 1)
    assert profile.get(CategoryCode.HEARING) is None


def test_functional_profile_representation_hides_the_private_values():
    profile = make_functional(("vision", 1, None), ("mobility_lower", 3, "handcycle"))
    text = repr(profile) + str(profile)
    assert "vision" not in text
    assert "handcycle" not in text


def test_capability_entry_representation_hides_category_level_and_equipment():
    entry = CapabilityEntry(CategoryCode.MOBILITY_LOWER, 3, EquipmentCode.HANDCYCLE)
    text = repr(entry) + str(entry)
    assert "mobility" not in text
    assert "handcycle" not in text
    assert "3" not in text


def test_capability_entry_equality_and_hash_still_use_the_values():
    a = CapabilityEntry(CategoryCode.VISION, 1)
    assert a == CapabilityEntry(CategoryCode.VISION, 1)
    assert a != CapabilityEntry(CategoryCode.VISION, 2)
    assert len({a, CapabilityEntry(CategoryCode.VISION, 1)}) == 1


def test_profile_view_representation_hides_the_functional_layer_and_the_cell():
    view = make_profile(caps=[("vision", 1, None)])
    text = repr(view)
    assert "vision" not in text
    assert str(view.cell.latitude) not in text
    assert str(view.cell.longitude) not in text


def test_empty_functional_profile_is_the_default():
    assert FunctionalProfile.empty() == FunctionalProfile(capabilities=frozenset())


@pytest.mark.parametrize("intensity", [0, 6])
def test_intensity_must_be_between_one_and_five(intensity):
    with pytest.raises(ValueError, match="intensity"):
        make_profile(intensity=intensity)


def test_profile_view_rejects_the_same_sport_twice():
    with pytest.raises(ValueError, match="sport"):
        make_profile(
            sports=[
                (SportCode.SWIMMING, SkillLevel.BEGINNER),
                (SportCode.SWIMMING, SkillLevel.ADVANCED),
            ]
        )


def test_profile_view_exposes_sport_codes_and_skills():
    view = make_profile(sports=[("swimming", SkillLevel.ADVANCED), "archery"])
    assert view.sport_codes == frozenset({SportCode.SWIMMING, SportCode.ARCHERY})
    assert view.skill_in(SportCode.SWIMMING) is SkillLevel.ADVANCED
    assert view.skill_in(SportCode.ROWING) is None


def test_profile_view_is_frozen_and_uses_slots():
    view = make_profile()
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.intensity = 5  # type: ignore[misc]
    assert not hasattr(view, "__dict__")


def test_profile_view_defaults_are_visible_without_district_or_capabilities():
    view = ProfileView(
        id=make_id(1),
        sports=frozenset(),
        intensity=3,
        cell=make_profile().cell,
    )
    assert view.is_visible is True
    assert view.district is None
    assert view.functional == FunctionalProfile.empty()
