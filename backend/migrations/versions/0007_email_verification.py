"""Confirm e-mail addresses before an account takes part in matching.

Adds ``users.email_verified_at`` and the ``email_verifications`` table of one-time tokens.
Accounts that exist when the migration runs are marked as verified: they were created before
the rule existed (in practice the demo accounts), and locking them out would break a running
deployment. New accounts start unverified. The downgrade drops both again.

Revision ID: 0007_email_verification
Revises: 0006_drop_invitation_message
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_email_verification"
down_revision: str | None = "0006_drop_invitation_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column, mark the existing accounts verified and create the token table."""
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE users SET email_verified_at = created_at"))
    op.create_table(
        "email_verifications",
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
            name="fk_email_verifications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_verifications"),
        sa.UniqueConstraint("token_hash", name="uq_email_verifications_token_hash"),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"])


def downgrade() -> None:
    """Drop the token table and the column."""
    op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
    op.drop_table("email_verifications")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
