"""Profiles, sports and functional capabilities.

The code lists below are a frozen copy of the taxonomy at the time of this revision, so the
migration keeps producing the same schema when the application taxonomy changes. A later
revision alters the constraints when codes are added.

Revision ID: 0003_profiles
Revises: 0002_users
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_profiles"
down_revision: str | None = "0002_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DISTRICTS = (
    "kyiv_holosiivskyi",
    "kyiv_darnytskyi",
    "kyiv_desnianskyi",
    "kyiv_dniprovskyi",
    "kyiv_obolonskyi",
    "kyiv_pecherskyi",
    "kyiv_podilskyi",
    "kyiv_sviatoshynskyi",
    "kyiv_solomianskyi",
    "kyiv_shevchenkivskyi",
)
SPORTS = (
    "swimming",
    "archery",
    "table_tennis",
    "sitting_volleyball",
    "wheelchair_basketball",
    "cycling",
    "handcycling",
    "rowing",
    "athletics",
    "gym_fitness",
    "powerlifting",
    "yoga_stretching",
    "badminton",
    "nordic_walking",
)
SKILLS = ("beginner", "intermediate", "advanced")
CATEGORIES = (
    "mobility_lower",
    "mobility_upper",
    "balance_posture",
    "endurance",
    "dexterity",
    "vision",
    "hearing",
)
EQUIPMENT = (
    "wheelchair_active",
    "handcycle",
    "crutches_or_cane",
    "prosthesis_lower_limb",
    "running_blade",
    "prosthesis_upper_limb",
    "guide_support",
    "hearing_aid",
)


def _code(values: Sequence[str], name: str) -> sa.Enum:
    """Return a constrained string column type (not a native enum) with a named CHECK."""
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=50)


def upgrade() -> None:
    """Create the three profile tables and the sport index."""
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=60), nullable=False),
        sa.Column("district_code", _code(DISTRICTS, "district_code"), nullable=True),
        sa.Column("intensity", sa.Integer(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("area_lat", sa.Double(), nullable=False),
        sa.Column("area_lon", sa.Double(), nullable=False),
        sa.Column("functional_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
        sa.CheckConstraint("intensity BETWEEN 1 AND 5", name=op.f("ck_profiles_intensity_range")),
        sa.CheckConstraint("area_lat BETWEEN -90 AND 90", name=op.f("ck_profiles_area_lat_range")),
        sa.CheckConstraint(
            "area_lon BETWEEN -180 AND 180", name=op.f("ck_profiles_area_lon_range")
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_profiles_user_id")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_profiles_user_id_users"), ondelete="CASCADE"
        ),
    )
    op.create_table(
        "profile_sports",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("sport", _code(SPORTS, "sport"), nullable=False),
        sa.Column("skill", _code(SKILLS, "skill"), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "sport", name=op.f("pk_profile_sports")),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name=op.f("fk_profile_sports_profile_id_profiles"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_profile_sports_sport", "profile_sports", ["sport"])
    op.create_table(
        "functional_capabilities",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("category", _code(CATEGORIES, "category"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("equipment", _code(EQUIPMENT, "equipment"), nullable=True),
        sa.PrimaryKeyConstraint("profile_id", "category", name=op.f("pk_functional_capabilities")),
        sa.CheckConstraint(
            "level BETWEEN 0 AND 4", name=op.f("ck_functional_capabilities_level_range")
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name=op.f("fk_functional_capabilities_profile_id_profiles"),
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Drop the profile tables in dependency order."""
    op.drop_table("functional_capabilities")
    op.drop_index("ix_profile_sports_sport", table_name="profile_sports")
    op.drop_table("profile_sports")
    op.drop_table("profiles")
