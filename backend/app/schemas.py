from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# The NUL character is rejected: PostgreSQL does not store it in text fields
NO_NUL = r"^[^\x00]*$"

# Upper limits on the number of entries in a profile. These are design limits
# until the reference lists appear (week 2), not the result of measurements.
MAX_SPORTS = 10
MAX_CAPABILITIES = 20


def _text(max_length: int):
    """String stripped of surrounding whitespace: non-empty, without NUL, at most max_length long."""
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=max_length, pattern=NO_NUL
        ),
    ]


DisplayName = _text(60)
District = _text(100)
Sport = _text(50)
Category = _text(50)
Equipment = _text(50)


class Location(BaseModel):
    """Coordinates are accepted as input only and are not stored as exact values."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    sport: Sport
    level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")


class CapabilityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    category: Category
    level: int = Field(ge=0, le=4)
    equipment: Equipment | None = None


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName = Field(alias="displayName")
    district: District | None = None
    location: Location
    intensity: int = Field(ge=1, le=5)
    is_visible: bool = Field(default=True, alias="isVisible")
    sports: list[SportEntry] = Field(min_length=1, max_length=MAX_SPORTS)
    capabilities: list[CapabilityEntry] = Field(default=[], max_length=MAX_CAPABILITIES)


class ProfilePublic(BaseModel):
    """Public view: without functional data and location."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    display_name: str = Field(serialization_alias="displayName")
    district: str | None
    intensity: int
    sports: list[SportEntry]


class ProfilePrivate(ProfilePublic):
    is_visible: bool = Field(serialization_alias="isVisible")
    capabilities: list[CapabilityEntry]


class MatchItem(BaseModel):
    profile: ProfilePublic
    score: float = Field(ge=0, le=100)
    distance: str
