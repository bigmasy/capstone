import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(60))
    district: Mapped[str | None] = mapped_column(String(100))
    # Center of a grid cell, not the exact position (see app/privacy.py)
    area_lat: Mapped[float] = mapped_column(Float)
    area_lon: Mapped[float] = mapped_column(Float)
    intensity: Mapped[int] = mapped_column(SmallInteger)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    sports: Mapped[list["ProfileSport"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    capabilities: Mapped[list["FunctionalCapability"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileSport(Base):
    __tablename__ = "profile_sports"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    sport: Mapped[str] = mapped_column(String(50), index=True)
    level: Mapped[str] = mapped_column(String(20), default="beginner")

    profile: Mapped[Profile] = relationship(back_populates="sports")


class FunctionalCapability(Base):
    """Private layer: capability categories and equipment, without diagnoses."""

    __tablename__ = "functional_capabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    level: Mapped[int] = mapped_column(SmallInteger)
    equipment: Mapped[str | None] = mapped_column(String(50))

    profile: Mapped[Profile] = relationship(back_populates="capabilities")
