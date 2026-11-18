"""Database access for profile photographs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Profile, ProfilePhoto
from app.repository.visibility import discoverable


class PhotoRepository:
    """All database operations on profile photographs.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def put_photo(self, user_id: UUID, content: bytes, now: datetime) -> bool:
        """Store or replace the photograph of a user's profile.

        :param user_id: Owner of the profile.
        :param content: The picture in its stored form.
        :param now: Time of the upload.
        :return: True if stored, False if the user has no profile to attach it to.
        """
        profile = (
            await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is None:
            return False
        photo = await self.db.get(ProfilePhoto, profile.id)
        if photo is None:
            self.db.add(ProfilePhoto(profile_id=profile.id, content=content, created_at=now))
        else:
            photo.content = content
            photo.created_at = now
        profile.photo_updated_at = now
        await self.db.commit()
        return True

    async def remove_photo(self, user_id: UUID) -> bool:
        """Delete the photograph of a user's profile.

        :param user_id: Owner of the profile.
        :return: True if the user has a profile (with or without a photograph), False otherwise.
        """
        profile = (
            await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is None:
            return False
        await self.db.execute(delete(ProfilePhoto).where(ProfilePhoto.profile_id == profile.id))
        profile.photo_updated_at = None
        await self.db.commit()
        return True

    async def get_photo(self, profile_id: UUID, viewer_user_id: UUID) -> bytes | None:
        """Load a photograph that the viewer may see.

        The owner always sees their own; anyone else sees it only while the profile is visible,
        so a hidden profile and a missing photograph give the same answer.

        :param profile_id: Identifier of the profile.
        :param viewer_user_id: The caller.
        :return: The stored picture, or None.
        """
        result = await self.db.execute(
            select(ProfilePhoto.content)
            .join(Profile, Profile.id == ProfilePhoto.profile_id)
            .where(
                ProfilePhoto.profile_id == profile_id,
                or_(Profile.user_id == viewer_user_id, discoverable()),
            )
        )
        return result.scalar_one_or_none()
