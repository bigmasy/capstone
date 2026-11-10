"""Reset tokens: stored as digests, used once, time-limited; the password changes with them."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, PasswordReset
from app.repository.password_reset import PasswordResetRepository
from app.repository.users import UserRepository

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64
NEW_HASH = "new-hash"


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def resets(session: AsyncSession) -> PasswordResetRepository:
    return PasswordResetRepository(session)


async def make_user(session: AsyncSession):
    return await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "old-hash")


async def test_a_token_changes_the_password_exactly_once(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))

    assert await resets.consume(DIGEST, T0 + timedelta(minutes=1), NEW_HASH) == account.id

    changed = await UserRepository(session).get_user_by_id(account.id)
    assert changed is not None
    assert changed.password_hash == NEW_HASH
    assert changed.password_changed_at == T0 + timedelta(minutes=1)
    assert await resets.consume(DIGEST, T0 + timedelta(minutes=2), "again") is None
    again = await UserRepository(session).get_user_by_id(account.id)
    assert again is not None and again.password_hash == NEW_HASH


async def test_the_link_proves_the_mailbox_so_the_account_becomes_confirmed(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    assert not account.is_verified
    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))

    await resets.consume(DIGEST, T0 + timedelta(minutes=1), NEW_HASH)

    changed = await UserRepository(session).get_user_by_id(account.id)
    assert changed is not None and changed.email_verified_at == T0 + timedelta(minutes=1)


async def test_an_account_confirmed_earlier_keeps_its_confirmation_time(
    session: AsyncSession, resets: PasswordResetRepository
):
    users = UserRepository(session)
    account = await users.create_user(f"{uuid4().hex}@example.org", "old", verified_at=T0)
    await resets.issue(account.id, DIGEST, T0 + timedelta(days=1), T0 + timedelta(days=1, hours=1))

    await resets.consume(DIGEST, T0 + timedelta(days=1, minutes=1), NEW_HASH)

    changed = await users.get_user_by_id(account.id)
    assert changed is not None and changed.email_verified_at == T0


async def test_an_expired_token_is_refused_and_changes_nothing(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))

    assert await resets.consume(DIGEST, T0 + timedelta(hours=1), NEW_HASH) is None

    unchanged = await UserRepository(session).get_user_by_id(account.id)
    assert unchanged is not None
    assert unchanged.password_hash == "old-hash"
    assert unchanged.password_changed_at is None


async def test_an_unknown_digest_is_refused(session: AsyncSession, resets: PasswordResetRepository):
    assert await resets.consume("b" * 64, T0, NEW_HASH) is None


async def test_issuing_again_replaces_the_earlier_token(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))
    await resets.issue(account.id, "c" * 64, T0 + timedelta(minutes=5), T0 + timedelta(hours=2))

    assert await resets.consume(DIGEST, T0 + timedelta(minutes=6), NEW_HASH) is None
    assert await resets.consume("c" * 64, T0 + timedelta(minutes=6), NEW_HASH) == account.id
    assert await session.scalar(select(func.count()).select_from(PasswordReset)) == 1


async def test_the_latest_issue_time_is_reported_in_utc(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    assert await resets.latest_issue_time(account.id) is None

    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))

    assert await resets.latest_issue_time(account.id) == T0


async def test_deleting_the_account_removes_its_tokens(
    session: AsyncSession, resets: PasswordResetRepository
):
    account = await make_user(session)
    await resets.issue(account.id, DIGEST, T0, T0 + timedelta(hours=1))

    await UserRepository(session).remove_user(account.id)

    assert await session.scalar(select(func.count()).select_from(PasswordReset)) == 0
