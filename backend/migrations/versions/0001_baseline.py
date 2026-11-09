"""Baseline: establishes the migration head; creates no tables.

Revision ID: 0001_baseline
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Do nothing; the schema starts in the next revision."""


def downgrade() -> None:
    """Do nothing."""
