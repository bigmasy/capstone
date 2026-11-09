"""Invitations on a real PostgreSQL/PostGIS database, created by the migrations."""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.config import get_settings
from app.database.models import Invitation
from app.domain.errors import ConflictError
from app.domain.invitations import Status
from app.repository.invitations import InvitationRepository
from app.repository.users import UserRepository

pytestmark = pytest.mark.postgis

BACKEND_DIR = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
EXPIRES = NOW + timedelta(days=14)


@pytest.fixture
def migrated_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Rebuild the schema from the migrations on the test database."""
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "m" * 40)
    monkeypatch.setenv("DB_URL", url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield url
    command.downgrade(config, "base")


@pytest.fixture
async def pg_engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_url)
    yield engine
    await engine.dispose()


async def make_user_id(session: AsyncSession) -> UUID:
    return (await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "hash")).id


async def invite(repo: InvitationRepository, sender: UUID, recipient: UUID) -> UUID:
    return (await repo.create_invitation(sender, recipient, NOW, EXPIRES)).id


def test_alembic_check_is_clean_after_the_invitations_revision(
    migrated_url: str, monkeypatch: pytest.MonkeyPatch
):
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    command.check(config)


async def test_the_pending_pair_rule_is_a_partial_unique_index(pg_engine: AsyncEngine):
    async with pg_engine.connect() as connection:
        definition = (
            await connection.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename = 'invitations' AND indexname = 'uq_invitations_pending_pair'"
                )
            )
        ).scalar_one()
        constraints = {
            row[0]
            for row in await connection.execute(
                text("SELECT conname FROM pg_constraint WHERE conrelid = 'invitations'::regclass")
            )
        }
        columns = {
            row[0]: (row[1], row[2])
            for row in await connection.execute(
                text(
                    "SELECT column_name, data_type, character_maximum_length "
                    "FROM information_schema.columns WHERE table_name = 'invitations'"
                )
            )
        }

    assert "UNIQUE" in definition
    assert "sender_user_id, recipient_user_id" in definition
    assert "WHERE" in definition and "'pending'" in definition
    assert {
        "pk_invitations",
        "ck_invitations_status",
        "ck_invitations_no_self_invitation",
        "ck_invitations_expiry_after_creation",
        "fk_invitations_sender_user_id_users",
        "fk_invitations_recipient_user_id_users",
    } <= constraints
    assert columns["expires_at"][0] == "timestamp with time zone"
    assert "message" not in columns
    assert columns["status"] == ("character varying", 50)


async def test_a_second_pending_invitation_is_refused_but_a_settled_one_is_not_counted(
    pg_engine: AsyncEngine,
):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        sender, recipient = await make_user_id(session), await make_user_id(session)
        repo = InvitationRepository(session)
        first = await invite(repo, sender, recipient)

        with pytest.raises(ConflictError):
            await invite(repo, sender, recipient)
        assert await repo.decline_invitation(first, recipient, NOW) is True
        await invite(repo, sender, recipient)

        count = await session.scalar(select(func.count()).select_from(Invitation))
    assert count == 2


async def test_a_stale_pending_invitation_is_retired_by_a_new_one(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        sender, recipient = await make_user_id(session), await make_user_id(session)
        repo = InvitationRepository(session)
        first = await invite(repo, sender, recipient)

        later = EXPIRES + timedelta(seconds=1)
        await repo.create_invitation(sender, recipient, later, later + timedelta(days=14))

        stored = await session.scalar(select(Invitation.status).where(Invitation.id == first))
    assert stored is Status.EXPIRED


async def test_database_rejects_a_self_invitation_and_a_bad_status(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        user = await make_user_id(session)

        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO invitations (id, sender_user_id, recipient_user_id, status, "
                    "created_at, expires_at) VALUES (:id, :u, :u, 'pending', now(), "
                    "now() + interval '1 day')"
                ),
                {"id": uuid4(), "u": user},
            )
        await session.rollback()
        other = await make_user_id(session)
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO invitations (id, sender_user_id, recipient_user_id, status, "
                    "created_at, expires_at) VALUES (:id, :a, :b, 'archived', now(), "
                    "now() + interval '1 day')"
                ),
                {"id": uuid4(), "a": user, "b": other},
            )


async def test_deleting_a_user_cascades_to_invitations(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        sender, recipient = await make_user_id(session), await make_user_id(session)
        await invite(InvitationRepository(session), sender, recipient)

        await UserRepository(session).remove_user(sender)

        assert await session.scalar(select(func.count()).select_from(Invitation)) == 0


@pytest.mark.parametrize("racers", [2, 8])
async def test_simultaneous_accepts_leave_exactly_one_winner(pg_engine: AsyncEngine, racers: int):
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user_id(setup), await make_user_id(setup)
        invitation_id = await invite(InvitationRepository(setup), sender, recipient)

    async def attempt() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).accept_invitation(
                invitation_id, recipient, NOW
            )

    results = await asyncio.gather(*(attempt() for _ in range(racers)))

    assert sorted(results) == [False] * (racers - 1) + [True]


async def test_accept_and_cancel_racing_leave_one_outcome(pg_engine: AsyncEngine):
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user_id(setup), await make_user_id(setup)
        invitation_id = await invite(InvitationRepository(setup), sender, recipient)

    async def accept() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).accept_invitation(
                invitation_id, recipient, NOW
            )

    async def cancel() -> bool:
        async with maker() as own_session:
            return await InvitationRepository(own_session).cancel_invitation(
                invitation_id, sender, NOW
            )

    accepted, cancelled = await asyncio.gather(accept(), cancel())

    assert accepted != cancelled
    async with maker() as check:
        stored = await check.scalar(select(Invitation.status).where(Invitation.id == invitation_id))
    assert stored is (Status.ACCEPTED if accepted else Status.CANCELLED)


async def test_simultaneous_invitations_for_one_pair_leave_one_pending(pg_engine: AsyncEngine):
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with maker() as setup:
        sender, recipient = await make_user_id(setup), await make_user_id(setup)

    async def send() -> bool:
        async with maker() as own_session:
            try:
                await invite(InvitationRepository(own_session), sender, recipient)
            except ConflictError:
                return False
            return True

    results = await asyncio.gather(*(send() for _ in range(6)))

    assert sorted(results) == [False] * 5 + [True]


async def test_expiry_is_exclusive_at_the_stored_instant(pg_engine: AsyncEngine):
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with maker() as session:
        sender, recipient = await make_user_id(session), await make_user_id(session)
        invitation_id = await invite(InvitationRepository(session), sender, recipient)
        repo = InvitationRepository(session)

        assert await repo.accept_invitation(invitation_id, recipient, EXPIRES) is False
        assert (
            await repo.accept_invitation(
                invitation_id, recipient, EXPIRES - timedelta(microseconds=1)
            )
            is True
        )
