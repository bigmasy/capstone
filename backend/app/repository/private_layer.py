"""The only door to the functional capability rows.

Capabilities describe what a person can do and are the most sensitive data of the platform.
Every read and write of the ``functional_capabilities`` table goes through this module, so a
review of who can see that data is a review of this file. Nothing here commits: the caller owns
the transaction.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import FunctionalCapability
from app.domain.profile import CapabilityEntry, FunctionalProfile


async def load_capabilities(session: AsyncSession, profile_id: UUID) -> tuple[CapabilityEntry, ...]:
    """Read the declared capabilities of a profile, ordered by category code.

    :param session: Database session.
    :param profile_id: Identifier of the profile.
    :return: The stored entries; empty if none were declared or consent was withdrawn.
    """
    result = await session.execute(
        select(FunctionalCapability)
        .where(FunctionalCapability.profile_id == profile_id)
        .order_by(FunctionalCapability.category)
        .execution_options(populate_existing=True)
    )
    return tuple(
        CapabilityEntry(category=row.category, level=row.level, equipment=row.equipment)
        for row in result.scalars()
    )


async def load_functional_profile(session: AsyncSession, profile_id: UUID) -> FunctionalProfile:
    """Read the private layer of a profile as the domain value used for scoring.

    :param session: Database session.
    :param profile_id: Identifier of the profile.
    :return: The functional profile; empty when nothing is stored.
    """
    return FunctionalProfile(capabilities=frozenset(await load_capabilities(session, profile_id)))


async def load_functional_profiles(
    session: AsyncSession, profile_ids: Collection[UUID]
) -> dict[UUID, FunctionalProfile]:
    """Read the private layer of several profiles in one query.

    The caller decides whose data may be read (matching passes only profiles whose owner gave
    consent); this function does not look at consent itself.

    :param session: Database session.
    :param profile_ids: Identifiers of the profiles.
    :return: A functional profile for every identifier; empty when nothing is stored.
    """
    if not profile_ids:
        return {}
    result = await session.execute(
        select(FunctionalCapability)
        .where(FunctionalCapability.profile_id.in_(profile_ids))
        .execution_options(populate_existing=True)
    )
    grouped: defaultdict[UUID, list[CapabilityEntry]] = defaultdict(list)
    for row in result.scalars():
        grouped[row.profile_id].append(
            CapabilityEntry(category=row.category, level=row.level, equipment=row.equipment)
        )
    return {
        profile_id: FunctionalProfile(capabilities=frozenset(grouped[profile_id]))
        for profile_id in profile_ids
    }


async def replace_capabilities(
    session: AsyncSession, profile_id: UUID, entries: Iterable[CapabilityEntry]
) -> None:
    """Replace all capabilities of a profile within the caller's transaction.

    :param session: Database session; the caller commits.
    :param profile_id: Identifier of the profile.
    :param entries: Entries to store; an empty collection deletes everything.
    """
    await session.execute(
        delete(FunctionalCapability).where(FunctionalCapability.profile_id == profile_id)
    )
    session.add_all(
        FunctionalCapability(
            profile_id=profile_id,
            category=entry.category,
            level=entry.level,
            equipment=entry.equipment,
        )
        for entry in entries
    )
