"""Invitation state machine: allowed transitions, who may perform them, and lazy expiry.

The rules are a table, not branches in a service. The persistence layer must still make the
change atomic (an update guarded by the current status), because two requests can pass the
check at the same time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from app.domain.account import PublicProfile
from app.domain.errors import AccessDeniedError, ConflictError, NotFoundError

CONTACT_REQUIRED_MESSAGE = "Add a contact to your profile to send and accept invitations"
CONTACT_REQUIRED_CODE = "contact_required"


class ContactRequiredError(ConflictError):
    """The acting user has no contact on the profile (HTTP 409 with a machine-readable code).

    The contact is the only channel that opens after an invitation is accepted, so a person
    without one can neither send nor accept an invitation. The message is fixed and names
    nothing about the other party.
    """

    code = CONTACT_REQUIRED_CODE

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(CONTACT_REQUIRED_MESSAGE)


class Status(StrEnum):
    """Status of an invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Action(StrEnum):
    """Action a participant can perform on an invitation."""

    ACCEPT = "accept"
    DECLINE = "decline"
    CANCEL = "cancel"


class Role(StrEnum):
    """Role of a participant in an invitation."""

    SENDER = "sender"
    RECIPIENT = "recipient"


class Direction(StrEnum):
    """Which side of the invitations of a user to list."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"


@dataclass(frozen=True, slots=True)
class Transition:
    """Who may perform an action and the status it leads to."""

    role: Role
    target: Status


TRANSITIONS = MappingProxyType(
    {
        (Status.PENDING, Action.ACCEPT): Transition(Role.RECIPIENT, Status.ACCEPTED),
        (Status.PENDING, Action.DECLINE): Transition(Role.RECIPIENT, Status.DECLINED),
        (Status.PENDING, Action.CANCEL): Transition(Role.SENDER, Status.CANCELLED),
    }
)

# Every status without an outgoing transition; EXPIRED is reached only through time
TERMINAL_STATUSES = frozenset(Status) - {source for source, _ in TRANSITIONS}

# One role per action: derived from the table so the two cannot disagree
_ROLE_OF_ACTION = {action: transition.role for (_, action), transition in TRANSITIONS.items()}


def _require_aware(moment: datetime) -> None:
    """Reject naive datetimes, which cannot be compared safely with stored UTC instants."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("datetimes must carry a timezone")


def role_of(user_id: UUID, sender_id: UUID, recipient_id: UUID) -> Role | None:
    """Return the role of a user in an invitation, or None for an outsider.

    :param user_id: The user acting.
    :param sender_id: Owner of the profile that sent the invitation.
    :param recipient_id: Owner of the profile that received it.
    :raises ValueError: If sender and recipient are the same user.
    :return: Sender, recipient, or None if the user is not a participant.
    """
    if sender_id == recipient_id:
        raise ValueError("an invitation to oneself is not valid")
    if user_id == sender_id:
        return Role.SENDER
    if user_id == recipient_id:
        return Role.RECIPIENT
    return None


def effective_status(status: Status, now: datetime, expires_at: datetime) -> Status:
    """Return the status as of ``now``: a pending invitation past its expiry is expired.

    Expiry is lazy: nothing changes in storage until someone reads or acts. The invitation
    is expired from the expiry instant on (``now >= expires_at``). Callers that read an
    invitation should show this status and may persist it.

    :param status: Stored status.
    :param now: Current time, timezone-aware.
    :param expires_at: Expiry instant, timezone-aware.
    :raises ValueError: If a datetime is naive.
    :return: EXPIRED for a stale pending invitation, otherwise the stored status.
    """
    _require_aware(now)
    _require_aware(expires_at)
    if status is Status.PENDING and now >= expires_at:
        return Status.EXPIRED
    return status


def apply(
    state: Status,
    action: Action,
    actor_role: Role | None,
    now: datetime,
    expires_at: datetime,
) -> Status:
    """Perform an action on an invitation and return the new status.

    Checks run in this order, so that existence is not revealed to outsiders and a wrong
    role never learns the state: participant (404), role (403), state and expiry (409).

    :param state: Stored status of the invitation.
    :param action: Action requested.
    :param actor_role: Role of the actor, or None if the actor is not a participant.
    :param now: Current time, timezone-aware.
    :param expires_at: Expiry instant, timezone-aware.
    :raises NotFoundError: If the actor is not a participant.
    :raises AccessDeniedError: If the actor's role may not perform the action.
    :raises ConflictError: If the invitation is expired or no longer pending.
    :raises ValueError: If a datetime is naive.
    :return: The new status.
    """
    if actor_role is None:
        raise NotFoundError("Invitation not found")
    if actor_role is not _ROLE_OF_ACTION[action]:
        raise AccessDeniedError("This action is not available for your role")
    current = effective_status(state, now, expires_at)
    transition = TRANSITIONS.get((current, action))
    if transition is None:
        if current is Status.EXPIRED:
            raise ConflictError("The invitation has expired")
        raise ConflictError("The invitation is no longer pending")
    return transition.target


@dataclass(frozen=True, slots=True, kw_only=True)
class InvitationRecord:
    """An invitation as stored: who invited whom, the stored status and the times.

    :param id: Invitation identifier.
    :param sender_user_id: User who sent the invitation.
    :param recipient_user_id: User who received it.
    :param status: Stored status; a stale pending invitation is reported as expired by
        :func:`effective_status`, not by this field.
    :param created_at: Creation time (UTC).
    :param expires_at: Instant from which the invitation can no longer be answered (UTC).
    :param responded_at: When the recipient or the sender settled it, or None.
    """

    id: UUID
    sender_user_id: UUID
    recipient_user_id: UUID
    status: Status
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class InvitationView:
    """An invitation as one of its participants sees it, with the other party attached.

    The partner carries public profile fields only. ``partner_contact`` is filled in solely for
    an accepted invitation; the storage layer enforces that, so no later layer has to remember it.

    :param invitation: The stored invitation.
    :param role: Role of the viewer in the invitation.
    :param partner: Public profile of the other party, or None if that profile no longer exists.
    :param partner_contact: Contact of the other party, released only after acceptance.
    """

    invitation: InvitationRecord
    role: Role
    partner: PublicProfile | None
    partner_contact: str | None = field(repr=False, default=None)
