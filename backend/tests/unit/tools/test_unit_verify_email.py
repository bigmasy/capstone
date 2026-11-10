import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select

from app.database.db import DatabaseSessionManager
from app.database.models import Base, EmailVerification, User
from app.tools import verify_email
from app.tools.verify_email import confirm
from tests.conftest import make_settings


@pytest.fixture
async def manager(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[DatabaseSessionManager]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'tool.db'}"
    monkeypatch.setenv("DB_URL", url)
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "t" * 40)
    db = DatabaseSessionManager(make_settings(DB_URL=url))
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with db.session() as session:
        session.add(User(email="a@example.org", password_hash="x"))
        await session.commit()
    yield db
    await db.close()


async def verified(db: DatabaseSessionManager) -> bool:
    async with db.session() as session:
        stamp = (await session.execute(select(User.email_verified_at))).scalar_one()
    return stamp is not None


async def test_confirming_marks_the_account_without_sending_anything(manager):
    settings = make_settings(DB_URL=str(manager.engine.url.render_as_string(hide_password=False)))

    assert await confirm(settings, "a@example.org", link=False) == ""

    assert await verified(manager)


async def test_the_link_option_issues_a_working_link_and_leaves_the_account_alone(manager):
    settings = make_settings(DB_URL=str(manager.engine.url.render_as_string(hide_password=False)))

    link = await confirm(settings, "a@example.org", link=True)

    assert link is not None
    assert link.startswith("http://localhost:5173/verify-email#token=")
    assert not await verified(manager)
    async with manager.session() as session:
        assert len((await session.execute(select(EmailVerification))).scalars().all()) == 1


async def test_an_unknown_address_is_reported_and_nothing_changes(manager, capsys):
    exit_code = await asyncio.to_thread(verify_email.main, ["nobody@example.org"])

    assert exit_code == verify_email.EXIT_NOT_FOUND
    assert "No account" in capsys.readouterr().err
    assert not await verified(manager)


async def test_the_command_line_confirms_and_prints_the_link(manager, capsys):
    assert await asyncio.to_thread(verify_email.main, ["--link", "A@Example.org"]) == 0
    assert "#token=" in capsys.readouterr().out
    assert await asyncio.to_thread(verify_email.main, ["a@example.org"]) == 0
    assert await verified(manager)


async def test_the_reset_link_option_issues_a_working_reset_link(manager):
    settings = make_settings(DB_URL=str(manager.engine.url.render_as_string(hide_password=False)))

    link = await confirm(settings, "a@example.org", link=False, reset_link=True)

    assert link is not None
    assert link.startswith("http://localhost:5173/reset-password#token=")
    assert not await verified(manager)
