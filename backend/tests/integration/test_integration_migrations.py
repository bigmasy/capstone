"""Alembic migrations against SQLite (always) and PostGIS (when TEST_DATABASE_URL is set)."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine

from app.conf.config import get_settings
from app.database.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[2]
TABLES = {"users", "profiles", "profile_sports", "functional_capabilities", "invitations"}


def alembic_config(monkeypatch: pytest.MonkeyPatch, url: str) -> Config:
    """Point the migration environment at a database through the environment."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "m" * 40)
    monkeypatch.setenv("DB_URL", url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def constraint_names(engine: Engine) -> dict[str, set[str]]:
    """Names of checks, unique constraints, foreign keys and indexes per application table."""
    result: dict[str, set[str]] = {}
    with engine.connect() as connection:
        inspector = inspect(connection)
        # Older revisions do not have every table yet
        for table in sorted(TABLES & set(inspector.get_table_names())):
            names = {c["name"] for c in inspector.get_check_constraints(table)}
            names |= {c["name"] for c in inspector.get_unique_constraints(table)}
            names |= {c["name"] for c in inspector.get_foreign_keys(table)}
            names |= {c["name"] for c in inspector.get_indexes(table)}
            primary = inspector.get_pk_constraint(table)["name"]
            result[table] = {n for n in names | {primary} if n}
    return result


def test_revision_ids_form_one_chain():
    script = ScriptDirectory(str(BACKEND_DIR / "migrations"))

    assert script.get_heads() == ["0006_drop_invitation_message"]
    chain = [rev.revision for rev in script.walk_revisions()]
    assert chain == [
        "0006_drop_invitation_message",
        "0005_invitations",
        "0004_geography",
        "0003_profiles",
        "0002_users",
        "0001_baseline",
    ]


def test_sqlite_upgrade_creates_the_schema_of_the_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    migrated_url = f"sqlite+aiosqlite:///{tmp_path / 'migrated.db'}"
    config = alembic_config(monkeypatch, migrated_url)

    command.upgrade(config, "head")

    migrated = create_engine(migrated_url.replace("+aiosqlite", ""))
    reference = create_engine(f"sqlite:///{tmp_path / 'reference.db'}")
    Base.metadata.create_all(reference)
    assert TABLES <= set(inspect(migrated).get_table_names())
    assert constraint_names(migrated) == constraint_names(reference)
    # alembic check fails when the models and the migrations disagree
    command.check(config)


def test_sqlite_downgrade_and_upgrade_again(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'cycle.db'}"
    config = alembic_config(monkeypatch, url)
    engine = create_engine(url.replace("+aiosqlite", ""))

    command.upgrade(config, "head")
    command.downgrade(config, "0001_baseline")
    assert not TABLES & set(inspect(engine).get_table_names())
    command.upgrade(config, "head")

    assert TABLES <= set(inspect(engine).get_table_names())


def test_geography_revision_is_a_no_op_on_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'noop.db'}"
    config = alembic_config(monkeypatch, url)
    engine = create_engine(url.replace("+aiosqlite", ""))

    command.upgrade(config, "0003_profiles")
    before = constraint_names(engine)
    command.upgrade(config, "0004_geography")

    columns = {c["name"] for c in inspect(engine).get_columns("profiles")}
    assert "area_center" not in columns
    assert constraint_names(engine) == before
    command.downgrade(config, "0003_profiles")


def test_invitations_revision_creates_the_pending_pair_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    url = f"sqlite+aiosqlite:///{tmp_path / 'invitations.db'}"
    config = alembic_config(monkeypatch, url)
    engine = create_engine(url.replace("+aiosqlite", ""))

    command.upgrade(config, "head")

    inspector = inspect(engine)
    indexes = {index["name"]: index for index in inspector.get_indexes("invitations")}
    assert indexes["uq_invitations_pending_pair"]["unique"]
    assert indexes["uq_invitations_pending_pair"]["column_names"] == [
        "sender_user_id",
        "recipient_user_id",
    ]
    checks = {c["name"] for c in inspector.get_check_constraints("invitations")}
    assert {
        "ck_invitations_no_self_invitation",
        "ck_invitations_expiry_after_creation",
        "ck_invitations_status",
    } <= checks
    foreign_keys = inspector.get_foreign_keys("invitations")
    assert {fk["options"].get("ondelete") for fk in foreign_keys} == {"CASCADE"}
    command.downgrade(config, "0004_geography")
    assert "invitations" not in inspect(engine).get_table_names()


def test_message_revision_drops_the_column_and_downgrade_restores_it_nullable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    url = f"sqlite+aiosqlite:///{tmp_path / 'message.db'}"
    config = alembic_config(monkeypatch, url)
    engine = create_engine(url.replace("+aiosqlite", ""))

    command.upgrade(config, "0005_invitations")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash) VALUES "
                "('00000000000000000000000000000001', 'a@example.org', 'x'), "
                "('00000000000000000000000000000002', 'b@example.org', 'x')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO invitations (id, sender_user_id, recipient_user_id, status, "
                "created_at, expires_at, message) VALUES "
                "('00000000000000000000000000000003', '00000000000000000000000000000001', "
                "'00000000000000000000000000000002', 'pending', '2030-01-01 00:00:00', "
                "'2030-02-01 00:00:00', 'note')"
            )
        )
    assert "message" in {c["name"] for c in inspect(engine).get_columns("invitations")}

    command.upgrade(config, "0006_drop_invitation_message")

    inspector = inspect(engine)
    assert "message" not in {c["name"] for c in inspector.get_columns("invitations")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM invitations")).scalar_one() == 1
    index_names = {index["name"] for index in inspector.get_indexes("invitations")}
    assert "uq_invitations_pending_pair" in index_names

    command.downgrade(config, "0005_invitations")

    restored = {c["name"]: c for c in inspect(engine).get_columns("invitations")}
    assert restored["message"]["nullable"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT message FROM invitations")).scalar_one() is None


@pytest.mark.postgis
def test_postgis_upgrade_adds_generated_geography_column(monkeypatch: pytest.MonkeyPatch):
    url = os.environ["TEST_DATABASE_URL"]
    config = alembic_config(monkeypatch, url)
    command.downgrade(config, "base")

    command.upgrade(config, "head")

    async def inspect_database() -> tuple[str, str, str]:
        async_engine = create_async_engine(url)
        async with async_engine.connect() as connection:
            column = (
                await connection.execute(
                    text(
                        "SELECT is_generated, generation_expression "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'profiles' AND column_name = 'area_center'"
                    )
                )
            ).one()
            index = (
                await connection.execute(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE tablename = 'profiles' AND indexname = 'ix_profiles_area_center'"
                    )
                )
            ).scalar_one()
            type_name = (
                await connection.execute(
                    text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_name = 'profiles' AND column_name = 'area_center'"
                    )
                )
            ).scalar_one()
        await async_engine.dispose()
        return column[0], index, type_name

    generated, index_definition, type_name = asyncio.run(inspect_database())
    assert generated == "ALWAYS"
    assert "gist" in index_definition.lower()
    assert type_name == "geography"
    command.check(config)
    command.downgrade(config, "0001_baseline")
    command.upgrade(config, "head")
