"""In-memory stand-ins for the invitation and profile lookups used by the invitation service."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.account import PublicProfile
from app.domain.errors import ConflictError
from app.domain.invitations import (
    Direction,
    InvitationRecord,
    InvitationView,
    Role,
    Status,
    role_of,
)


class FakeProfiles:
    """Knows which users have a profile and which profiles are visible."""

    def __init__(self) -> None:
        self.owners: dict[UUID, UUID] = {}  # profile id -> user id
        self.hidden: set[UUID] = set()
        self.without_contact: set[UUID] = set()  # user ids

    def add(self, user_id: UUID, *, visible: bool = True, contact: bool = True) -> UUID:
        profile_id = uuid4()
        self.owners[profile_id] = user_id
        if not contact:
            self.without_contact.add(user_id)
        if not visible:
            self.hidden.add(profile_id)
        return profile_id

    async def profile_exists(self, user_id: UUID) -> bool:
        return user_id in self.owners.values()

    async def has_contact(self, user_id: UUID) -> bool:
        return user_id in self.owners.values() and user_id not in self.without_contact

    async def get_visible_owner_id(self, profile_id: UUID) -> UUID | None:
        if profile_id in self.hidden:
            return None
        return self.owners.get(profile_id)


class FakeInvitations:
    """Mimics the repository: guarded transitions, participant filtering, one pending per pair."""

    def __init__(self) -> None:
        self.records: dict[UUID, InvitationRecord] = {}
        self.created: list[tuple[UUID, UUID, datetime, datetime]] = []
        # Called right before a guarded write, to let a test change the state under the service
        self.before_write: Callable[[], Awaitable[None]] | None = None

    async def create_invitation(
        self,
        sender_user_id: UUID,
        recipient_user_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> InvitationRecord:
        for record in self.records.values():
            if (
                (record.sender_user_id, record.recipient_user_id)
                == (sender_user_id, recipient_user_id)
                and record.status is Status.PENDING
                and record.expires_at > now
            ):
                raise ConflictError("You already have a pending invitation to this person")
        self.created.append((sender_user_id, recipient_user_id, now, expires_at))
        record = InvitationRecord(
            id=uuid4(),
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            status=Status.PENDING,
            created_at=now,
            expires_at=expires_at,
            responded_at=None,
        )
        self.records[record.id] = record
        return record

    def _view(self, record: InvitationRecord, user_id: UUID) -> InvitationView | None:
        role = role_of(user_id, record.sender_user_id, record.recipient_user_id)
        if role is None:
            return None
        return InvitationView(
            invitation=record,
            role=role,
            partner=PublicProfile(
                id=uuid4(), display_name="Partner", district=None, intensity=3, sports=()
            ),
            partner_contact="partner-contact" if record.status is Status.ACCEPTED else None,
        )

    async def get_invitation_by_id(
        self, invitation_id: UUID, user_id: UUID
    ) -> InvitationView | None:
        record = self.records.get(invitation_id)
        return None if record is None else self._view(record, user_id)

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
        views = []
        for record in self.records.values():
            view = self._view(record, user_id)
            if view is None:
                continue
            if direction is Direction.INCOMING and view.role is not Role.RECIPIENT:
                continue
            if direction is Direction.OUTGOING and view.role is not Role.SENDER:
                continue
            if status is not None and record.status is not status:
                continue
            views.append(view)
        return views[skip : skip + limit]

    async def _transition(
        self, invitation_id: UUID, user_id: UUID, role: Role, target: Status, now: datetime
    ) -> bool:
        if self.before_write is not None:
            hook, self.before_write = self.before_write, None
            await hook()
        record = self.records.get(invitation_id)
        if record is None or record.status is not Status.PENDING or record.expires_at <= now:
            return False
        if role_of(user_id, record.sender_user_id, record.recipient_user_id) is not role:
            return False
        self.records[invitation_id] = replace(record, status=target, responded_at=now)
        return True

    async def accept_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        return await self._transition(invitation_id, user_id, Role.RECIPIENT, Status.ACCEPTED, now)

    async def decline_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        return await self._transition(invitation_id, user_id, Role.RECIPIENT, Status.DECLINED, now)

    async def cancel_invitation(self, invitation_id: UUID, user_id: UUID, now: datetime) -> bool:
        return await self._transition(invitation_id, user_id, Role.SENDER, Status.CANCELLED, now)
