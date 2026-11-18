"""Profile scenarios: the consent rule, location coarsening, visibility and the photograph."""

import asyncio
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
from app.domain.photo import (
    PHOTO_MAX_UPLOAD_BYTES,
    PHOTO_TOO_LARGE_CODE,
    PhotoRejectedError,
)
from app.domain.privacy import DEFAULT_PRECISION, AreaPrecision, GridCell, coarsen
from app.repository.photos import PhotoRepository
from app.repository.profiles import ProfileRepository

_NOT_FOUND = "Profile not found"
_PHOTO_NOT_FOUND = "Photo not found"


def _utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class ProfileService:
    """Profile scenarios.

    :param profiles: Repository of profiles.
    :param clock: Source of the current time; replaced in tests.
    :param photos: Repository of photographs; needed only by the photograph scenarios.
    :param normalise_photo: Blocking function that turns an upload into the stored picture.
    """

    def __init__(
        self,
        profiles: ProfileRepository,
        clock: Callable[[], datetime] = _utc_now,
        photos: PhotoRepository | None = None,
        normalise_photo: Callable[[bytes], bytes] | None = None,
    ) -> None:
        """Keep the collaborators."""
        self.profiles = profiles
        self.clock = clock
        self.photos = photos
        self.normalise_photo = normalise_photo

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

        The owner chooses how coarse the area is. With a location the chosen grid is applied to
        it. Without one, asking for a coarser grid coarsens the stored cell; asking for a finer
        one changes nothing, because the point inside the stored cell is not known.

        :param user_id: Owner of the profile.
        :param draft: Submitted content with the exact location, or without one.
        :raises LocationRequiredError: If the draft has no location and the user has no profile.
        :return: The stored profile as its owner sees it.
        """
        existing = await self.profiles.get_profile_by_user_id(user_id)
        cell: GridCell | None = None
        precision: AreaPrecision | None = None
        if draft.latitude is not None and draft.longitude is not None:
            precision = draft.area_precision or (
                existing.area_precision if existing else DEFAULT_PRECISION
            )
            cell = coarsen(draft.latitude, draft.longitude, precision)
        elif existing is None:
            raise LocationRequiredError
        elif draft.area_precision is not None and draft.area_precision.is_coarser_than(
            existing.area_precision
        ):
            # The grids are nested, so the stored cell lies inside exactly one coarser cell
            stored = await self.profiles.get_stored_area(user_id)
            if stored is not None:
                precision = draft.area_precision
                cell = coarsen(stored[0].latitude, stored[0].longitude, precision)
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
            area_precision=precision,
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

    async def put_photo(self, user_id: UUID, content: bytes) -> None:
        """Store the caller's photograph, replacing the previous one.

        The upload is decoded and written again as a small square JPEG in a worker thread, so
        nothing of the original file (its metadata in particular) is kept.

        :param user_id: The caller.
        :param content: The uploaded file.
        :raises PhotoRejectedError: If the file is too large or is not a picture.
        :raises NotFoundError: If the caller has no profile yet.
        """
        if self.photos is None or self.normalise_photo is None:
            raise RuntimeError("the photograph scenarios are not configured")
        if len(content) > PHOTO_MAX_UPLOAD_BYTES:
            raise PhotoRejectedError(PHOTO_TOO_LARGE_CODE)
        stored = await asyncio.to_thread(self.normalise_photo, content)
        if not await self.photos.put_photo(user_id, stored, self.clock()):
            raise NotFoundError(_NOT_FOUND)

    async def delete_photo(self, user_id: UUID) -> None:
        """Delete the caller's photograph; deleting a missing one is not an error.

        :param user_id: The caller.
        :raises NotFoundError: If the caller has no profile.
        """
        if self.photos is None:
            raise RuntimeError("the photograph scenarios are not configured")
        if not await self.photos.remove_photo(user_id):
            raise NotFoundError(_NOT_FOUND)

    async def get_photo(self, profile_id: UUID, viewer_user_id: UUID) -> bytes:
        """Return the photograph of a profile the caller may see.

        :param profile_id: Identifier of the profile.
        :param viewer_user_id: The caller.
        :raises NotFoundError: If there is no photograph, or the profile is hidden from the
            caller; the two are not told apart.
        :return: The stored JPEG.
        """
        if self.photos is None:
            raise RuntimeError("the photograph scenarios are not configured")
        content = await self.photos.get_photo(profile_id, viewer_user_id)
        if content is None:
            raise NotFoundError(_PHOTO_NOT_FOUND)
        return content
