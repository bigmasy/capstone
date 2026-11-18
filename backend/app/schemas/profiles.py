"""Request and response models of the profile routes.

``ProfilePublic`` is what any signed-in user may see; ``ProfileOwner`` adds the private fields
for the owner. Neither has a latitude, a longitude or a grid cell: the location leaves the
system as a district code only.
"""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.domain.account import (
    CONTACT_MAX_LENGTH,
    CONTACT_MIN_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    LOCATION_INCOMPLETE_MESSAGE,
    MAX_SPORTS,
    OwnerProfile,
    ProfileDraft,
    PublicProfile,
)
from app.domain.privacy import AreaPrecision
from app.domain.profile import CapabilityEntry, SportEntry
from app.domain.taxonomy import (
    CATEGORIES,
    EQUIPMENT_BY_CODE,
    MAX_CAPABILITY_LEVEL,
    MAX_INTENSITY,
    MIN_CAPABILITY_LEVEL,
    MIN_INTENSITY,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)

MAX_CAPABILITIES = len(CATEGORIES)

# Messages are fixed strings: a validation message must never repeat what the client sent.
_DUPLICATE_SPORT = "Each sport can be listed only once"
_DUPLICATE_CATEGORY = "Each category can be declared only once"
_EQUIPMENT_MISMATCH = "Equipment does not apply to the category"
_BAD_TEXT = "Text contains control characters"
_TOO_SHORT = "Text is too short"

Intensity = Annotated[int, Field(strict=True, ge=MIN_INTENSITY, le=MAX_INTENSITY)]
ShortText = StringConstraints(strip_whitespace=True)


def _has_control_characters(value: str) -> bool:
    """Tell whether a string holds control characters (NUL, newlines, escapes)."""
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


class SportItem(BaseModel):
    """A sport with the self-declared skill; used in requests and responses."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    sport: SportCode
    skill: SkillLevel = SkillLevel.BEGINNER


class CapabilityItem(BaseModel):
    """A declared capability; used in requests and in the owner's response."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    category: CategoryCode
    level: Annotated[int, Field(strict=True, ge=MIN_CAPABILITY_LEVEL, le=MAX_CAPABILITY_LEVEL)]
    equipment: EquipmentCode | None = None

    @model_validator(mode="after")
    def check_equipment_fits_category(self) -> Self:
        """Reject equipment that cannot be attached to the category.

        :raises ValueError: With a fixed message, if the equipment does not apply.
        :return: The validated item.
        """
        if (
            self.equipment is not None
            and self.category not in EQUIPMENT_BY_CODE[self.equipment].categories
        ):
            raise ValueError(_EQUIPMENT_MISMATCH)
        return self


class ProfilePut(BaseModel):
    """Body of ``PUT /profiles/me``: the full profile, replacing the previous one.

    ``latitude`` and ``longitude`` go together: send both or neither. Both omitted (or null)
    keeps the location stored with the existing profile, so the contact or the sports can be
    edited without entering the location again. The first save of a profile needs both, and
    sending only one is rejected.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH),
    ]
    district_code: DistrictCode | None = None
    intensity: Intensity
    is_visible: StrictBool = True
    # Exact coordinates are accepted as input only; the service coarsens them before storage.
    latitude: Annotated[float, Field(strict=True, ge=-90, le=90, allow_inf_nan=False)] | None = (
        Field(
            default=None,
            repr=False,
            description=(
                "Exact latitude, -90 to 90; coarsened to a grid cell before storage and never "
                "returned. Send together with longitude, or omit both to keep the stored location "
                "(required on the first save)."
            ),
        )
    )
    longitude: Annotated[float, Field(strict=True, ge=-180, le=180, allow_inf_nan=False)] | None = (
        Field(
            default=None,
            repr=False,
            description=(
                "Exact longitude, -180 to 180; coarsened to a grid cell before storage and never "
                "returned. Send together with latitude, or omit both to keep the stored location "
                "(required on the first save)."
            ),
        )
    )
    area_precision: AreaPrecision | None = Field(
        default=None,
        description=(
            "How coarse the stored area is: a grid of about 1, 2 or 4 km, or 'place' for a city "
            "or district alone. With coordinates it selects the grid they are coarsened to; "
            "without them a coarser value coarsens the stored area and a finer one is ignored. "
            "Omit to keep the stored choice (4km for a new profile)."
        ),
    )
    sports: Annotated[list[SportItem], Field(min_length=1, max_length=MAX_SPORTS)]
    capabilities: Annotated[
        list[CapabilityItem], Field(max_length=MAX_CAPABILITIES, repr=False)
    ] = []
    functional_data_consent: StrictBool = False
    contact: Annotated[str | None, ShortText, Field(max_length=CONTACT_MAX_LENGTH, repr=False)] = (
        None
    )

    @model_validator(mode="after")
    def check_location_is_complete(self) -> Self:
        """Require latitude and longitude to be given together or not at all.

        :raises PydanticCustomError: With a fixed message, if only one coordinate is given.
        :return: The validated body.
        """
        if (self.latitude is None) != (self.longitude is None):
            raise PydanticCustomError("location_incomplete", LOCATION_INCOMPLETE_MESSAGE)
        return self

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, value: str) -> str:
        """Reject control characters in the display name.

        :param value: Trimmed name.
        :raises ValueError: With a fixed message.
        :return: The name unchanged.
        """
        if _has_control_characters(value):
            raise ValueError(_BAD_TEXT)
        return value

    @field_validator("contact")
    @classmethod
    def check_contact(cls, value: str | None) -> str | None:
        """Turn a blank contact into None, reject a too short one and control characters.

        Blank means "no contact" so the owner can clear the field; anything else must be
        3 to 120 characters after trimming (the upper bound is the field constraint).

        :param value: Trimmed contact.
        :raises PydanticCustomError: With a fixed message, if the contact is shorter than allowed.
        :raises ValueError: With a fixed message, if it holds control characters.
        :return: The contact, or None when blank.
        """
        if not value:
            return None
        if _has_control_characters(value):
            raise ValueError(_BAD_TEXT)
        if len(value) < CONTACT_MIN_LENGTH:
            raise PydanticCustomError("string_too_short", _TOO_SHORT)
        return value

    @field_validator("sports")
    @classmethod
    def check_sports_unique(cls, value: list[SportItem]) -> list[SportItem]:
        """Reject a sport listed twice.

        :param value: Submitted sports.
        :raises ValueError: With a fixed message.
        :return: The sports unchanged.
        """
        if len({item.sport for item in value}) != len(value):
            raise ValueError(_DUPLICATE_SPORT)
        return value

    @field_validator("capabilities")
    @classmethod
    def check_categories_unique(cls, value: list[CapabilityItem]) -> list[CapabilityItem]:
        """Reject two capabilities for one category.

        :param value: Submitted capabilities.
        :raises ValueError: With a fixed message.
        :return: The capabilities unchanged.
        """
        if len({item.category for item in value}) != len(value):
            raise ValueError(_DUPLICATE_CATEGORY)
        return value

    def to_draft(self) -> ProfileDraft:
        """Convert the validated body to the record the service works with.

        :return: The draft, which still carries the exact location.
        """
        return ProfileDraft(
            display_name=self.display_name,
            district=self.district_code,
            intensity=self.intensity,
            is_visible=self.is_visible,
            latitude=self.latitude,
            longitude=self.longitude,
            area_precision=self.area_precision,
            sports=tuple(SportEntry(item.sport, item.skill) for item in self.sports),
            capabilities=tuple(
                CapabilityEntry(item.category, item.level, item.equipment)
                for item in self.capabilities
            ),
            functional_data_consent=self.functional_data_consent,
            contact=self.contact,
        )


class ProfilePublic(BaseModel):
    """What another signed-in user sees: no capabilities, no contact, no location."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    district_code: DistrictCode | None
    intensity: int
    sports: list[SportItem]
    has_photo: bool = Field(
        description="Whether GET /profiles/{id}/photo has a picture for the caller."
    )

    @classmethod
    def from_domain(cls, profile: PublicProfile) -> Self:
        """Build the response from a public profile record.

        :param profile: The record.
        :return: The response model.
        """
        return cls(
            id=profile.id,
            display_name=profile.display_name,
            district_code=profile.district,
            intensity=profile.intensity,
            sports=[SportItem.model_validate(entry) for entry in profile.sports],
            has_photo=profile.has_photo,
        )


class ProfileOwner(ProfilePublic):
    """What the owner sees: the public fields plus the private ones, still no location.

    ``area_precision`` says how coarse the stored area is; the area itself is not returned.
    """

    is_visible: bool
    area_precision: AreaPrecision
    functional_data_consent: bool
    functional_consent_at: datetime | None
    capabilities: list[CapabilityItem]
    contact: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_owner(cls, profile: OwnerProfile) -> Self:
        """Build the response from an owner record.

        :param profile: The record.
        :return: The response model.
        """
        return cls(
            id=profile.id,
            display_name=profile.display_name,
            district_code=profile.district,
            intensity=profile.intensity,
            sports=[SportItem.model_validate(entry) for entry in profile.sports],
            has_photo=profile.has_photo,
            is_visible=profile.is_visible,
            area_precision=profile.area_precision,
            functional_data_consent=profile.functional_consent_at is not None,
            functional_consent_at=profile.functional_consent_at,
            capabilities=[CapabilityItem.model_validate(entry) for entry in profile.capabilities],
            contact=profile.contact,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class PhotoRejectedResponse(BaseModel):
    """Body of the 422 answer to an upload that cannot be used as a photograph."""

    detail: str
    code: Literal["photo_invalid", "photo_too_large"]
