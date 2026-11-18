"""Database access for profiles and their sports."""

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Profile, ProfileSport
from app.domain.account import LocationRequiredError, OwnerProfile, ProfileRecord, PublicProfile
from app.domain.privacy import AreaPrecision, GridCell
from app.domain.profile import FunctionalProfile, ProfileView, SportEntry
from app.repository import private_layer
from app.repository.users import as_utc
from app.repository.visibility import discoverable


def _sports(row: Profile) -> tuple[SportEntry, ...]:
    """Map the loaded sport rows to entries ordered by sport code."""
    entries = (SportEntry(sport=item.sport, skill=item.skill) for item in row.sports)
    return tuple(sorted(entries, key=lambda entry: entry.sport.value))


class ProfileRepository:
    """All database operations on profiles.

    Reads that serve other people (``get_public_profile_by_id``) never load the private
    columns or the capability table.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def _load(self, *conditions: object) -> Profile | None:
        """Load one profile row with its sports, bypassing the identity map."""
        result = await self.db.execute(
            select(Profile)
            .where(*conditions)  # type: ignore[arg-type]
            .options(selectinload(Profile.sports))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _to_owner(self, row: Profile) -> OwnerProfile:
        """Map a row to the owner record; capabilities come from the private layer."""
        return OwnerProfile(
            id=row.id,
            user_id=row.user_id,
            display_name=row.display_name,
            district=row.district_code,
            intensity=row.intensity,
            is_visible=row.is_visible,
            sports=_sports(row),
            capabilities=await private_layer.load_capabilities(self.db, row.id),
            functional_consent_at=(
                None if row.functional_consent_at is None else as_utc(row.functional_consent_at)
            ),
            contact=row.contact,
            created_at=as_utc(row.created_at),
            updated_at=as_utc(row.updated_at),
            area_precision=row.area_precision,
            has_photo=row.photo_updated_at is not None,
        )

    async def get_profile_by_user_id(self, user_id: UUID) -> OwnerProfile | None:
        """Load the profile of a user.

        :param user_id: Owner of the profile.
        :return: The owner's view, or None if the user has no profile.
        """
        row = await self._load(Profile.user_id == user_id)
        return None if row is None else await self._to_owner(row)

    async def get_profile_by_id(self, profile_id: UUID, user_id: UUID) -> OwnerProfile | None:
        """Load a profile by identifier, only if it belongs to the user.

        :param profile_id: Identifier of the profile.
        :param user_id: Owner; a profile of someone else is reported as missing.
        :return: The owner's view, or None.
        """
        row = await self._load(Profile.id == profile_id, Profile.user_id == user_id)
        return None if row is None else await self._to_owner(row)

    async def get_public_profile_by_id(self, profile_id: UUID) -> PublicProfile | None:
        """Load the public view of a profile that its owner made visible.

        Hidden profiles are indistinguishable from missing ones. Only public columns and the
        sports are read.

        :param profile_id: Identifier of the profile.
        :return: The public view, or None if the profile is missing or hidden.
        """
        row = await self._load(Profile.id == profile_id, discoverable())
        if row is None:
            return None
        return PublicProfile(
            id=row.id,
            display_name=row.display_name,
            district=row.district_code,
            intensity=row.intensity,
            sports=_sports(row),
            has_photo=row.photo_updated_at is not None,
        )

    async def get_visible_owner_id(self, profile_id: UUID) -> UUID | None:
        """Resolve a visible profile to the user who owns it.

        Used to address an invitation. A hidden profile and a missing one give the same answer,
        and only the owner's identifier is read, never the profile content.

        :param profile_id: Identifier of the profile.
        :return: The owner's user identifier, or None if the profile is missing or hidden.
        """
        result = await self.db.execute(
            select(Profile.user_id).where(Profile.id == profile_id, discoverable())
        )
        return result.scalar_one_or_none()

    async def profile_exists(self, user_id: UUID) -> bool:
        """Tell whether a user has created a profile.

        :param user_id: Owner of the profile.
        :return: True if the user has a profile, visible or not.
        """
        result = await self.db.execute(select(Profile.id).where(Profile.user_id == user_id))
        return result.scalar_one_or_none() is not None

    async def has_contact(self, user_id: UUID) -> bool:
        """Tell whether a user has a profile with a contact, without returning the contact.

        :param user_id: Owner of the profile.
        :return: True if the profile exists and its contact is not empty.
        """
        result = await self.db.execute(
            select(Profile.id).where(
                Profile.user_id == user_id,
                Profile.contact.is_not(None),
                Profile.contact != "",
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_profile_view(self, user_id: UUID) -> ProfileView | None:
        """Load the snapshot used by matching: grid cell, sports and the private layer.

        The private layer is read only while the owner's consent is on record; without consent
        the snapshot carries no capabilities, even if rows were left behind.

        :param user_id: Owner of the profile.
        :return: The domain snapshot, or None if the user has no profile.
        """
        row = await self._load(Profile.user_id == user_id)
        if row is None:
            return None
        return ProfileView(
            id=row.id,
            sports=frozenset(_sports(row)),
            intensity=row.intensity,
            cell=GridCell(latitude=row.area_lat, longitude=row.area_lon),
            district=row.district_code,
            functional=(
                await private_layer.load_functional_profile(self.db, row.id)
                if row.functional_consent_at is not None
                else FunctionalProfile.empty()
            ),
            is_visible=row.is_visible,
        )

    async def replace_profile(self, user_id: UUID, record: ProfileRecord) -> OwnerProfile:
        """Create or fully replace the profile of a user in one transaction.

        The profile row, the sports and the capabilities are written together or not at all.

        :param user_id: Owner of the profile.
        :param record: New content; the location is already a grid cell, or None to keep the
            cell of the existing profile.
        :raises LocationRequiredError: If there is no location to keep and the record has none.
        :raises IntegrityError: If the write fails for a reason other than a concurrent first
            save by the same user.
        :return: The stored profile as its owner sees it.
        """
        try:
            await self._write(user_id, record)
        except IntegrityError:
            # Two first saves by one user race on the unique user_id; the loser retries as an
            # update of the row the winner created.
            await self.db.rollback()
            await self._write(user_id, record)
        row = await self._load(Profile.user_id == user_id)
        if row is None:
            raise RuntimeError("profile vanished after a successful write")
        return await self._to_owner(row)

    async def _write(self, user_id: UUID, record: ProfileRecord) -> None:
        """Upsert the rows of one profile and commit."""
        result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            if record.cell is None:
                # The profile was deleted after the service looked: there is no cell to keep.
                raise LocationRequiredError
            row = Profile(id=uuid4(), user_id=user_id)
            self.db.add(row)
        row.display_name = record.display_name
        row.district_code = record.district
        row.intensity = record.intensity
        row.is_visible = record.is_visible
        if record.cell is not None:
            row.area_lat = record.cell.latitude
            row.area_lon = record.cell.longitude
            if record.area_precision is not None:
                row.area_precision = record.area_precision
        row.functional_consent_at = record.functional_consent_at
        row.contact = record.contact
        await self.db.flush()
        await self.db.execute(delete(ProfileSport).where(ProfileSport.profile_id == row.id))
        self.db.add_all(
            ProfileSport(profile_id=row.id, sport=entry.sport, skill=entry.skill)
            for entry in record.sports
        )
        await private_layer.replace_capabilities(self.db, row.id, record.capabilities)
        await self.db.commit()

    async def get_stored_area(self, user_id: UUID) -> tuple[GridCell, AreaPrecision] | None:
        """Load the stored cell of a user's profile together with its grid.

        For the owner's own save only: the cell never leaves the service that asks for it.

        :param user_id: Owner of the profile.
        :return: The cell centre and the grid it belongs to, or None without a profile.
        """
        result = await self.db.execute(
            select(Profile.area_lat, Profile.area_lon, Profile.area_precision).where(
                Profile.user_id == user_id
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        return GridCell(latitude=row.area_lat, longitude=row.area_lon), row.area_precision

    async def remove_profile(self, user_id: UUID) -> bool:
        """Delete the profile of a user with its sports and capabilities.

        :param user_id: Owner of the profile.
        :return: True if a profile was deleted, False if there was none.
        """
        result = await self.db.execute(delete(Profile).where(Profile.user_id == user_id))
        await self.db.commit()
        # A DELETE statement always yields a cursor result; the typing stubs say Result.
        return bool(cast(CursorResult[Any], result).rowcount)
