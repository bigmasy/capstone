from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, Invitation, User
from app.domain.invitations import Status

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


async def saved_user(db: AsyncSession) -> UUID:
    user = User(email=f"{uuid4().hex}@example.org", password_hash="hash")
    db.add(user)
    await db.commit()
    return user.id


def make_invitation(sender: UUID, recipient: UUID, **overrides: Any) -> Invitation:
    values: dict[str, Any] = {
        "sender_user_id": sender,
        "recipient_user_id": recipient,
        "status": Status.PENDING,
        "created_at": NOW,
        "expires_at": NOW + timedelta(days=14),
    }
    values.update(overrides)
    return Invitation(**values)


async def test_invitation_is_stored_with_defaults(session: AsyncSession):
    sender, recipient = await saved_user(session), await saved_user(session)
    session.add(make_invitation(sender, recipient))

    await session.commit()

    row = (await session.execute(select(Invitation))).scalar_one()
    assert row.id is not None
    assert row.status is Status.PENDING
    assert row.responded_at is None


async def test_a_user_cannot_invite_themselves(session: AsyncSession):
    user = await saved_user(session)
    session.add(make_invitation(user, user))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_only_one_pending_invitation_per_ordered_pair(session: AsyncSession):
    sender, recipient = await saved_user(session), await saved_user(session)
    session.add_all([make_invitation(sender, recipient), make_invitation(sender, recipient)])

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_settled_invitations_do_not_block_a_new_pending_one(session: AsyncSession):
    sender, recipient = await saved_user(session), await saved_user(session)
    session.add_all(
        [
            make_invitation(sender, recipient, status=Status.DECLINED),
            make_invitation(sender, recipient, status=Status.EXPIRED),
            make_invitation(sender, recipient, status=Status.PENDING),
        ]
    )

    await session.commit()

    assert await session.scalar(select(func.count()).select_from(Invitation)) == 3


async def test_the_reverse_direction_is_a_different_pair(session: AsyncSession):
    first, second = await saved_user(session), await saved_user(session)
    session.add_all([make_invitation(first, second), make_invitation(second, first)])

    await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "archived"},
        {"expires_at": NOW},
        {"expires_at": NOW - timedelta(seconds=1)},
        {"expires_at": None},
    ],
)
async def test_constraints_reject_bad_values(session: AsyncSession, overrides: dict[str, Any]):
    sender, recipient = await saved_user(session), await saved_user(session)
    session.add(make_invitation(sender, recipient, **overrides))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_both_users_must_exist(session: AsyncSession):
    user = await saved_user(session)
    session.add(make_invitation(user, uuid4()))

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize("deleted", ["sender", "recipient"])
async def test_deleting_either_user_removes_the_invitation(session: AsyncSession, deleted: str):
    sender, recipient = await saved_user(session), await saved_user(session)
    session.add(make_invitation(sender, recipient))
    await session.commit()

    user = await session.get(User, sender if deleted == "sender" else recipient)
    await session.delete(user)
    await session.commit()

    assert await session.scalar(select(func.count()).select_from(Invitation)) == 0
