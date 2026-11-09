"""The matching feed with a learned ranker, and the fallbacks to the weighted baseline."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.conf.config import Settings
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.ranking.artifact import MODEL_FILE
from app.ranking.lightgbm_scorer import LightGBMScorer
from app.ranking.train import TrainConfig, export_artifact, train_ranker
from tests.conftest import make_settings
from tests.integration.helpers import Actor, sign_up_with_profile
from tests.unit.ranking.data import make_queries

pytest.importorskip("lightgbm")
pytestmark = pytest.mark.ml

URL = "/api/v1/matches"
INFLUENCE_KEYS = {"sport", "distance", "functional", "intensity"}
INFLUENCES = {"raises", "neutral", "lowers"}


@pytest.fixture(scope="module")
def good_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A tiny model trained in a temporary directory; nothing is read from the repository."""
    model = train_ranker(
        make_queries(1, 30),
        make_queries(2, 10),
        TrainConfig(seed=1, n_estimators=10, num_leaves=5, min_child_samples=5),
    )
    directory = tmp_path_factory.mktemp("artifact")
    export_artifact(model, directory, seeds={"train": 1}, n_events=10, metrics={})
    return directory


@pytest.fixture
def settings(request: pytest.FixtureRequest, good_artifact: Path, tmp_path: Path) -> Settings:
    """Settings that enable the ranker; ``indirect`` parameters pick a broken variant."""
    kind = getattr(request, "param", "good")
    if kind == "good":
        return make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=good_artifact)
    if kind == "missing":
        return make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=tmp_path / "nowhere")
    if kind == "corrupt":
        broken = tmp_path / "corrupt"
        broken.mkdir()
        for name in (MODEL_FILE, "manifest.json"):
            (broken / name).write_text("garbage", encoding="utf-8")
        return make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=broken)
    if kind == "tampered":
        tampered = tmp_path / "tampered"
        tampered.mkdir()
        for name in (MODEL_FILE, "manifest.json"):
            (tampered / name).write_bytes((good_artifact / name).read_bytes())
        (tampered / MODEL_FILE).write_text("tree\nchanged after the manifest was written")
        return make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=tampered)
    return make_settings(RANKER_ENABLED=False, RANKER_ARTIFACT_DIR=good_artifact)


async def add(client: httpx.AsyncClient, **overrides: Any) -> tuple[Actor, dict[str, Any]]:
    return await sign_up_with_profile(client, **overrides)


async def populate(client: httpx.AsyncClient) -> Actor:
    """A viewer and six varied candidates; returns the viewer."""
    sports = [
        {"sport": "swimming", "skill": "beginner"},
        {"sport": "archery", "skill": "advanced"},
    ]
    me, _ = await add(client, sports=sports, intensity=3)
    layout = [
        (50.45, 30.52, 3, sports[:1]),
        (50.49, 30.52, 5, sports),
        (50.53, 30.58, 1, sports[1:]),
        (50.60, 30.52, 4, sports[:1]),
        (50.70, 30.64, 2, sports),
        (50.46, 30.40, 3, sports[1:]),
    ]
    for number, (lat, lon, intensity, picked) in enumerate(layout):
        await add(
            client,
            display_name=f"P{number}",
            latitude=lat,
            longitude=lon,
            intensity=intensity,
            sports=picked,
        )
    return me


async def test_the_learned_ranker_orders_the_feed_and_explains_it_qualitatively(
    client: httpx.AsyncClient, app: FastAPI
):
    me = await populate(client)

    response = await client.get(URL, params={"limit": 50}, headers=me.headers)

    assert isinstance(app.state.scorer, LightGBMScorer)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 6
    for item in items:
        assert item["rank_source"] == "learned"
        assert set(item["rank_influence"]) == INFLUENCE_KEYS
        assert set(item["rank_influence"].values()) <= INFLUENCES
        # The numbers shown are always those of the baseline formula
        assert set(item["breakdown"]) == {"sport", "distance", "intensity", "functional", "total"}
        assert 0 < item["breakdown"]["total"] <= 100
    assert not {"score", "raw_score", "rank_score"} & set(items[0])


async def test_the_learned_feed_keeps_the_same_candidates_as_the_baseline(
    client: httpx.AsyncClient, app: FastAPI
):
    me = await populate(client)
    learned = (await client.get(URL, params={"limit": 50}, headers=me.headers)).json()
    # Swap in the baseline scorer on the same application and data
    app.state.scorer = WeightedScorer(DEFAULT_WEIGHTS)
    baseline = (await client.get(URL, params={"limit": 50}, headers=me.headers)).json()

    assert {i["id"] for i in learned["items"]} == {i["id"] for i in baseline["items"]}
    assert {i["rank_source"] for i in baseline["items"]} == {"baseline"}
    by_id = {i["id"]: i["breakdown"] for i in baseline["items"]}
    assert all(by_id[i["id"]] == i["breakdown"] for i in learned["items"])


async def test_the_learned_order_is_stable_between_requests_and_pages(
    client: httpx.AsyncClient,
):
    me = await populate(client)

    first = (await client.get(URL, params={"limit": 50}, headers=me.headers)).json()
    again = (await client.get(URL, params={"limit": 50}, headers=me.headers)).json()
    page_one = (await client.get(URL, params={"limit": 4}, headers=me.headers)).json()
    page_two = (await client.get(URL, params={"skip": 4, "limit": 4}, headers=me.headers)).json()

    ids = [i["id"] for i in first["items"]]
    assert ids == [i["id"] for i in again["items"]]
    assert ids == [i["id"] for i in page_one["items"] + page_two["items"]]


@pytest.mark.parametrize("settings", ["missing", "corrupt", "tampered", "disabled"], indirect=True)
async def test_a_missing_damaged_or_switched_off_model_leaves_the_baseline_in_charge(
    client: httpx.AsyncClient, app: FastAPI
):
    me = await populate(client)

    response = await client.get(URL, params={"limit": 50}, headers=me.headers)

    assert isinstance(app.state.scorer, WeightedScorer)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 6
    assert {i["rank_source"] for i in items} == {"baseline"}
    assert {i["rank_influence"] for i in items} == {None}
    totals = [i["breakdown"]["total"] for i in items]
    assert totals == sorted(totals, reverse=True)
