from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.account import PublicProfile
from app.domain.invitations import InvitationRecord, InvitationView, Role, Status
from app.domain.profile import SportEntry
from app.domain.taxonomy import DistrictCode, SkillLevel, SportCode
from app.schemas.invitations import (
    InvitationCreate,
    InvitationIncoming,
    InvitationOutgoing,
    invitation_response,
)

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def make_view(role: Role, *, contact: str | None = None, partner: bool = True) -> InvitationView:
    record = InvitationRecord(
        id=uuid4(),
        sender_user_id=uuid4(),
        recipient_user_id=uuid4(),
        status=Status.ACCEPTED if contact else Status.PENDING,
        created_at=NOW,
        expires_at=NOW + timedelta(days=14),
        responded_at=None,
    )
    profile = PublicProfile(
        id=uuid4(),
        display_name="Orest",
        district=DistrictCode.KYIV_PODILSKYI,
        intensity=3,
        sports=(SportEntry(SportCode.SWIMMING, SkillLevel.BEGINNER),),
    )
    return InvitationView(
        invitation=record, role=role, partner=profile if partner else None, partner_contact=contact
    )


def test_the_recipient_gets_the_incoming_form_with_the_sender():
    response = invitation_response(make_view(Role.RECIPIENT))

    assert isinstance(response, InvitationIncoming)
    assert response.direction == "incoming"
    assert response.sender is not None and response.sender.display_name == "Orest"
    assert "recipient" not in response.model_dump()


def test_the_sender_gets_the_outgoing_form_with_the_recipient():
    response = invitation_response(make_view(Role.SENDER))

    assert isinstance(response, InvitationOutgoing)
    assert response.direction == "outgoing"
    assert response.recipient is not None
    assert "sender" not in response.model_dump()


def test_the_contact_is_carried_only_when_the_view_holds_one():
    pending = invitation_response(make_view(Role.SENDER))
    accepted = invitation_response(make_view(Role.SENDER, contact="t.me/partner"))

    assert isinstance(pending, InvitationOutgoing) and isinstance(accepted, InvitationOutgoing)
    assert pending.recipient is not None and pending.recipient.contact is None
    assert accepted.recipient is not None and accepted.recipient.contact == "t.me/partner"


def test_a_missing_partner_profile_becomes_null():
    response = invitation_response(make_view(Role.RECIPIENT, partner=False))

    assert isinstance(response, InvitationIncoming)
    assert response.sender is None


def test_the_response_has_no_location_or_functional_field():
    dump = invitation_response(make_view(Role.SENDER)).model_dump()

    assert set(dump) == {
        "id",
        "status",
        "created_at",
        "expires_at",
        "responded_at",
        "direction",
        "recipient",
    }
    assert set(dump["recipient"]) == {
        "id",
        "display_name",
        "district_code",
        "intensity",
        "sports",
        "has_photo",
        "contact",
    }


def test_a_free_text_note_is_not_accepted():
    with pytest.raises(ValidationError):
        InvitationCreate.model_validate({"recipient_profile_id": str(uuid4()), "message": "hi"})


def test_unknown_fields_are_forbidden():
    with pytest.raises(ValidationError):
        InvitationCreate.model_validate({"recipient_profile_id": str(uuid4()), "sender": "x"})


def test_repr_of_the_records_keeps_free_text_and_contact_out():
    view = make_view(Role.SENDER, contact="secret-contact")

    assert "secret-contact" not in repr(view)
    assert "Hello" not in repr(view)
