"""Alembic environment: async engine, URL taken from application settings."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.conf.config import get_settings
from app.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Percent signs in a URL (encoded passwords) must be doubled for ConfigParser interpolation.
_url = get_settings().DB_URL.get_secret_value()
config.set_main_option("sqlalchemy.url", _url.replace("%", "%%"))

# SQLite cannot ALTER most constraints in place; batch mode recreates the table instead.
_render_as_batch = _url.startswith("sqlite")


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Hide database objects that exist only on PostgreSQL from autogenerate.

    The generated ``area_center`` column and its GiST index are created outside the ORM
    metadata. The PostGIS image also ships tables of its own (``spatial_ref_sys``, the
    geocoder schemas); a reflected table that the models do not know is ignored, otherwise
    ``alembic check`` would propose dropping them.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    if type_ == "column" and name == "area_center":
        return False
    if type_ == "index" and name == "ix_profiles_area_center":
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_render_as_batch,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an open synchronous-style connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=_render_as_batch,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run the migrations through ``run_sync``."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
