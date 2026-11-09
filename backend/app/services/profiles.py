"""Profile scenarios: the consent rule, location coarsening and visibility."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.domain.account import (
    LocationRequiredError,
    OwnerProfile,
    ProfileDraft,
    ProfileRecord,
    PublicProfile,
)
from app.domain.errors import NotFoundError
from app.domain.privacy import GridCell, coarsen
from app.repository.profiles import ProfileRepository

_NOT_FOUND = "Profile not found"


def _utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class ProfileService:
    """Profile scenarios.

    :param profiles: Repository of profiles.
    :param clock: Source of the current time; replaced in tests.
    """

    def __init__(
        self, profiles: ProfileRepository, clock: Callable[[], datetime] = _utc_now
    ) -> None:
        """Keep the collaborators."""
        self.profiles = profiles
        self.clock = clock

    async def put_profile(self, user_id: UUID, draft: ProfileDraft) -> OwnerProfile:
        """Create or replace the profile of a user.

        Two privacy rules are applied here, before anything reaches storage. The exact location
        is replaced by the centre of its grid cell, so exact coordinates are never stored.
        Capabilities are kept only while ``functional_data_consent`` is true; withdrawing
        consent deletes them together with the consent time. The time of the first consent is
        kept across later saves.

        A draft without a location keeps the grid cell that is already stored, so editing the
        contact does not force the owner to enter the location again. Without a stored profile
        there is nothing to keep.

        :param user_id: Owner of the profile.
        :param draft: Submitted content with the exact location, or without one.
        :raises LocationRequiredError: If the draft has no location and the user has no profile.
        :return: The stored profile as its owner sees it.
        """
        existing = await self.profiles.get_profile_by_user_id(user_id)
        cell: GridCell | None = None
        if draft.latitude is not None and draft.longitude is not None:
            cell = coarsen(draft.latitude, draft.longitude)
        elif existing is None:
            raise LocationRequiredError
        consent_at: datetime | None = None
        if draft.functional_data_consent:
            previous = existing.functional_consent_at if existing else None
            consent_at = previous or self.clock()
        record = ProfileRecord(
            display_name=draft.display_name,
            district=draft.district,
            intensity=draft.intensity,
            is_visible=draft.is_visible,
            cell=cell,
            sports=draft.sports,
            capabilities=draft.capabilities if draft.functional_data_consent else (),
            functional_consent_at=consent_at,
            contact=draft.contact,
        )
        return await self.profiles.replace_profile(user_id, record)

    async def get_my_profile(self, user_id: UUID) -> OwnerProfile:
        """Return the caller's own profile.

        :param user_id: The caller.
        :raises NotFoundError: If the caller has not created a profile yet.
        :return: The profile as its owner sees it.
        """
        profile = await self.profiles.get_profile_by_user_id(user_id)
        if profile is None:
            raise NotFoundError(_NOT_FOUND)
        return profile

    async def get_public_profile(self, profile_id: UUID) -> PublicProfile:
        """Return the public view of a profile.

        A hidden profile is reported exactly like a missing one.

        :param profile_id: Identifier of the profile.
        :raises NotFoundError: If the profile does not exist or is hidden.
        :return: The public view.
        """
        profile = await self.profiles.get_public_profile_by_id(profile_id)
        if profile is None:
            raise NotFoundError(_NOT_FOUND)
        return profile

    async def delete_my_profile(self, user_id: UUID) -> None:
        """Delete the caller's profile with its sports and capabilities.

        :param user_id: The caller.
        :raises NotFoundError: If the caller has no profile.
        """
        if not await self.profiles.remove_profile(user_id):
            raise NotFoundError(_NOT_FOUND)
