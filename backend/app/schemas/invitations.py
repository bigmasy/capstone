"""Request and response models of the invitation routes.

There is one response class per party. The recipient sees the sender under ``sender``, the
sender sees the recipient under ``recipient``; either way the other party is only a public
profile (name, district, intensity, sports). ``contact`` of the other party is null until the
invitation is accepted. No class here has a location or a functional field.
"""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.account import PublicProfile
from app.domain.invitations import InvitationView, Role, Status
from app.schemas.auth import ErrorResponse
from app.schemas.profiles import ProfilePublic, SportItem


class ContactRequiredResponse(ErrorResponse):
    """Body of the 409 that asks the caller to add a contact to the profile first."""

    code: Literal["contact_required"]


class InvitationCreate(BaseModel):
    """Body of ``POST /invitations``."""

    model_config = ConfigDict(extra="forbid")

    recipient_profile_id: UUID


class InvitationPartner(ProfilePublic):
    """The other party of an invitation: public profile fields and, once accepted, a contact."""

    contact: str | None

    @classmethod
    def from_partner(cls, profile: PublicProfile, contact: str | None) -> Self:
        """Build the partner from a public profile and the released contact.

        :param profile: Public fields of the other party.
        :param contact: Contact of the other party; the storage layer passes one only for an
            accepted invitation.
        :return: The response model.
        """
        return cls(
            id=profile.id,
            display_name=profile.display_name,
            district_code=profile.district,
            intensity=profile.intensity,
            sports=[SportItem.model_validate(entry) for entry in profile.sports],
            contact=contact,
        )


class _InvitationBase(BaseModel):
    """Fields both parties see."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: Status
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None


class InvitationIncoming(_InvitationBase):
    """An invitation as its recipient sees it; the other party is the sender."""

    direction: Literal["incoming"]
    sender: InvitationPartner | None


class InvitationOutgoing(_InvitationBase):
    """An invitation as its sender sees it; the other party is the recipient."""

    direction: Literal["outgoing"]
    recipient: InvitationPartner | None


InvitationOut = Annotated[InvitationIncoming | InvitationOutgoing, Field(discriminator="direction")]


def invitation_response(view: InvitationView) -> InvitationIncoming | InvitationOutgoing:
    """Build the response of the party that is looking at an invitation.

    :param view: The invitation with the other party attached.
    :return: The incoming form for the recipient, the outgoing form for the sender.
    """
    record = view.invitation
    partner = (
        None
        if view.partner is None
        else InvitationPartner.from_partner(view.partner, view.partner_contact)
    )
    common = {
        "id": record.id,
        "status": record.status,
        "created_at": record.created_at,
        "expires_at": record.expires_at,
        "responded_at": record.responded_at,
    }
    if view.role is Role.RECIPIENT:
        return InvitationIncoming(direction="incoming", sender=partner, **common)
    return InvitationOutgoing(direction="outgoing", recipient=partner, **common)
