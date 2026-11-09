"""Candidate retrieval for the matching feed: PostGIS in production, plain code elsewhere.

Both sources implement the ``CandidateSource`` port and return the same set. They differ only in
where the radius test runs: PostgreSQL uses ``ST_DWithin`` on the generated ``area_center``
geography column (served by its GiST index), other databases load the visible profiles of a
latitude band and measure the haversine distance between cell centres in Python.

Distances shown to the caller never come from the database: the domain recomputes them from the
cell centres with the same haversine formula the scorer and the experiment use, so a band is
the same on every backend. The two radius tests can disagree only for a profile whose cell
centre lies within about 0.2 m of the radius (PostGIS uses a sphere of mean radius 6371.0088 km,
the haversine function 6371.0 km); the tests allow exactly that tolerance.
"""

import math
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, exists, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Profile, ProfileSport
from app.domain.matching.source import CandidateProfile, CandidateSource
from app.domain.privacy import EARTH_RADIUS_KM, GridCell, haversine_km
from app.domain.profile import FunctionalProfile, ProfileView, SportEntry
from app.repository import private_layer

POSTGRESQL = "postgresql"
_METRES_PER_KM = 1000.0
# Margin on the latitude band so that float rounding can never cut off a profile on the edge
_BAND_MARGIN_DEGREES = 1e-6


def _sports(row: Profile) -> frozenset[SportEntry]:
    """Map the loaded sport rows to entries."""
    return frozenset(SportEntry(sport=item.sport, skill=item.skill) for item in row.sports)


def _eligible(viewer: ProfileView) -> Select[tuple[Profile]]:
    """Statement for visible profiles other than the viewer that share a sport with them."""
    shares_a_sport = exists().where(
        ProfileSport.profile_id == Profile.id,
        ProfileSport.sport.in_(sorted(viewer.sport_codes)),
    )
    return (
        select(Profile)
        .where(Profile.is_visible.is_(True), Profile.id != viewer.id, shares_a_sport)
        .options(selectinload(Profile.sports))
        .execution_options(populate_existing=True)
    )


class _SessionCandidateSource:
    """Shared part of the two sources: eligibility, hydration and the consent rule.

    :param session: Database session of the request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def _hydrate(self, rows: Sequence[Profile]) -> list[CandidateProfile]:
        """Turn rows into snapshots, reading capabilities only of profiles with consent.

        The check repeats a rule the profile service already enforces on write (capabilities are
        deleted with the consent), so a stray row of a profile without consent still stays out
        of other people's comparisons.
        """
        consenting = {row.id for row in rows if row.functional_consent_at is not None}
        functional = await private_layer.load_functional_profiles(self.db, consenting)
        return [
            CandidateProfile(
                view=ProfileView(
                    id=row.id,
                    sports=_sports(row),
                    intensity=row.intensity,
                    cell=GridCell(latitude=row.area_lat, longitude=row.area_lon),
                    district=row.district_code,
                    functional=functional.get(row.id, FunctionalProfile.empty()),
                    is_visible=row.is_visible,
                ),
                display_name=row.display_name,
            )
            for row in rows
        ]


class HaversineCandidateSource(_SessionCandidateSource):
    """Portable source: a latitude band in SQL, the haversine radius test in Python.

    Used by the tests and whenever the database is not PostgreSQL. Cost grows with the number
    of visible profiles in the latitude band, which is acceptable only for development sizes;
    production uses :class:`PostgisCandidateSource`.
    """

    async def search_candidates(
        self, viewer: ProfileView, radius_km: float, limit: int
    ) -> list[CandidateProfile]:
        """Find candidates within the radius, nearest first.

        :param viewer: The viewer; their own profile is never returned.
        :param radius_km: Search radius in kilometres, measured between cell centres.
        :param limit: Maximum number of profiles to return.
        :return: Candidate profiles ordered by distance and then by profile id.
        """
        if limit <= 0 or not viewer.sports:
            return []
        # A point farther than the radius in latitude alone is farther than the radius
        half_band = math.degrees(radius_km / EARTH_RADIUS_KM) + _BAND_MARGIN_DEGREES
        latitude = viewer.cell.latitude
        result = await self.db.execute(
            _eligible(viewer).where(
                Profile.area_lat.between(latitude - half_band, latitude + half_band)
            )
        )
        measured = [
            (haversine_km(viewer.cell, GridCell(row.area_lat, row.area_lon)), row.id, row)
            for row in result.scalars()
        ]
        within = sorted((m for m in measured if m[0] <= radius_km), key=lambda m: (m[0], m[1]))
        return await self._hydrate([row for _, _, row in within[:limit]])


class PostgisCandidateSource(_SessionCandidateSource):
    """PostgreSQL source: ``ST_DWithin`` on the generated geography column and its GiST index.

    Needs the ``area_center`` column of migration 0004. Distances are on the sphere
    (``use_spheroid`` false) so that they match the haversine distance used for the bands.
    """

    async def search_candidates(
        self, viewer: ProfileView, radius_km: float, limit: int
    ) -> list[CandidateProfile]:
        """Find candidates within the radius, nearest first.

        :param viewer: The viewer; their own profile is never returned.
        :param radius_km: Search radius in kilometres, measured between cell centres.
        :param limit: Maximum number of profiles to return.
        :return: Candidate profiles ordered by distance and then by profile id.
        """
        if limit <= 0 or not viewer.sports:
            return []
        center: ColumnElement[Any] = literal_column("profiles.area_center")
        point = func.ST_GeogFromText(
            f"SRID=4326;POINT({viewer.cell.longitude:.6f} {viewer.cell.latitude:.6f})"
        )
        statement = (
            _eligible(viewer)
            .where(func.ST_DWithin(center, point, radius_km * _METRES_PER_KM, False))
            .order_by(func.ST_Distance(center, point, False), Profile.id)
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return await self._hydrate(result.scalars().all())


def build_candidate_source(session: AsyncSession) -> CandidateSource:
    """Choose the source that fits the database behind the session.

    :param session: Database session of the request.
    :return: The PostGIS source on PostgreSQL, the portable one on any other database.
    """
    if session.get_bind().dialect.name == POSTGRESQL:
        return PostgisCandidateSource(session)
    return HaversineCandidateSource(session)


__all__ = [
    "HaversineCandidateSource",
    "PostgisCandidateSource",
    "build_candidate_source",
]
