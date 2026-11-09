"""Tests of the profile records: the location rules of the draft."""

import pytest

from app.domain.account import (
    LOCATION_INCOMPLETE_MESSAGE,
    LOCATION_REQUIRED_MESSAGE,
    LocationRequiredError,
    ProfileDraft,
)
from app.domain.errors import DomainError


def make_draft(**overrides: object) -> ProfileDraft:
    values: dict[str, object] = {
        "display_name": "Orest",
        "district": None,
        "intensity": 3,
        "is_visible": True,
        "sports": (),
        "capabilities": (),
        "functional_data_consent": False,
    }
    values.update(overrides)
    return ProfileDraft(**values)  # type: ignore[arg-type]


def test_a_draft_may_carry_both_coordinates_or_neither():
    assert make_draft(latitude=50.45, longitude=30.52).latitude == 50.45
    assert make_draft().latitude is None and make_draft().longitude is None


@pytest.mark.parametrize("given", [{"latitude": 50.45}, {"longitude": 30.52}])
def test_a_draft_with_one_coordinate_is_rejected_without_naming_it(given: dict[str, float]):
    with pytest.raises(ValueError, match=LOCATION_INCOMPLETE_MESSAGE) as caught:
        make_draft(**given)

    assert "50.45" not in str(caught.value) and "30.52" not in str(caught.value)


def test_the_coordinates_are_not_in_the_repr():
    assert "50.45" not in repr(make_draft(latitude=50.45, longitude=30.52))


def test_the_location_error_is_a_domain_error_with_a_fixed_message():
    error = LocationRequiredError()

    assert isinstance(error, DomainError)
    assert error.message == LOCATION_REQUIRED_MESSAGE
