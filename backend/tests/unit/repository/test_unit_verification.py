"""Confirmation tokens: stored as digests, used once, valid for a limited time."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, EmailVerification
from app.repository.users import UserRepository
from app.repository.verification import VerificationRepository

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def tokens(session: AsyncSession) -> VerificationRepository:
    return VerificationRepository(session)


async def make_user(session: AsyncSession):
    return await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "hash")


async def test_a_token_verifies_its_account_exactly_once(
    session: AsyncSession, tokens: VerificationRepository
):
    account = await make_user(session)
    await tokens.issue(account.id, DIGEST, T0, T0 + timedelta(hours=24))
    users = UserRepository(session)

    assert await tokens.consume(DIGEST, T0 + timedelta(minutes=1)) == account.id
    assert (await users.get_user_by_id(account.id)).is_verified  # type: ignore[union-attr]
    assert await tokens.consume(DIGEST, T0 + timedelta(minutes=2)) is None


async def test_an_expired_token_is_refused_and_verifies_nothing(
    session: AsyncSession, tokens: VerificationRepository
):
    account = await make_user(session)
    await tokens.issue(account.id, DIGEST, T0, T0 + timedelta(hours=24))

    assert await tokens.consume(DIGEST, T0 + timedelta(hours=24)) is None

    assert not (await UserRepository(session).get_user_by_id(account.id)).is_verified  # type: ignore[union-attr]


async def test_an_unknown_digest_is_refused(session: AsyncSession, tokens: VerificationRepository):
    assert await tokens.consume("b" * 64, T0) is None


async def test_issuing_again_replaces_the_earlier_token(
    session: AsyncSession, tokens: VerificationRepository
):
    account = await make_user(session)
    await tokens.issue(account.id, DIGEST, T0, T0 + timedelta(hours=24))
    await tokens.issue(account.id, "c" * 64, T0 + timedelta(minutes=5), T0 + timedelta(hours=25))

    assert await tokens.consume(DIGEST, T0 + timedelta(minutes=6)) is None
    assert await tokens.consume("c" * 64, T0 + timedelta(minutes=6)) == account.id
    assert await session.scalar(select(func.count()).select_from(EmailVerification)) == 1


async def test_the_latest_issue_time_is_reported_in_utc(
    session: AsyncSession, tokens: VerificationRepository
):
    account = await make_user(session)
    assert await tokens.latest_issue_time(account.id) is None

    await tokens.issue(account.id, DIGEST, T0, T0 + timedelta(hours=24))

    assert await tokens.latest_issue_time(account.id) == T0


async def test_deleting_the_account_removes_its_tokens(
    session: AsyncSession, tokens: VerificationRepository
):
    account = await make_user(session)
    await tokens.issue(account.id, DIGEST, T0, T0 + timedelta(hours=24))

    await UserRepository(session).remove_user(account.id)

    assert await session.scalar(select(func.count()).select_from(EmailVerification)) == 0
