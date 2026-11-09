"""Remove the free-text note from invitations.

The platform lets two users exchange no free text before a contact is released, so the column
has no use. The downgrade restores it as a nullable column; the dropped notes are not recovered.

Revision ID: 0006_drop_invitation_message
Revises: 0005_invitations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_drop_invitation_message"
down_revision: str | None = "0005_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the message column (batch mode rebuilds the table on SQLite)."""
    with op.batch_alter_table("invitations") as batch:
        batch.drop_column("message")


def downgrade() -> None:
    """Add the message column back, empty and nullable."""
    with op.batch_alter_table("invitations") as batch:
        batch.add_column(sa.Column("message", sa.String(length=280), nullable=True))
