"""The feed: which profiles may be offered to a viewer and in which order."""

import dataclasses
from collections.abc import Callable, Sequence

from app.domain.functional import shield_insufficient_overlap
from app.domain.matching.scorer import Candidate, Scored
from app.domain.profile import ProfileView


def eligible_candidates(viewer: ProfileView, profiles: Sequence[ProfileView]) -> list[Candidate]:
    """Return the profiles that may appear in the viewer's feed, with their distances.

    A profile is eligible if it is visible, is not the viewer and shares at least one sport
    with the viewer. Distant profiles stay eligible: distance lowers the score but never
    removes a candidate. The distance is measured between the cell centres.

    :param viewer: The viewer.
    :param profiles: Profiles to choose from, in any order.
    :return: Eligible candidates in the order given.
    """
    mine = viewer.sport_codes
    return [
        Candidate.between(viewer, profile)
        for profile in profiles
        if profile.id != viewer.id and profile.is_visible and mine & profile.sport_codes
    ]


def shield_functional(viewer: ProfileView, candidate: Candidate) -> Candidate:
    """Withhold the functional data of a candidate that shares too few categories with the viewer.

    Applies the minimum-shared-categories rule (see ``shield_insufficient_overlap``) before
    scoring, so that neither the baseline nor the learned ranker can act on a comparison that
    would let the viewer probe for a single category. The candidate stays in the feed: removing
    them instead would make their presence in the feed a probe of the very same fact.

    :param viewer: The viewer.
    :param candidate: A candidate with its distance.
    :return: The candidate unchanged if the rule is met, otherwise a copy without functional
        data.
    """
    shielded = shield_insufficient_overlap(viewer.functional, candidate.profile.functional)
    if shielded is candidate.profile.functional:
        return candidate
    masked = dataclasses.replace(candidate.profile, functional=shielded)
    return Candidate(profile=masked, distance_km=candidate.distance_km)


def rank(
    scored: Sequence[Scored], limit: int, keeps: Callable[[Scored], bool] | None = None
) -> list[Scored]:
    """Order scored candidates for the feed and cut the list to the limit.

    Which entries are dropped is a rule of the scorer that produced them (``Scorer.keeps``):
    a baseline score of 0 means "nothing in common", but a learned score is relative and may be
    negative for a good candidate. Without a rule nothing is dropped. Equal scores are ordered
    by profile id, so the order does not depend on the order of the input.

    :param scored: Scored candidates, in any order.
    :param limit: Maximum number of entries to return.
    :param keeps: Predicate that tells which entries may appear, usually ``scorer.keeps``.
    :raises ValueError: If the limit is negative.
    :return: At most ``limit`` entries, best first.
    """
    if limit < 0:
        raise ValueError("limit must not be negative")
    kept = [entry for entry in scored if keeps is None or keeps(entry)]
    kept.sort(key=lambda entry: (-entry.score, entry.candidate.profile.id))
    return kept[:limit]
