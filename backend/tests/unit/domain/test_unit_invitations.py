"""Tests of the invitation state machine."""

import itertools
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.errors import AccessDeniedError, ConflictError, DomainError, NotFoundError
from app.domain.invitations import (
    TERMINAL_STATUSES,
    TRANSITIONS,
    Action,
    Role,
    Status,
    apply,
    effective_status,
    role_of,
)

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
FUTURE = NOW + timedelta(days=1)
PAST = NOW - timedelta(seconds=1)

# Independent statement of the rules, written as plain data for the exhaustive test
REQUIRED_ROLE = {
    Action.ACCEPT: Role.RECIPIENT,
    Action.DECLINE: Role.RECIPIENT,
    Action.CANCEL: Role.SENDER,
}
RESULT_OF_ACTION = {
    Action.ACCEPT: Status.ACCEPTED,
    Action.DECLINE: Status.DECLINED,
    Action.CANCEL: Status.CANCELLED,
}


def test_the_table_has_exactly_the_three_transitions_out_of_pending():
    assert {(key, t.role, t.target) for key, t in TRANSITIONS.items()} == {
        ((Status.PENDING, Action.ACCEPT), Role.RECIPIENT, Status.ACCEPTED),
        ((Status.PENDING, Action.DECLINE), Role.RECIPIENT, Status.DECLINED),
        ((Status.PENDING, Action.CANCEL), Role.SENDER, Status.CANCELLED),
    }


def test_terminal_states_are_everything_but_pending():
    assert TERMINAL_STATUSES == {
        Status.ACCEPTED,
        Status.DECLINED,
        Status.CANCELLED,
        Status.EXPIRED,
    }
    assert not any(status == Status.PENDING for status in TERMINAL_STATUSES)
    assert not any(key[0] in TERMINAL_STATUSES for key in TRANSITIONS)


@pytest.mark.parametrize(
    "action,role,target",
    [
        (Action.ACCEPT, Role.RECIPIENT, Status.ACCEPTED),
        (Action.DECLINE, Role.RECIPIENT, Status.DECLINED),
        (Action.CANCEL, Role.SENDER, Status.CANCELLED),
    ],
)
def test_valid_transitions_from_pending(action, role, target):
    assert apply(Status.PENDING, action, role, NOW, FUTURE) is target


def test_non_participant_gets_not_found_for_every_state_and_action():
    for status, action in itertools.product(Status, Action):
        with pytest.raises(NotFoundError):
            apply(status, action, None, NOW, FUTURE)


def test_wrong_role_gets_access_denied():
    with pytest.raises(AccessDeniedError):
        apply(Status.PENDING, Action.ACCEPT, Role.SENDER, NOW, FUTURE)
    with pytest.raises(AccessDeniedError):
        apply(Status.PENDING, Action.DECLINE, Role.SENDER, NOW, FUTURE)
    with pytest.raises(AccessDeniedError):
        apply(Status.PENDING, Action.CANCEL, Role.RECIPIENT, NOW, FUTURE)


@pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
def test_terminal_states_reject_every_action_with_conflict(status):
    for action in Action:
        with pytest.raises(ConflictError):
            apply(status, action, REQUIRED_ROLE[action], NOW, FUTURE)


def test_pending_invitation_at_or_after_the_expiry_instant_is_expired():
    assert effective_status(Status.PENDING, NOW, FUTURE) is Status.PENDING
    assert effective_status(Status.PENDING, NOW, PAST) is Status.EXPIRED
    assert effective_status(Status.PENDING, NOW, NOW) is Status.EXPIRED


@pytest.mark.parametrize("status", sorted(TERMINAL_STATUSES))
def test_terminal_statuses_do_not_change_with_time(status):
    assert effective_status(status, NOW, PAST) is status


def test_acting_on_an_expired_pending_invitation_is_a_conflict():
    for action in Action:
        with pytest.raises(ConflictError, match="expired"):
            apply(Status.PENDING, action, REQUIRED_ROLE[action], NOW, PAST)


def test_acting_on_the_expiry_instant_is_a_conflict():
    with pytest.raises(ConflictError):
        apply(Status.PENDING, Action.ACCEPT, Role.RECIPIENT, NOW, NOW)


def test_acting_one_microsecond_before_expiry_still_works():
    just_before = NOW + timedelta(microseconds=1)
    assert apply(Status.PENDING, Action.ACCEPT, Role.RECIPIENT, NOW, just_before) is Status.ACCEPTED


def test_a_participant_with_the_wrong_role_is_denied_before_expiry_is_considered():
    with pytest.raises(AccessDeniedError):
        apply(Status.PENDING, Action.ACCEPT, Role.SENDER, NOW, PAST)


def test_naive_datetimes_are_rejected():
    naive = datetime(2026, 11, 4, 12, 0)
    with pytest.raises(ValueError, match="timezone"):
        apply(Status.PENDING, Action.ACCEPT, Role.RECIPIENT, naive, FUTURE)
    with pytest.raises(ValueError, match="timezone"):
        effective_status(Status.PENDING, NOW, naive)


def test_state_machine_is_exhaustive_over_every_combination():
    # Arrange: every status, action, role (including no role) and both sides of the expiry
    combinations = itertools.product(
        Status, Action, [None, Role.SENDER, Role.RECIPIENT], [FUTURE, PAST]
    )

    for status, action, role, expires_at in combinations:
        # Act
        try:
            outcome: Status | type[DomainError] = apply(status, action, role, NOW, expires_at)
        except DomainError as error:
            outcome = type(error)

        # Assert: expected outcome from the plain statement of the rules
        if role is None:
            expected: Status | type[DomainError] = NotFoundError
        elif role is not REQUIRED_ROLE[action]:
            expected = AccessDeniedError
        elif status is Status.PENDING and expires_at is FUTURE:
            expected = RESULT_OF_ACTION[action]
        else:
            expected = ConflictError
        assert outcome is expected, (status, action, role, expires_at)


def test_domain_errors_carry_messages_without_identifiers():
    with pytest.raises(NotFoundError) as info:
        apply(Status.PENDING, Action.ACCEPT, None, NOW, FUTURE)
    assert info.value.message == "Invitation not found"


def test_role_of_identifies_sender_recipient_and_outsiders():
    sender, recipient, outsider = UUID(int=1), UUID(int=2), UUID(int=3)
    assert role_of(sender, sender_id=sender, recipient_id=recipient) is Role.SENDER
    assert role_of(recipient, sender_id=sender, recipient_id=recipient) is Role.RECIPIENT
    assert role_of(outsider, sender_id=sender, recipient_id=recipient) is None


def test_role_of_rejects_an_invitation_to_oneself():
    user = UUID(int=1)
    with pytest.raises(ValueError, match="oneself"):
        role_of(user, sender_id=user, recipient_id=user)


@given(st.sampled_from(list(Action)), st.integers(min_value=1, max_value=10_000))
def test_a_pending_invitation_changes_state_once_and_then_is_final(action, offset_seconds):
    # Arrange: the role is derived from the action and the expiry lies in the future, so no
    # generated example has to be discarded
    role = REQUIRED_ROLE[action]
    expires_at = NOW + timedelta(seconds=offset_seconds)

    # Act
    first = apply(Status.PENDING, action, role, NOW, expires_at)

    # Assert: the result is terminal and accepts nothing further
    assert first in TERMINAL_STATUSES
    for again in Action:
        with pytest.raises(ConflictError):
            apply(first, again, REQUIRED_ROLE[again], NOW, expires_at)
