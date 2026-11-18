"""Profile photograph and the owner's choice of area precision.

Adds ``profiles.area_precision`` (the grid the stored cell belongs to; existing rows keep the grid
of about 4 km they were stored with), ``profiles.photo_updated_at`` and the ``profile_photos``
table that holds the picture itself. The downgrade drops all three; areas stored on a finer grid
stay as they are, only the note of their grid is lost.

Revision ID: 0010_photo_and_area_precision
Revises: 0009_password_reset
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_photo_and_area_precision"
down_revision: str | None = "0009_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRECISIONS = ("1km", "2km", "4km", "place")


def upgrade() -> None:
    """Add the two columns and create the table of pictures."""
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(
            sa.Column(
                "area_precision",
                sa.Enum(
                    *_PRECISIONS,
                    name="area_precision",
                    native_enum=False,
                    create_constraint=True,
                    length=50,
                ),
                nullable=False,
                server_default="4km",
            )
        )
        batch.add_column(sa.Column("photo_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "profile_photos",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_profile_photos_profile_id_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("profile_id", name="pk_profile_photos"),
    )


def downgrade() -> None:
    """Drop the table of pictures and the two columns."""
    op.drop_table("profile_photos")
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("photo_updated_at")
        batch.drop_constraint("area_precision", type_="check")
        batch.drop_column("area_precision")
