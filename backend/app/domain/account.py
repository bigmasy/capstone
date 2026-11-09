"""Account and profile records exchanged between the service and repository layers.

These are plain immutable values, independent of storage and of the HTTP schemas. Fields that
hold personal data are excluded from ``repr`` so they cannot leak through logs or test output.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.errors import DomainError
from app.domain.privacy import GridCell
from app.domain.profile import CapabilityEntry, SportEntry
from app.domain.taxonomy import DistrictCode

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
EMAIL_MAX_LENGTH = 254
DISPLAY_NAME_MAX_LENGTH = 60
CONTACT_MIN_LENGTH = 3
CONTACT_MAX_LENGTH = 120
MAX_SPORTS = 10

LOCATION_REQUIRED_MESSAGE = "Latitude and longitude are required to create a profile"
LOCATION_INCOMPLETE_MESSAGE = "Latitude and longitude must be given together"


class LocationRequiredError(DomainError):
    """A profile would be stored without a location (HTTP 422).

    Raised when the owner has no stored location yet and the submission carries none. The
    message is fixed and never repeats any submitted value.
    """

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(LOCATION_REQUIRED_MESSAGE)


def password_meets_policy(password: str) -> bool:
    """Check the password policy: 10 to 128 characters, no other composition rules.

    Length is the only rule on purpose: composition rules push people towards predictable
    patterns, and the upper bound keeps the hashing cost bounded.

    :param password: Candidate password.
    :return: True when the length is within the allowed range.
    """
    return PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH


@dataclass(frozen=True, slots=True)
class Account:
    """A registered user as the service layer sees it.

    :param id: User identifier.
    :param email: Lower-cased e-mail address.
    :param password_hash: Argon2id hash of the password.
    :param created_at: Registration time (UTC).
    """

    id: UUID
    email: str = field(repr=False)
    password_hash: str = field(repr=False)
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileDraft:
    """What the owner submits when saving a profile; the only record that holds exact coordinates.

    The draft never reaches storage: the service coarsens the location first.

    :param display_name: Name shown to other people.
    :param district: Optional district.
    :param intensity: Preferred training intensity, 1 to 5.
    :param is_visible: Whether other people may see the profile.
    :param latitude: Exact latitude as submitted, or None to keep the stored location.
    :param longitude: Exact longitude as submitted, or None to keep the stored location.
    :param sports: Sports with skills.
    :param capabilities: Declared capabilities; kept only with consent.
    :param functional_data_consent: Whether the owner consents to storing capabilities.
    :param contact: Optional contact shown to a partner after an invitation is accepted.
    :raises ValueError: If only one of the two coordinates is given.
    """

    display_name: str
    district: DistrictCode | None
    intensity: int
    is_visible: bool
    latitude: float | None = field(repr=False, default=None)
    longitude: float | None = field(repr=False, default=None)
    sports: tuple[SportEntry, ...]
    capabilities: tuple[CapabilityEntry, ...] = field(repr=False)
    functional_data_consent: bool
    contact: str | None = field(repr=False, default=None)

    def __post_init__(self) -> None:
        """Reject half a location; the message names no value."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(LOCATION_INCOMPLETE_MESSAGE)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileRecord:
    """A profile ready for storage: the location is already a grid cell.

    :param display_name: Name shown to other people.
    :param district: Optional district.
    :param intensity: Preferred training intensity, 1 to 5.
    :param is_visible: Whether other people may see the profile.
    :param cell: Centre of the grid cell of the owner's location, or None to keep the cell that
        is already stored (only valid for an existing profile).
    :param sports: Sports with skills.
    :param capabilities: Capabilities to store; empty without consent.
    :param functional_consent_at: When consent was given, or None.
    :param contact: Optional contact.
    """

    display_name: str
    district: DistrictCode | None
    intensity: int
    is_visible: bool
    cell: GridCell | None = field(repr=False)
    sports: tuple[SportEntry, ...]
    capabilities: tuple[CapabilityEntry, ...] = field(repr=False)
    functional_consent_at: datetime | None
    contact: str | None = field(repr=False, default=None)


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnerProfile:
    """A profile as its owner sees it: public fields plus private ones, never the location.

    :param id: Profile identifier.
    :param user_id: Owner.
    :param display_name: Name shown to other people.
    :param district: Optional district.
    :param intensity: Preferred training intensity, 1 to 5.
    :param is_visible: Whether other people may see the profile.
    :param sports: Sports with skills, ordered by sport code.
    :param capabilities: Declared capabilities, ordered by category code.
    :param functional_consent_at: When consent was given, or None.
    :param contact: Optional contact.
    :param created_at: Creation time (UTC).
    :param updated_at: Last change (UTC).
    """

    id: UUID
    user_id: UUID
    display_name: str
    district: DistrictCode | None
    intensity: int
    is_visible: bool
    sports: tuple[SportEntry, ...]
    capabilities: tuple[CapabilityEntry, ...] = field(repr=False)
    functional_consent_at: datetime | None
    contact: str | None = field(repr=False)
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class PublicProfile:
    """A profile as any other signed-in user sees it.

    :param id: Profile identifier.
    :param display_name: Name shown to other people.
    :param district: Optional district.
    :param intensity: Preferred training intensity, 1 to 5.
    :param sports: Sports with skills, ordered by sport code.
    """

    id: UUID
    display_name: str
    district: DistrictCode | None
    intensity: int
    sports: tuple[SportEntry, ...]
