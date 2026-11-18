from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.profiles import ProfileOwner, ProfilePublic, ProfilePut

SECRET_MARK = "canary-input-7731"


def profile_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "display_name": "Orest",
        "district_code": "kyiv_podilskyi",
        "intensity": 3,
        "is_visible": True,
        "latitude": 50.45,
        "longitude": 30.52,
        "sports": [{"sport": "swimming", "skill": "beginner"}],
        "capabilities": [{"category": "mobility_lower", "level": 2, "equipment": "handcycle"}],
        "functional_data_consent": True,
        "contact": "t.me/orest",
    }
    body.update(overrides)
    return body


def error_messages(exc: ValidationError) -> str:
    return " ".join(error["msg"] for error in exc.errors())


def test_valid_profile_converts_to_a_draft():
    draft = ProfilePut.model_validate(profile_body()).to_draft()

    assert draft.display_name == "Orest"
    assert draft.sports[0].sport.value == "swimming"
    assert draft.capabilities[0].level == 2
    assert draft.functional_data_consent is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"extra_field": 1},
        {"display_name": ""},
        {"display_name": "   "},
        {"display_name": "x" * 61},
        {"display_name": "bad\x00name"},
        {"district_code": "atlantis"},
        {"intensity": 0},
        {"intensity": 6},
        {"latitude": 91},
        {"latitude": float("nan")},
        {"longitude": -181},
        {"longitude": float("inf")},
        {"sports": []},
        {"sports": [{"sport": "swimming", "skill": "beginner"}] * 2},
        {"sports": [{"sport": "chess", "skill": "beginner"}]},
        {"sports": [{"sport": "swimming", "skill": "expert"}]},
        {"sports": [{"sport": "swimming", "skill": "beginner", "x": 1}]},
        {
            "sports": [
                {"sport": s, "skill": "beginner"}
                for s in [
                    "swimming",
                    "archery",
                    "table_tennis",
                    "sitting_volleyball",
                    "wheelchair_basketball",
                    "cycling",
                    "handcycling",
                    "rowing",
                    "athletics",
                    "gym_fitness",
                    "powerlifting",
                ]
            ]
        },
        {"capabilities": [{"category": "vision", "level": 5}]},
        {"capabilities": [{"category": "vision", "level": -1}]},
        {"capabilities": [{"category": "vision", "level": 2, "equipment": "handcycle"}]},
        {"capabilities": [{"category": "vision", "level": 1}, {"category": "vision", "level": 2}]},
        {"capabilities": [{"category": "telepathy", "level": 1}]},
        {"capabilities": [{"category": "vision", "level": 1, "note": "x"}]},
        {"contact": "x" * 121},
        {"contact": "ab"},
        {"contact": "  a  "},
        {"contact": "t.me/\x00orest"},
        {"contact": "t.me/orest\nsecond line"},
        {"contact": "t.me/orest\x7f"},
        {"functional_data_consent": "maybe"},
        {"is_visible": "perhaps"},
    ],
)
def test_invalid_profiles_are_rejected(overrides: dict[str, Any]):
    with pytest.raises(ValidationError):
        ProfilePut.model_validate(profile_body(**overrides))


def test_capability_list_is_capped_at_the_number_of_categories():
    categories = [
        "mobility_lower", "mobility_upper", "balance_posture", "endurance",
        "dexterity", "vision", "hearing",
    ]  # fmt: skip
    body = profile_body(capabilities=[{"category": c, "level": 1} for c in categories] * 2)

    with pytest.raises(ValidationError):
        ProfilePut.model_validate(body)


def test_error_messages_never_echo_the_input():
    bodies = [
        profile_body(display_name=SECRET_MARK * 10),
        profile_body(district_code=SECRET_MARK),
        profile_body(sports=[{"sport": SECRET_MARK, "skill": "beginner"}]),
        profile_body(capabilities=[{"category": SECRET_MARK, "level": 1}]),
        profile_body(capabilities=[{"category": "vision", "level": 1, "equipment": SECRET_MARK}]),
        profile_body(contact=SECRET_MARK * 20),
        profile_body(intensity=SECRET_MARK),
        profile_body(latitude=SECRET_MARK),
        profile_body(**{SECRET_MARK: 1}),
    ]
    for body in bodies:
        with pytest.raises(ValidationError) as caught:
            ProfilePut.model_validate(body)
        assert SECRET_MARK not in error_messages(caught.value)


def test_duplicate_and_equipment_messages_are_fixed_strings():
    with pytest.raises(ValidationError) as dup:
        ProfilePut.model_validate(
            profile_body(sports=[{"sport": "swimming", "skill": "beginner"}] * 2)
        )
    with pytest.raises(ValidationError) as fit:
        ProfilePut.model_validate(
            profile_body(
                capabilities=[{"category": "vision", "level": 2, "equipment": "handcycle"}]
            )
        )

    assert "Each sport can be listed only once" in error_messages(dup.value)
    assert "Equipment does not apply to the category" in error_messages(fit.value)


def test_text_fields_are_trimmed_and_blank_contact_becomes_none():
    draft = ProfilePut.model_validate(
        profile_body(display_name="  Orest  ", contact="  ")
    ).to_draft()

    assert draft.display_name == "Orest"
    assert draft.contact is None


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("abc", "abc"),
        ("  t.me/orest  ", "t.me/orest"),
        ("x" * 120, "x" * 120),
        ("  " + "x" * 120 + "  ", "x" * 120),
        (None, None),
        ("", None),
    ],
)
def test_contact_is_trimmed_and_kept_between_3_and_120_characters(
    raw: str | None, stored: str | None
):
    draft = ProfilePut.model_validate(profile_body(contact=raw)).to_draft()

    assert draft.contact == stored


def test_the_contact_stays_out_of_the_repr_of_the_body():
    body = ProfilePut.model_validate(profile_body(contact="canary-contact-1c2d"))

    assert "canary-contact-1c2d" not in repr(body)


def test_omitted_visibility_and_consent_use_safe_defaults():
    body = profile_body()
    del body["is_visible"], body["functional_data_consent"], body["capabilities"]

    draft = ProfilePut.model_validate(body).to_draft()

    assert draft.is_visible is True
    assert draft.functional_data_consent is False
    assert draft.capabilities == ()


def test_register_normalises_the_email_and_applies_the_password_policy():
    request = RegisterRequest(email="  Orest@Example.ORG ", password="x" * 10)

    assert request.email == "orest@example.org"


@pytest.mark.parametrize(
    "values",
    [
        {"email": "not-an-email", "password": "x" * 10},
        {"email": "a@b", "password": "x" * 10},
        {"email": "a b@example.org", "password": "x" * 10},
        {"email": "a@example.org", "password": "x" * 9},
        {"email": "a@example.org", "password": "x" * 129},
        {"email": "a" * 250 + "@example.org", "password": "x" * 10},
        {"email": "a@example.org", "password": "x" * 10, "role": "admin"},
    ],
)
def test_invalid_registrations_are_rejected(values: dict[str, Any]):
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate(values)


def test_password_is_never_in_error_text_or_repr():
    with pytest.raises(ValidationError) as caught:
        RegisterRequest.model_validate({"email": "bad", "password": SECRET_MARK})

    assert SECRET_MARK not in str(caught.value.errors(include_input=False))
    assert SECRET_MARK not in error_messages(caught.value)
    assert SECRET_MARK not in repr(LoginRequest(email="a@example.org", password=SECRET_MARK))


def test_public_and_owner_models_expose_no_location():
    for model in (ProfilePublic, ProfileOwner):
        names = set(model.model_fields)
        assert not {"latitude", "longitude", "area_lat", "area_lon", "cell"} & names
    assert {"capabilities", "contact"}.isdisjoint(ProfilePublic.model_fields)
    assert set(ProfilePublic.model_fields) == {
        "id", "display_name", "district_code", "intensity", "sports", "has_photo",
    }  # fmt: skip


def without_location(**overrides: Any) -> dict[str, Any]:
    body = profile_body(**overrides)
    del body["latitude"], body["longitude"]
    return body


def test_a_body_without_a_location_is_valid_and_gives_a_draft_without_one():
    draft = ProfilePut.model_validate(without_location()).to_draft()

    assert draft.latitude is None and draft.longitude is None


def test_null_coordinates_count_as_omitted():
    parsed = ProfilePut.model_validate(profile_body(latitude=None, longitude=None))

    assert parsed.latitude is None and parsed.longitude is None


@pytest.mark.parametrize("given", ["latitude", "longitude"])
def test_one_coordinate_alone_is_rejected_with_a_fixed_message(given: str):
    body = without_location()
    body[given] = 1.5

    with pytest.raises(ValidationError) as caught:
        ProfilePut.model_validate(body)

    assert [error["type"] for error in caught.value.errors()] == ["location_incomplete"]
    assert error_messages(caught.value) == "Latitude and longitude must be given together"


def test_one_null_and_one_value_is_rejected():
    with pytest.raises(ValidationError):
        ProfilePut.model_validate(profile_body(latitude=None))


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": 90.5},
        {"latitude": -90.5},
        {"longitude": 180.5},
        {"longitude": -180.5},
        {"latitude": float("nan")},
        {"longitude": float("inf")},
        {"latitude": "50.4"},
        {"longitude": True},
    ],
)
def test_given_coordinates_are_still_validated_strictly(overrides: dict[str, Any]):
    with pytest.raises(ValidationError):
        ProfilePut.model_validate(profile_body(**overrides))


def test_the_coordinates_stay_out_of_repr_when_given_and_when_omitted():
    given = ProfilePut.model_validate(profile_body(latitude=50.4501, longitude=30.5234))
    omitted = ProfilePut.model_validate(without_location())

    assert "50.4501" not in repr(given) and "30.5234" not in repr(given)
    assert "latitude" not in repr(omitted)
