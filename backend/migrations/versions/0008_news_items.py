"""Store the adaptive-sport digest collected from public feeds.

Adds the ``news_items`` table. The address of an article is unique, so collecting the same feed
twice stores nothing twice. The downgrade drops the table; the items are public and are collected
again.

Revision ID: 0008_news_items
Revises: 0007_email_verification
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_news_items"
down_revision: str | None = "0007_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the table and its index on the publication time."""
    op.create_table(
        "news_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_news_items"),
        sa.UniqueConstraint("url", name="uq_news_items_url"),
    )
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"])


def downgrade() -> None:
    """Drop the table."""
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_table("news_items")
