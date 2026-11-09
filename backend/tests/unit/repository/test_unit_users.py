from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base
from app.domain.errors import ConflictError
from app.repository.users import UserRepository


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def users(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


async def test_create_user_returns_a_domain_account(users: UserRepository):
    account = await users.create_user("a@example.org", "hash-1")

    assert account.email == "a@example.org"
    assert account.password_hash == "hash-1"
    assert account.created_at.tzinfo is not None


async def test_email_is_stored_lower_cased(users: UserRepository):
    account = await users.create_user("Mixed.Case@Example.ORG", "hash")

    assert account.email == "mixed.case@example.org"
    assert await users.get_user_by_email("MIXED.case@example.org") == account


async def test_duplicate_email_raises_a_generic_conflict(users: UserRepository):
    await users.create_user("a@example.org", "hash")

    with pytest.raises(ConflictError) as caught:
        await users.create_user("A@example.org", "other")

    assert "a@example.org" not in caught.value.message.lower()


async def test_repository_usable_after_a_conflict(users: UserRepository):
    await users.create_user("a@example.org", "hash")
    with pytest.raises(ConflictError):
        await users.create_user("a@example.org", "hash")

    assert (await users.create_user("b@example.org", "hash")).email == "b@example.org"


async def test_lookup_by_id_and_unknown_values(users: UserRepository):
    account = await users.create_user("a@example.org", "hash")

    assert await users.get_user_by_id(account.id) == account
    assert await users.get_user_by_id(uuid4()) is None
    assert await users.get_user_by_email("nobody@example.org") is None


async def test_update_password_hash(users: UserRepository):
    account = await users.create_user("a@example.org", "old")

    await users.update_password_hash(account.id, "new")

    stored = await users.get_user_by_id(account.id)
    assert stored is not None
    assert stored.password_hash == "new"


async def test_remove_user_reports_whether_something_was_deleted(users: UserRepository):
    account = await users.create_user("a@example.org", "hash")

    assert await users.remove_user(account.id) is True
    assert await users.remove_user(account.id) is False
    assert await users.get_user_by_id(account.id) is None


def test_account_repr_hides_personal_data():
    from datetime import UTC, datetime

    from app.domain.account import Account

    account = Account(
        id=uuid4(),
        email="secret@example.org",
        password_hash="$argon2id$secret",
        created_at=datetime.now(UTC),
    )

    assert "secret" not in repr(account)
