"""Password reset by e-mail.

Adds ``users.password_changed_at`` (access tokens issued before it are refused) and the
``password_resets`` table of one-time tokens, stored as digests like the confirmation tokens.
The downgrade drops both.

Revision ID: 0009_password_reset
Revises: 0008_news_items
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_password_reset"
down_revision: str | None = "0008_news_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column and create the token table."""
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_password_resets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_password_resets"),
        sa.UniqueConstraint("token_hash", name="uq_password_resets_token_hash"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])


def downgrade() -> None:
    """Drop the token table and the column."""
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
