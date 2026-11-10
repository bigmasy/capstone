"""Sending, listing and answering invitations."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, InvitationServiceDep
from app.domain.invitations import Direction
from app.domain.invitations import Status as InvitationStatus
from app.schemas.auth import ErrorResponse
from app.schemas.invitations import (
    ContactRequiredResponse,
    EmailNotVerifiedResponse,
    InvitationCreate,
    InvitationOut,
    invitation_response,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT: dict[int | str, dict[str, Any]] = {status.HTTP_409_CONFLICT: {"model": ErrorResponse}}
# Operations that need a contact on the caller's profile: the 409 body is either the usual
# error or the one with the machine code.
_CONFLICT_OR_CONTACT: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {"model": ErrorResponse | ContactRequiredResponse}
}
_FORBIDDEN: dict[int | str, dict[str, Any]] = {status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}}
# Sending and accepting need a confirmed e-mail address: the 403 body is either the usual error
# (accepting as the sender) or the one with the machine code.
_FORBIDDEN_OR_UNVERIFIED: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse | EmailNotVerifiedResponse}
}


@router.post(
    "",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    responses={**_UNAUTHORIZED, **_FORBIDDEN_OR_UNVERIFIED, **_NOT_FOUND, **_CONFLICT_OR_CONTACT},
)
async def post_invitation(
    body: InvitationCreate, current: CurrentUser, service: InvitationServiceDep
) -> InvitationOut:
    """Invite the owner of a visible profile to train together.

    A hidden profile is answered exactly like a missing one (404).

    :param body: The profile to invite.
    :param current: The authenticated caller; needs a profile of their own.
    :param service: Invitation service.
    :raises NotFoundError: If the profile is missing or hidden (answered with 404).
    :raises ConflictError: If the caller has no profile, targets themselves or already has a
        pending invitation to this person (answered with 409).
    :raises ContactRequiredError: If the caller's profile has no contact (409, code
        ``contact_required``).
    :return: The new invitation as the sender sees it.
    """
    view = await service.create_invitation(current.id, body.recipient_profile_id)
    return invitation_response(view)


@router.get("", response_model=list[InvitationOut], responses=_UNAUTHORIZED)
async def get_invitations(
    current: CurrentUser,
    service: InvitationServiceDep,
    direction: Direction | None = None,
    status_filter: Annotated[InvitationStatus | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0, le=10_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[InvitationOut]:
    """List the caller's invitations, newest first.

    :param current: The authenticated caller.
    :param service: Invitation service.
    :param direction: Only ``incoming`` or only ``outgoing``; both when omitted.
    :param status_filter: Keep one status; a stale pending invitation counts as expired.
    :param skip: Number of invitations to skip.
    :param limit: Maximum number of invitations to return.
    :return: The caller's invitations.
    """
    views = await service.get_invitations(current.id, direction, status_filter, skip, limit)
    return [invitation_response(view) for view in views]


@router.get(
    "/{invitation_id}",
    response_model=InvitationOut,
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def get_invitation(
    invitation_id: UUID, current: CurrentUser, service: InvitationServiceDep
) -> InvitationOut:
    """Return one invitation the caller sent or received.

    :param invitation_id: Identifier of the invitation.
    :param current: The authenticated caller.
    :param service: Invitation service.
    :raises NotFoundError: If it does not exist or the caller is not a participant (404).
    :return: The invitation as the caller sees it.
    """
    return invitation_response(await service.get_invitation(invitation_id, current.id))


@router.post(
    "/{invitation_id}/accept",
    response_model=InvitationOut,
    responses={
        **_UNAUTHORIZED,
        **_FORBIDDEN_OR_UNVERIFIED,
        **_NOT_FOUND,
        **_CONFLICT_OR_CONTACT,
    },
)
async def accept_invitation(
    invitation_id: UUID, current: CurrentUser, service: InvitationServiceDep
) -> InvitationOut:
    """Accept an invitation addressed to the caller; both contacts are released.

    :param invitation_id: Identifier of the invitation.
    :param current: The authenticated caller, who must be the recipient.
    :param service: Invitation service.
    :raises NotFoundError: If the caller is not a participant (404).
    :raises AccessDeniedError: If the caller is the sender (403).
    :raises ConflictError: If the invitation is expired or no longer pending (409).
    :raises ContactRequiredError: If the caller's profile has no contact (409, code
        ``contact_required``).
    :return: The updated invitation.
    """
    return invitation_response(await service.accept_invitation(invitation_id, current.id))


@router.post(
    "/{invitation_id}/decline",
    response_model=InvitationOut,
    responses={**_UNAUTHORIZED, **_FORBIDDEN, **_NOT_FOUND, **_CONFLICT},
)
async def decline_invitation(
    invitation_id: UUID, current: CurrentUser, service: InvitationServiceDep
) -> InvitationOut:
    """Decline an invitation addressed to the caller.

    :param invitation_id: Identifier of the invitation.
    :param current: The authenticated caller, who must be the recipient.
    :param service: Invitation service.
    :raises NotFoundError: If the caller is not a participant (404).
    :raises AccessDeniedError: If the caller is the sender (403).
    :raises ConflictError: If the invitation is expired or no longer pending (409).
    :return: The updated invitation.
    """
    return invitation_response(await service.decline_invitation(invitation_id, current.id))


@router.post(
    "/{invitation_id}/cancel",
    response_model=InvitationOut,
    responses={**_UNAUTHORIZED, **_FORBIDDEN, **_NOT_FOUND, **_CONFLICT},
)
async def cancel_invitation(
    invitation_id: UUID, current: CurrentUser, service: InvitationServiceDep
) -> InvitationOut:
    """Cancel an invitation the caller sent.

    :param invitation_id: Identifier of the invitation.
    :param current: The authenticated caller, who must be the sender.
    :param service: Invitation service.
    :raises NotFoundError: If the caller is not a participant (404).
    :raises AccessDeniedError: If the caller is the recipient (403).
    :raises ConflictError: If the invitation is expired or no longer pending (409).
    :return: The updated invitation.
    """
    return invitation_response(await service.cancel_invitation(invitation_id, current.id))
