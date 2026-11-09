"""PostGIS geography column derived from the coarsened profile location (PostgreSQL only).

The column is generated, so it can never disagree with ``area_lon`` and ``area_lat``; it is not
mapped in the ORM and only spatial queries read it. On other databases (SQLite in tests) this
revision does nothing.

Revision ID: 0004_geography
Revises: 0003_profiles
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_geography"
down_revision: str | None = "0003_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgresql() -> bool:
    """Tell whether the migration runs against PostgreSQL."""
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Enable PostGIS, add the generated geography column and its GiST index."""
    if not _is_postgresql():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        "ALTER TABLE profiles ADD COLUMN area_center geography(Point, 4326) "
        "GENERATED ALWAYS AS "
        "(ST_SetSRID(ST_MakePoint(area_lon, area_lat), 4326)::geography) STORED"
    )
    op.execute("CREATE INDEX ix_profiles_area_center ON profiles USING gist (area_center)")


def downgrade() -> None:
    """Drop the index and the column; the extension is left installed on purpose."""
    if not _is_postgresql():
        return
    op.execute("DROP INDEX IF EXISTS ix_profiles_area_center")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS area_center")
