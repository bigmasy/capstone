"""Invitations between users.

The status list is a frozen copy of the domain enum at the time of this revision, so the
migration keeps producing the same schema when the application changes. A later revision alters
the constraint when a status is added.

Revision ID: 0005_invitations
Revises: 0004_geography
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_invitations"
down_revision: str | None = "0004_geography"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("pending", "accepted", "declined", "cancelled", "expired")


def upgrade() -> None:
    """Create the invitations table, the pending-pair rule and the listing indexes."""
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*STATUSES, name="status", native_enum=False, create_constraint=True, length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.String(length=280), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.CheckConstraint(
            "sender_user_id <> recipient_user_id", name=op.f("ck_invitations_no_self_invitation")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_invitations_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_sender_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_recipient_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_invitations_pending_pair",
        "invitations",
        ["sender_user_id", "recipient_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_invitations_sender_created", "invitations", ["sender_user_id", "created_at"]
    )
    op.create_index(
        "ix_invitations_recipient_created", "invitations", ["recipient_user_id", "created_at"]
    )


def downgrade() -> None:
    """Drop the indexes and the table."""
    op.drop_index("ix_invitations_recipient_created", table_name="invitations")
    op.drop_index("ix_invitations_sender_created", table_name="invitations")
    op.drop_index("uq_invitations_pending_pair", table_name="invitations")
    op.drop_table("invitations")
