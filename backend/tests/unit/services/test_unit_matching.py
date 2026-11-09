"""Tests of the matching service with in-memory stand-ins for storage and the learned model."""

import asyncio
import dataclasses
import threading
from collections.abc import Sequence
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.errors import NotFoundError
from app.domain.functional import MIN_SHARED_CATEGORIES, FunctionalLevel
from app.domain.matching.scorer import (
    Candidate,
    Criterion,
    RankInfluence,
    RankSource,
    Scored,
)
from app.domain.matching.source import CandidateProfile
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.privacy import haversine_km
from app.domain.profile import ProfileView
from app.domain.taxonomy import SportCode
from app.services.matching import MatchingService
from tests.unit.domain.builders import make_id, make_profile
from tests.unit.domain.strategies import profile_pools

VIEWER_USER = UUID(int=9_000)
BASELINE = WeightedScorer(DEFAULT_WEIGHTS)


class FakeProfiles:
    """Returns the viewer's snapshot for one known user."""

    def __init__(self, viewer: ProfileView | None) -> None:
        self.viewer = viewer

    async def get_profile_view(self, user_id: UUID) -> ProfileView | None:
        return self.viewer if user_id == VIEWER_USER else None


class FakeSource:
    """Returns the whole pool, even the viewer and hidden profiles, to test the service's guard."""

    def __init__(self, pool: Sequence[ProfileView]) -> None:
        self.pool = list(pool)
        self.calls: list[tuple[float, int]] = []

    async def search_candidates(
        self, viewer: ProfileView, radius_km: float, limit: int
    ) -> list[CandidateProfile]:
        self.calls.append((radius_km, limit))
        near = [p for p in self.pool if haversine_km(viewer.cell, p.cell) <= radius_km]
        return [CandidateProfile(view=p, display_name=f"Name {p.id.int}") for p in near[:limit]]


class LearnedLike:
    """A scorer with negative, uncalibrated scores that records the thread it ran on."""

    name = "learned-like"
    version = "1"
    rank_source = RankSource.LEARNED

    def __init__(self) -> None:
        self.thread_ids: list[int] = []

    def score(self, viewer: ProfileView, candidates: Sequence[Candidate]) -> list[Scored]:
        self.thread_ids.append(threading.get_ident())
        base = BASELINE.score(viewer, candidates)
        influence = {c: RankInfluence.NEUTRAL for c in Criterion}
        return [
            dataclasses.replace(
                item, score=-float(item.candidate.profile.id.int), rank_influence=influence
            )
            for item in base
        ]

    def keeps(self, scored: Scored) -> bool:
        return True


class Broken(LearnedLike):
    def score(self, viewer: ProfileView, candidates: Sequence[Candidate]) -> list[Scored]:
        raise RuntimeError("model exploded with secret-feature-values")


def service(viewer, pool, scorer=BASELINE, **kwargs) -> tuple[MatchingService, FakeSource]:
    source = FakeSource(pool)
    return MatchingService(FakeProfiles(viewer), source, scorer, **kwargs), source  # type: ignore[arg-type]


def ids(page) -> list[UUID]:
    return [e.scored.candidate.profile.id for e in page.entries]


async def test_a_caller_without_a_profile_gets_not_found():
    matching, _ = service(None, [])

    with pytest.raises(NotFoundError):
        await matching.get_matches(VIEWER_USER)


async def test_the_feed_is_ordered_best_first_and_excludes_the_viewer_and_hidden_profiles():
    me = make_profile(1, ["swimming"], intensity=3)
    better = make_profile(2, ["swimming"], intensity=3)
    worse = make_profile(3, ["swimming"], intensity=1, lat=50.5)
    hidden = make_profile(4, ["swimming"], visible=False)
    unrelated = make_profile(5, ["archery"])
    matching, _ = service(me, [me, worse, hidden, better, unrelated])

    page = await matching.get_matches(VIEWER_USER)

    assert ids(page) == [better.id, worse.id]
    assert page.total == 2
    assert page.rank_source is RankSource.BASELINE
    assert all(e.scored.rank_influence is None for e in page.entries)


async def test_entries_carry_the_public_name_and_the_baseline_breakdown():
    me = make_profile(1)
    other = make_profile(2)
    matching, _ = service(me, [other])

    [entry] = (await matching.get_matches(VIEWER_USER)).entries

    assert entry.display_name == "Name 2"
    assert entry.scored.breakdown.total == entry.scored.score


async def test_pages_follow_skip_and_limit_over_one_ordering():
    me = make_profile(1)
    pool = [
        make_profile(10 + n, lat=50.45 + 0.04 * (n % 5), lon=30.52 + 0.06 * (n // 5))
        for n in range(12)
    ]
    matching, _ = service(me, pool)

    everything = await matching.get_matches(VIEWER_USER, limit=50)
    first = await matching.get_matches(VIEWER_USER, skip=0, limit=5)
    second = await matching.get_matches(VIEWER_USER, skip=5, limit=5)
    last = await matching.get_matches(VIEWER_USER, skip=10, limit=5)
    beyond = await matching.get_matches(VIEWER_USER, skip=40, limit=5)

    assert ids(first) + ids(second) + ids(last) == ids(everything)
    assert [len(p.entries) for p in (first, second, last, beyond)] == [5, 5, 2, 0]
    assert {p.total for p in (first, second, last, beyond)} == {12}


async def test_the_feed_length_is_capped_by_max_matches():
    me = make_profile(1)
    matching, _ = service(me, [make_profile(10 + n) for n in range(8)], max_matches=3)

    page = await matching.get_matches(VIEWER_USER, limit=50)

    assert len(page.entries) == page.total == 3


async def test_the_radius_defaults_to_the_configured_one_and_never_exceeds_it():
    me = make_profile(1)
    matching, source = service(me, [], default_radius_km=40.0, candidate_limit=17)

    await matching.get_matches(VIEWER_USER)
    await matching.get_matches(VIEWER_USER, radius_km=10.0)

    assert source.calls == [(40.0, 17), (10.0, 17)]
    for bad in (0.0, -1.0, 40.1):
        with pytest.raises(ValueError, match="radius"):
            await matching.get_matches(VIEWER_USER, radius_km=bad)


async def test_a_smaller_radius_leaves_out_far_candidates():
    me = make_profile(1)
    near, far = make_profile(2, lat=50.49), make_profile(3, lat=51.2)
    matching, _ = service(me, [near, far])

    wide = await matching.get_matches(VIEWER_USER)
    narrow = await matching.get_matches(VIEWER_USER, radius_km=10.0)

    assert ids(wide) == [near.id, far.id]
    assert ids(narrow) == [near.id]


async def test_the_sport_filter_keeps_candidates_who_practise_that_sport():
    me = make_profile(1, ["swimming", "archery"])
    swimmer = make_profile(2, ["swimming"])
    archer = make_profile(3, ["archery"])
    matching, _ = service(me, [swimmer, archer])

    page = await matching.get_matches(VIEWER_USER, sport=SportCode.ARCHERY)

    assert ids(page) == [archer.id]


async def test_negative_arguments_are_rejected():
    matching, _ = service(make_profile(1), [])

    with pytest.raises(ValueError, match="negative"):
        await matching.get_matches(VIEWER_USER, skip=-1)
    with pytest.raises(ValueError, match="negative"):
        await matching.get_matches(VIEWER_USER, limit=-1)


async def test_a_learned_scorer_orders_by_raw_score_and_keeps_negative_scores():
    me = make_profile(1)
    pool = [make_profile(n) for n in (2, 3, 4)]
    matching, _ = service(me, pool, LearnedLike())

    page = await matching.get_matches(VIEWER_USER)

    # Raw scores are -2, -3, -4: all negative, and none may be dropped
    assert ids(page) == [make_id(2), make_id(3), make_id(4)]
    assert page.rank_source is RankSource.LEARNED
    assert all(e.scored.rank_influence is not None for e in page.entries)


async def test_scoring_runs_outside_the_event_loop_thread():
    me = make_profile(1)
    learned = LearnedLike()
    matching, _ = service(me, [make_profile(2)], learned)

    await matching.get_matches(VIEWER_USER)

    assert learned.thread_ids
    assert threading.get_ident() not in learned.thread_ids


async def test_a_failing_learned_scorer_falls_back_to_the_baseline(
    caplog: pytest.LogCaptureFixture,
):
    me = make_profile(1)
    matching, _ = service(me, [make_profile(2)], Broken(), fallback=BASELINE)

    page = await matching.get_matches(VIEWER_USER)

    assert page.rank_source is RankSource.BASELINE
    assert len(page.entries) == 1
    assert "RuntimeError" in caplog.text
    assert "secret-feature-values" not in caplog.text


async def test_without_a_fallback_a_failing_scorer_raises():
    matching, _ = service(make_profile(1), [make_profile(2)], Broken())

    with pytest.raises(RuntimeError):
        await matching.get_matches(VIEWER_USER)


async def test_one_shared_category_does_not_reveal_the_candidates_level():
    me = make_profile(1, caps=[("vision", 4, None), ("hearing", 4, None)])
    low = make_profile(2, caps=[("vision", 0, None), ("endurance", 0, None)])
    high = make_profile(3, caps=[("vision", 4, None), ("endurance", 4, None)])
    full = make_profile(4, caps=[("vision", 4, None), ("hearing", 4, None)])
    matching, _ = service(me, [low, high, full])

    page = await matching.get_matches(VIEWER_USER)

    levels = {
        e.scored.candidate.profile.id: e.scored.breakdown.functional_level for e in page.entries
    }
    assert levels[low.id] is FunctionalLevel.MEDIUM
    assert levels[high.id] is FunctionalLevel.MEDIUM
    assert levels[full.id] is FunctionalLevel.HIGH
    low_entry = next(e for e in page.entries if e.scored.candidate.profile.id == low.id)
    assert low_entry.scored.candidate.profile.functional.capabilities == frozenset()


def run(coroutine):
    return asyncio.run(coroutine)


@settings(max_examples=60, deadline=None)
@given(profile_pools(max_size=14))
def test_property_the_feed_is_sorted_and_holds_only_visible_other_profiles(pool):
    if not pool:
        return
    viewer = dataclasses.replace(pool[0], is_visible=True)
    matching, _ = service(viewer, pool)

    page = run(matching.get_matches(VIEWER_USER, limit=50))

    scores = [(-e.scored.score, e.scored.candidate.profile.id) for e in page.entries]
    assert scores == sorted(scores)
    for entry in page.entries:
        other = entry.scored.candidate.profile
        assert other.id != viewer.id
        assert other.is_visible
        assert other.sport_codes & viewer.sport_codes


@settings(max_examples=60, deadline=None)
@given(profile_pools(max_size=14))
def test_property_functional_data_is_used_only_with_enough_shared_categories(pool):
    if not pool:
        return
    viewer = pool[0]
    matching, _ = service(viewer, pool)

    page = run(matching.get_matches(VIEWER_USER, limit=50))

    mine = {c.category for c in viewer.functional.capabilities}
    for entry in page.entries:
        profile = entry.scored.candidate.profile
        original = next(p for p in pool if p.id == profile.id)
        shared = mine & {c.category for c in original.functional.capabilities}
        if len(shared) < MIN_SHARED_CATEGORIES:
            assert profile.functional.capabilities == frozenset()
            assert entry.scored.breakdown.functional_level is FunctionalLevel.MEDIUM


@settings(max_examples=40, deadline=None)
@given(profile_pools(max_size=14), st.integers(0, 6), st.integers(1, 5))
def test_property_pages_are_slices_of_one_ordering(pool, skip, limit):
    if not pool:
        return
    matching, _ = service(pool[0], pool)

    whole = run(matching.get_matches(VIEWER_USER, limit=50))
    page = run(matching.get_matches(VIEWER_USER, skip=skip, limit=limit))

    assert ids(page) == ids(whole)[skip : skip + limit]
    assert page.total == whole.total
