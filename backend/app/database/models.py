"""Declarative base and ORM models.

Everything here is private to the ``database`` and ``repository`` layers: the API and the
services work with the records of ``app.domain`` and never see these classes.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.account import CONTACT_MAX_LENGTH, DISPLAY_NAME_MAX_LENGTH, EMAIL_MAX_LENGTH
from app.domain.invitations import Status
from app.domain.privacy import DEFAULT_PRECISION, AreaPrecision
from app.domain.taxonomy import (
    MAX_CAPABILITY_LEVEL,
    MAX_INTENSITY,
    MIN_CAPABILITY_LEVEL,
    MIN_INTENSITY,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)

# Explicit constraint names keep Alembic migrations deterministic on PostgreSQL and SQLite.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_CODE_LENGTH = 50


class Base(DeclarativeBase):
    """The single declarative base shared by all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _code_column(enum: type[StrEnum], name: str) -> Enum:
    """Return a string column type constrained to the values of a taxonomy enum.

    The enum is stored as a plain string with a CHECK constraint (not a native database enum),
    so adding a code is a migration of one constraint. The stored text is the code value, not
    the member name.
    """
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=_CODE_LENGTH,
        values_callable=lambda members: [member.value for member in members],
    )


class User(Base):
    """A registered account."""

    __tablename__ = "users"
    __table_args__ = (
        # The service lower-cases addresses; the constraint makes the unique index safe against
        # writers that do not.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set when the owner follows the link sent to the address; until then the account cannot
    # invite, accept or be found by others.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when the password is reset by e-mail; access tokens issued before it stop working.
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )


class EmailVerification(Base):
    """A one-time confirmation token of an account, stored as a digest only."""

    __tablename__ = "email_verifications"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_email_verifications_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordReset(Base):
    """A one-time password-reset token of an account, stored as a digest only."""

    __tablename__ = "password_resets"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        Index("ix_password_resets_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NewsItem(Base):
    """One item of the adaptive-sport digest collected from a public feed."""

    __tablename__ = "news_items"
    __table_args__ = (Index("ix_news_items_published_at", "published_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Profile(Base):
    """The profile of one user, with the coarsened location of the owner.

    ``area_lat`` and ``area_lon`` hold the centre of a grid cell, never exact coordinates. On
    PostgreSQL the migration adds a generated ``area_center`` geography column built from them;
    it is deliberately not mapped here.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            f"intensity BETWEEN {MIN_INTENSITY} AND {MAX_INTENSITY}", name="intensity_range"
        ),
        CheckConstraint("area_lat BETWEEN -90 AND 90", name="area_lat_range"),
        CheckConstraint("area_lon BETWEEN -180 AND 180", name="area_lon_range"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    display_name: Mapped[str] = mapped_column(String(DISPLAY_NAME_MAX_LENGTH))
    district_code: Mapped[DistrictCode | None] = mapped_column(
        _code_column(DistrictCode, "district_code"), nullable=True
    )
    intensity: Mapped[int] = mapped_column(Integer)
    is_visible: Mapped[bool] = mapped_column(default=True, server_default=true())
    area_lat: Mapped[float] = mapped_column(Double)
    area_lon: Mapped[float] = mapped_column(Double)
    # The grid the cell above belongs to; the owner chooses how coarse the stored area is.
    area_precision: Mapped[AreaPrecision] = mapped_column(
        _code_column(AreaPrecision, "area_precision"),
        default=DEFAULT_PRECISION,
        server_default=DEFAULT_PRECISION.value,
    )
    # Set while a photograph is stored; lets every reader know without touching the picture.
    photo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    functional_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contact: Mapped[str | None] = mapped_column(String(CONTACT_MAX_LENGTH), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile", lazy="raise")
    sports: Mapped[list["ProfileSport"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    # There is intentionally no relationship to FunctionalCapability: the private layer is
    # reached only through app.repository.private_layer, never by walking an attribute.


class ProfilePhoto(Base):
    """The photograph of a profile, in its stored form: a small square JPEG without metadata.

    Kept apart from ``profiles`` so that no query of profiles loads picture bytes by accident.
    """

    __tablename__ = "profile_photos"

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProfileSport(Base):
    """A sport a profile practises, with the self-declared skill."""

    __tablename__ = "profile_sports"
    __table_args__ = (Index("ix_profile_sports_sport", "sport"),)

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    sport: Mapped[SportCode] = mapped_column(_code_column(SportCode, "sport"), primary_key=True)
    skill: Mapped[SkillLevel] = mapped_column(_code_column(SkillLevel, "skill"))

    profile: Mapped[Profile] = relationship(back_populates="sports", lazy="raise")


class FunctionalCapability(Base):
    """One declared capability of a profile: private layer, stored only with consent."""

    __tablename__ = "functional_capabilities"
    __table_args__ = (
        CheckConstraint(
            f"level BETWEEN {MIN_CAPABILITY_LEVEL} AND {MAX_CAPABILITY_LEVEL}",
            name="level_range",
        ),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[CategoryCode] = mapped_column(
        _code_column(CategoryCode, "category"), primary_key=True
    )
    level: Mapped[int] = mapped_column(Integer)
    equipment: Mapped[EquipmentCode | None] = mapped_column(
        _code_column(EquipmentCode, "equipment"), nullable=True
    )


class Invitation(Base):
    """An invitation from one user to another to train together.

    The row connects users, not profiles, so it survives a profile being edited or replaced.
    There is deliberately no contact column: contacts stay on the profiles and are read only
    for an accepted invitation. Expiry is lazy: a pending row past ``expires_at`` is reported as
    expired and is rewritten only when the same pair is invited again.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("sender_user_id <> recipient_user_id", name="no_self_invitation"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        # At most one open invitation per ordered pair; settled ones do not count. The partial
        # index is supported by both PostgreSQL and SQLite, which keeps the rule testable.
        Index(
            "uq_invitations_pending_pair",
            "sender_user_id",
            "recipient_user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index("ix_invitations_sender_created", "sender_user_id", "created_at"),
        Index("ix_invitations_recipient_created", "recipient_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sender_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[Status] = mapped_column(_code_column(Status, "status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
