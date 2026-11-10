"""Invitation scenarios: sending, listing and answering invitations."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.errors import ConflictError, NotFoundError
from app.domain.invitations import (
    Action,
    ContactRequiredError,
    Direction,
    InvitationView,
    Status,
    apply,
    effective_status,
)
from app.domain.verification import EmailNotVerifiedError
from app.repository.invitations import InvitationRepository
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository

# The same text for a missing and a hidden profile: a hidden profile must not be discoverable.
_PROFILE_NOT_FOUND = "Profile not found"
_INVITATION_NOT_FOUND = "Invitation not found"
_NO_OWN_PROFILE = "Create your profile before sending invitations"
_SELF_INVITATION = "You cannot invite yourself"
_NO_LONGER_PENDING = "The invitation is no longer pending"


def _utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class InvitationService:
    """Invitation scenarios.

    The domain state machine decides who may do what and in which order the errors are
    reported; the repository performs the change atomically.

    :param invitations: Repository of invitations.
    :param profiles: Repository of profiles, used to address an invitation.
    :param users: Repository of accounts, used to check that the caller confirmed the e-mail.
    :param ttl_days: How many days an invitation can be answered.
    :param clock: Source of the current time; replaced in tests.
    """

    def __init__(
        self,
        invitations: InvitationRepository,
        profiles: ProfileRepository,
        users: UserRepository,
        ttl_days: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Keep the collaborators."""
        self.invitations = invitations
        self.profiles = profiles
        self.users = users
        self.ttl = timedelta(days=ttl_days)
        self.clock = clock

    async def create_invitation(
        self, sender_user_id: UUID, recipient_profile_id: UUID
    ) -> InvitationView:
        """Invite the owner of a visible profile.

        The sender needs a profile of their own, so the recipient has someone to answer. The
        recipient is looked up through the visible profile: a hidden profile and a missing one
        are reported identically.

        :param sender_user_id: The caller.
        :param recipient_profile_id: Profile of the person to invite.
        :raises EmailNotVerifiedError: If the caller has not confirmed the e-mail address.
        :raises ContactRequiredError: If the caller's profile has no contact.
        :raises ConflictError: If the caller has no profile, targets their own profile, or
            already has a pending invitation to this person.
        :raises NotFoundError: If the profile is missing, hidden or belongs to an unconfirmed
            account.
        :return: The new invitation as the sender sees it.
        """
        await self._require_verified(sender_user_id)
        if not await self.profiles.profile_exists(sender_user_id):
            raise ConflictError(_NO_OWN_PROFILE)
        # Only the caller's own state is checked here, before the recipient is looked up, so
        # the answer says nothing about whether the target profile exists or is hidden.
        await self._require_contact(sender_user_id)
        recipient_user_id = await self.profiles.get_visible_owner_id(recipient_profile_id)
        if recipient_user_id is None:
            raise NotFoundError(_PROFILE_NOT_FOUND)
        if recipient_user_id == sender_user_id:
            raise ConflictError(_SELF_INVITATION)
        now = self.clock()
        record = await self.invitations.create_invitation(
            sender_user_id, recipient_user_id, now, now + self.ttl
        )
        return await self._load(record.id, sender_user_id)

    async def get_invitations(
        self,
        user_id: UUID,
        direction: Direction | None,
        status: Status | None,
        skip: int,
        limit: int,
    ) -> list[InvitationView]:
        """List the caller's invitations, newest first.

        :param user_id: The caller.
        :param direction: Only incoming or only outgoing invitations; None for both.
        :param status: Status to keep as of now (a stale pending invitation counts as expired).
        :param skip: Number of invitations to skip.
        :param limit: Maximum number of invitations to return.
        :return: The invitations with the other party attached.
        """
        now = self.clock()
        views = await self.invitations.get_invitations(
            user_id, direction, status, skip, limit, now=now
        )
        return [self._as_of(view, now) for view in views]

    async def get_invitation(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Return one invitation the caller takes part in.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The caller.
        :raises NotFoundError: If the invitation does not exist or the caller is not a
            participant.
        :return: The invitation with the other party attached.
        """
        return await self._load(invitation_id, user_id)

    async def accept_invitation(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Accept an invitation addressed to the caller; the contacts are released.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The caller, who must be the recipient.
        :raises EmailNotVerifiedError: If the caller has not confirmed the e-mail address.
        :raises NotFoundError: If the caller is not a participant.
        :raises AccessDeniedError: If the caller is the sender.
        :raises ConflictError: If the invitation is expired or no longer pending.
        :raises ContactRequiredError: If the caller's profile has no contact.
        :return: The updated invitation.
        """
        await self._require_verified(user_id)
        return await self._answer(
            Action.ACCEPT,
            self.invitations.accept_invitation,
            invitation_id,
            user_id,
            require_contact=True,
        )

    async def decline_invitation(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Decline an invitation addressed to the caller.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The caller, who must be the recipient.
        :raises NotFoundError: If the caller is not a participant.
        :raises AccessDeniedError: If the caller is the sender.
        :raises ConflictError: If the invitation is expired or no longer pending.
        :return: The updated invitation.
        """
        return await self._answer(
            Action.DECLINE, self.invitations.decline_invitation, invitation_id, user_id
        )

    async def cancel_invitation(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Cancel an invitation the caller sent.

        :param invitation_id: Identifier of the invitation.
        :param user_id: The caller, who must be the sender.
        :raises NotFoundError: If the caller is not a participant.
        :raises AccessDeniedError: If the caller is the recipient.
        :raises ConflictError: If the invitation is expired or no longer pending.
        :return: The updated invitation.
        """
        return await self._answer(
            Action.CANCEL, self.invitations.cancel_invitation, invitation_id, user_id
        )

    async def _answer(
        self,
        action: Action,
        write: Callable[[UUID, UUID, datetime], Awaitable[bool]],
        invitation_id: UUID,
        user_id: UUID,
        *,
        require_contact: bool = False,
    ) -> InvitationView:
        """Decide with the state machine, then perform the guarded write."""
        now = self.clock()
        view = await self._load_stored(invitation_id, user_id)
        # Raises 404, 403 or 409 in that order; the write itself picks the target status.
        apply(view.invitation.status, action, view.role, now, view.invitation.expires_at)
        if require_contact:
            # After the 404, 403 and 409 checks: a stranger still gets 404 and a wrong role
            # never learns anything about the contact rule.
            await self._require_contact(user_id)
        if not await write(invitation_id, user_id, now):
            # Lost a race with another request: read the fresh state and report why the action
            # no longer applies.
            fresh = await self._load_stored(invitation_id, user_id)
            apply(fresh.invitation.status, action, fresh.role, now, fresh.invitation.expires_at)
            raise ConflictError(_NO_LONGER_PENDING)
        return await self._load(invitation_id, user_id)

    async def _require_verified(self, user_id: UUID) -> None:
        """Raise unless the user confirmed the e-mail address.

        Checked before anything about other people is looked up, so the answer depends only on
        the caller's own state.
        """
        if not await self.users.is_email_verified(user_id):
            raise EmailNotVerifiedError

    async def _require_contact(self, user_id: UUID) -> None:
        """Raise unless the user's profile has a contact."""
        if not await self.profiles.has_contact(user_id):
            raise ContactRequiredError

    async def _load_stored(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Load an invitation of the caller with its stored status."""
        view = await self.invitations.get_invitation_by_id(invitation_id, user_id)
        if view is None:
            raise NotFoundError(_INVITATION_NOT_FOUND)
        return view

    async def _load(self, invitation_id: UUID, user_id: UUID) -> InvitationView:
        """Load an invitation of the caller with the status as of now."""
        return self._as_of(await self._load_stored(invitation_id, user_id), self.clock())

    @staticmethod
    def _as_of(view: InvitationView, now: datetime) -> InvitationView:
        """Report a stale pending invitation as expired without touching storage."""
        record = view.invitation
        status = effective_status(record.status, now, record.expires_at)
        if status is record.status:
            return view
        return replace(view, invitation=replace(record, status=status))
