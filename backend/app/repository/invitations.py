"""Database access for invitations."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, CursorResult, and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.database.models import Invitation, Profile, ProfileSport
from app.domain.account import PublicProfile
from app.domain.errors import ConflictError, NotFoundError
from app.domain.invitations import (
    Direction,
    InvitationRecord,
    InvitationView,
    Status,
    role_of,
)
from app.domain.profile import SportEntry
from app.repository.users import as_utc
from app.repository.visibility import discoverable

_DUPLICATE = "You already have a pending invitation to this person"
_RECIPIENT_GONE = "Profile not found"


def _to_record(row: Invitation) -> InvitationRecord:
    """Map an ORM row to the domain record."""
    return InvitationRecord(
        id=row.id,
        sender_user_id=row.sender_user_id,
        recipient_user_id=row.recipient_user_id,
        status=row.status,
        created_at=as_utc(row.created_at),
        expires_at=as_utc(row.expires_at),
        responded_at=None if row.responded_at is None else as_utc(row.responded_at),
    )


def _partner_user_id(row: Invitation, user_id: UUID) -> UUID:
    """Return the user on the other side of an invitation."""
    return row.recipient_user_id if row.sender_user_id == user_id else row.sender_user_id


def _status_condition(status: Status, now: datetime) -> ColumnElement[bool]:
    """Build the filter for an effective status; time decides pending versus expired.

    A pending row past its expiry instant is expired even though storage still says pending, so
    the filter has to look at the clock and not only at the column.
    """
    if status is Status.PENDING:
        return and_(Invitation.status == Status.PENDING, Invitation.expires_at > now)
    if status is Status.EXPIRED:
        return or_(
            Invitation.status == Status.EXPIRED,
            and_(Invitation.status == Status.PENDING, Invitation.expires_at <= now),
        )
    return Invitation.status == status


class InvitationRepository:
    """All database operations on invitations.

    Every read takes the acting user and returns only invitations the user takes part in; a
    foreign invitation looks exactly like a missing one. The profile of the other party is read
    through the public columns only, never the location or the private layer.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def create_invitation(
        self,
        sender_user_id: UUID,
        recipient_user_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> InvitationRecord:
        """Create a pending invitation, first retiring a stale one of the same pair.

        A pending invitation past its expiry still occupies the unique slot of the pair, so it is
        marked expired in the same transaction. The unique index settles a race between two
        simultaneous invitations: one insert wins, the other becomes a conflict.

        :param sender_user_id: User who invites.
        :param recipient_user_id: User who is invited.
        :param now: Current time.
        :param expires_at: Instant from which the invitation can no longer be answered.
        :raises ConflictError: If the sender already has a pending invitation to the recipient.
        :raises NotFoundError: If the recipient disappeared while the invitation was written.
        :return: The stored invitation.
        """
        now = as_utc(now)
        await self.db.execute(
            update(Invitation)
            .where(
                Invitation.sender_user_id == sender_user_id,
                Invitation.recipient_user_id == recipient_user_id,
                Invitation.status == Status.PENDING,
                Invitation.expires_at <= now,
            )
            .values(status=Status.EXPIRED)
            .execution_options(synchronize_session=False)
        )
        row = Invitation(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            status=Status.PENDING,
            created_at=now,
            expires_at=as_utc(expires_at),
        )
        self.db.add(row)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            if await self._has_pending(sender_user_id, recipient_user_id, now):
                raise ConflictError(_DUPLICATE) from exc
            # The pair is free, so the failure was the foreign key: the recipient was deleted
            # between the lookup and the insert.
            raise NotFoundError(_RECIPIENT_GONE) from exc
        return _to_record(row)

    async def _has_pending(
        self, sender_user_id: UUID, recipient_user_id: UUID, now: datetime
    ) -> bool:
        """Tell whether the ordered pair has an unexpired pending invitation."""
        result = await self.db.execute(
            select(Invitation.id).where(
                Invitation.sender_user_id == sender_user_id,
                Invitation.recipient_user_id == recipient_user_id,
                Invitation.status == Status.PENDING,
                Invitation.expires_at > now,
            )
        )
        return result.first() is not None

    async def get_invitation_by_id(
        self, invitation_id: UUID, user_id: UUID
    ) -> InvitationView | None:
        """Load an invitation if the user is its sender or its recipient.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The acting user; an invitation between other people is reported as
            missing.
        :return: The invitation with the other party attached, or None. The status is the stored
            one; lazy expiry is applied by the caller.
        """
        result = await self.db.execute(
            select(Invitation)
            .where(
                Invitation.id == invitation_id,
                or_(Invitation.sender_user_id == user_id, Invitation.recipient_user_id == user_id),
            )
            .execution_options(populate_existing=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return (await self._views([row], user_id))[0]

    async def get_invitations(
        self,
        user_id: UUID,
        direction: Direction | None,
        status: Status | None,
        skip: int,
        limit: int,
        *,
        now: datetime,
    ) -> list[InvitationView]:
        """List the invitations of a user, newest first.

        :param user_id: The acting user.
        :param direction: Only incoming or only outgoing invitations; None for both.
        :param status: Effective status to keep, or None for all.
        :param skip: Number of invitations to skip.
        :param limit: Maximum number of invitations to return.
        :param now: Current time, used to tell pending from expired.
        :return: Invitations with the other party attached; the status is the stored one.
        """
        now = as_utc(now)
        if direction is Direction.INCOMING:
            party: ColumnElement[bool] = Invitation.recipient_user_id == user_id
        elif direction is Direction.OUTGOING:
            party = Invitation.sender_user_id == user_id
        else:
            party = or_(
                Invitation.sender_user_id == user_id, Invitation.recipient_user_id == user_id
            )
        query = select(Invitation).where(party)
        if status is not None:
            query = query.where(_status_condition(status, now))
        query = (
            query.order_by(Invitation.created_at.desc(), Invitation.id.desc())
            .offset(skip)
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        rows = (await self.db.execute(query)).scalars().all()
        return await self._views(rows, user_id)

    async def accept_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        """Accept a pending, unexpired invitation addressed to the user.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The recipient.
        :param now: Current time; the invitation must expire strictly after it.
        :return: True if this call changed the invitation, False if it no longer qualified.
        """
        return await self._transition(
            invitation_id, user_id, Invitation.recipient_user_id, Status.ACCEPTED, now
        )

    async def decline_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        """Decline a pending, unexpired invitation addressed to the user.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The recipient.
        :param now: Current time; the invitation must expire strictly after it.
        :return: True if this call changed the invitation, False if it no longer qualified.
        """
        return await self._transition(
            invitation_id, user_id, Invitation.recipient_user_id, Status.DECLINED, now
        )

    async def cancel_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        """Cancel a pending, unexpired invitation the user sent.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The sender.
        :param now: Current time; the invitation must expire strictly after it.
        :return: True if this call changed the invitation, False if it no longer qualified.
        """
        return await self._transition(
            invitation_id, user_id, Invitation.sender_user_id, Status.CANCELLED, now
        )

    async def _transition(
        self,
        invitation_id: UUID,
        user_id: UUID,
        party: InstrumentedAttribute[UUID],
        target: Status,
        now: datetime,
    ) -> bool:
        """Move a pending invitation to ``target`` in one guarded statement and commit.

        The status, the expiry and the acting party are all part of the WHERE clause, so the
        decision and the write cannot be separated by a concurrent request: of two simultaneous
        calls exactly one matches a row.
        """
        now = as_utc(now)
        result = await self.db.execute(
            update(Invitation)
            .where(
                Invitation.id == invitation_id,
                Invitation.status == Status.PENDING,
                Invitation.expires_at > now,
                party == user_id,
            )
            .values(status=target, responded_at=now)
            .execution_options(synchronize_session=False)
        )
        await self.db.commit()
        # An UPDATE statement always yields a cursor result; the typing stubs say Result.
        return cast(CursorResult[Any], result).rowcount == 1

    async def _views(self, rows: Sequence[Invitation], user_id: UUID) -> list[InvitationView]:
        """Attach the other party to invitations, reading public profile columns only.

        The contact is fetched solely for accepted invitations. For any other status it is never
        read, so it cannot reach a response by mistake.
        """
        partner_ids = {_partner_user_id(row, user_id) for row in rows}
        accepted_ids = {
            _partner_user_id(row, user_id) for row in rows if row.status is Status.ACCEPTED
        }
        partners = await self._load_partners(partner_ids)
        contacts = await self._load_contacts(accepted_ids)
        views: list[InvitationView] = []
        for row in rows:
            partner_id = _partner_user_id(row, user_id)
            role = role_of(user_id, row.sender_user_id, row.recipient_user_id)
            if role is None:
                raise RuntimeError("an invitation outside the acting user's scope was loaded")
            views.append(
                InvitationView(
                    invitation=_to_record(row),
                    role=role,
                    partner=partners.get(partner_id),
                    partner_contact=contacts.get(partner_id),
                )
            )
        return views

    async def _load_partners(self, user_ids: set[UUID]) -> dict[UUID, PublicProfile]:
        """Load the public profile fields of users, keyed by user identifier."""
        if not user_ids:
            return {}
        # Only public columns are selected: no coordinates, no consent time, no contact.
        profile_rows = (
            await self.db.execute(
                select(
                    Profile.id,
                    Profile.user_id,
                    Profile.display_name,
                    Profile.district_code,
                    Profile.intensity,
                    # A photograph is announced only where the route that serves it would answer
                    (Profile.photo_updated_at.is_not(None) & discoverable()).label("has_photo"),
                ).where(Profile.user_id.in_(user_ids))
            )
        ).all()
        sports: dict[UUID, list[SportEntry]] = {row.id: [] for row in profile_rows}
        if sports:
            sport_rows = (
                await self.db.execute(
                    select(ProfileSport.profile_id, ProfileSport.sport, ProfileSport.skill).where(
                        ProfileSport.profile_id.in_(sports)
                    )
                )
            ).all()
            for sport_row in sport_rows:
                sports[sport_row.profile_id].append(SportEntry(sport_row.sport, sport_row.skill))
        return {
            row.user_id: PublicProfile(
                id=row.id,
                display_name=row.display_name,
                district=row.district_code,
                intensity=row.intensity,
                sports=tuple(sorted(sports[row.id], key=lambda entry: entry.sport.value)),
                has_photo=bool(row.has_photo),
            )
            for row in profile_rows
        }

    async def _load_contacts(self, user_ids: set[UUID]) -> dict[UUID, str]:
        """Load the contacts of users who have one, keyed by user identifier."""
        if not user_ids:
            return {}
        rows = (
            await self.db.execute(
                select(Profile.user_id, Profile.contact).where(
                    Profile.user_id.in_(user_ids), Profile.contact.is_not(None)
                )
            )
        ).all()
        return {row.user_id: row.contact for row in rows}
