import dataclasses
import random
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pytest

from app.domain.matching.features import FEATURE_NAMES
from app.domain.matching.feed import rank
from app.domain.matching.scorer import Candidate, Criterion, RankInfluence, RankSource
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.ranking.features import feature_matrix
from app.synthetic import GeneratorParams, generate_profiles

pytest.importorskip("lightgbm")
pytestmark = pytest.mark.ml

from app.ranking.lightgbm_scorer import (  # noqa: E402
    CRITERION_FEATURES,
    LightGBMScorer,
)
from app.ranking.train import TrainConfig, export_artifact, train_ranker  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[3]
CONFIG = TrainConfig(seed=1, n_estimators=30, num_leaves=7, min_child_samples=5)


@pytest.fixture(scope="module")
def artifact_dir(tmp_path_factory):
    # Train on pair features of generated profiles so the scorer sees realistic columns
    population = generate_profiles(GeneratorParams(count=80), 5)
    queries = []
    from app.domain.matching.feed import eligible_candidates
    from app.ranking.features import QueryData

    rng = np.random.default_rng(0)
    for viewer in population[:50]:
        cands = eligible_candidates(viewer, population)[:15]
        if len(cands) < 4:
            continue
        x = feature_matrix(viewer, cands)
        score = x[:, 1] - 0.4 * x[:, 5] + 0.5 * x[:, 10] + rng.normal(0, 0.3, len(cands))
        y = (score > np.median(score)).astype(float)
        queries.append(QueryData(x, y))
    model = train_ranker(queries[:35], queries[35:], CONFIG)
    directory = tmp_path_factory.mktemp("artifact")
    export_artifact(
        model, directory, seeds={"train": 1}, n_events=500, metrics={"model": {"ndcg@10": 0.5}}
    )
    return directory


@pytest.fixture(scope="module")
def scorer(artifact_dir):
    return LightGBMScorer.from_directory(artifact_dir)


@pytest.fixture(scope="module")
def world():
    population = generate_profiles(GeneratorParams(count=60), 9)
    viewer = population[0]
    from app.domain.matching.feed import eligible_candidates

    return viewer, eligible_candidates(viewer, population)


def test_scorer_identifies_itself_with_the_manifest_version(scorer):
    assert scorer.name == "lightgbm"
    assert scorer.version.startswith("lgbm-")


def test_breakdown_is_always_the_baseline_breakdown(scorer, world):
    viewer, candidates = world

    learned = scorer.score(viewer, candidates)
    baseline = WeightedScorer(DEFAULT_WEIGHTS).score(viewer, candidates)

    assert [s.breakdown for s in learned] == [b.breakdown for b in baseline]
    assert [s.candidate for s in learned] == candidates


def test_score_is_the_raw_model_score_and_not_a_percentage(scorer, world):
    viewer, candidates = world

    learned = scorer.score(viewer, candidates)

    raw = scorer.raw_scores(feature_matrix(viewer, candidates))
    assert [s.score for s in learned] == pytest.approx(raw.tolist())
    assert "calibrated" in (LightGBMScorer.score.__doc__ or "")


def test_shap_contributions_plus_bias_equal_the_raw_score(scorer, world):
    viewer, candidates = world
    matrix = feature_matrix(viewer, candidates)

    contributions = scorer.contributions(matrix)

    assert contributions.shape == (len(candidates), len(FEATURE_NAMES) + 1)
    assert contributions.sum(axis=1) == pytest.approx(scorer.raw_scores(matrix), abs=1e-9)


def test_criterion_groups_cover_every_feature_exactly_once():
    grouped = [name for names in CRITERION_FEATURES.values() for name in names]

    assert sorted(grouped) == sorted(FEATURE_NAMES)
    assert set(CRITERION_FEATURES) == {"sport", "distance", "intensity", "functional"}


def test_influences_are_qualitative_and_centred_over_the_list(scorer, world):
    viewer, candidates = world

    influences = scorer.criterion_influences(viewer, candidates)

    assert len(influences) == len(candidates)
    values = {RankInfluence.RAISES, RankInfluence.NEUTRAL, RankInfluence.LOWERS}
    for item in influences:
        assert {item.sport, item.distance, item.intensity, item.functional} <= values
    # A criterion cannot lower every candidate: contributions are centred, so some are not below
    for criterion in ("sport", "distance", "intensity", "functional"):
        column = [getattr(i, criterion) for i in influences]
        assert not all(c is RankInfluence.LOWERS for c in column)
        assert not all(c is RankInfluence.RAISES for c in column)


def test_rank_influence_is_a_per_criterion_mapping_on_every_result(scorer, world):
    viewer, candidates = world

    learned = scorer.score(viewer, candidates)
    influences = scorer.criterion_influences(viewer, candidates)

    for scored, detail in zip(learned, influences, strict=True):
        assert isinstance(scored.rank_influence, Mapping)
        assert set(scored.rank_influence) == set(Criterion)
        assert all(isinstance(v, RankInfluence) for v in scored.rank_influence.values())
        assert dict(scored.rank_influence) == detail.as_mapping()


def test_the_influence_mapping_is_read_only(scorer, world):
    viewer, candidates = world

    [first, *_] = scorer.score(viewer, candidates)

    with pytest.raises(TypeError):
        first.rank_influence[Criterion.SPORT] = RankInfluence.RAISES  # type: ignore[index]


def test_a_single_candidate_has_no_relative_influence(scorer, world):
    viewer, candidates = world

    [only] = scorer.score(viewer, candidates[:1])

    assert set(only.rank_influence.values()) == {RankInfluence.NEUTRAL}


def test_the_learned_scorer_keeps_negative_scores(scorer, world):
    viewer, candidates = world
    learned = scorer.score(viewer, candidates)
    negative = dataclasses.replace(learned[0], score=-3.5)

    assert scorer.keeps(negative)
    assert scorer.rank_source is RankSource.LEARNED
    assert [e.score for e in rank([negative, *learned[1:]], 100, scorer.keeps)].count(-3.5) == 1


def test_empty_candidate_list_gives_an_empty_result(scorer, world):
    viewer, _ = world

    assert scorer.score(viewer, []) == []
    assert scorer.criterion_influences(viewer, []) == []


def test_result_does_not_depend_on_the_order_of_the_candidates(scorer, world):
    viewer, candidates = world
    shuffled = list(candidates)
    random.Random(3).shuffle(shuffled)

    straight = {s.candidate.profile.id: s for s in scorer.score(viewer, candidates)}
    mixed = {s.candidate.profile.id: s for s in scorer.score(viewer, shuffled)}

    assert straight.keys() == mixed.keys()
    for key, item in straight.items():
        assert mixed[key].score == pytest.approx(item.score)
        assert mixed[key].rank_influence == item.rank_influence


def test_only_the_whitelisted_features_reach_the_model(scorer, world):
    viewer, candidates = world
    matrix = feature_matrix(viewer, candidates)

    assert matrix.shape[1] == len(FEATURE_NAMES) == scorer.n_features
    with pytest.raises(ValueError):
        scorer.raw_scores(np.hstack([matrix, matrix[:, :1]]))


def test_scoring_the_same_candidates_twice_is_identical(scorer, world):
    viewer, candidates = world

    assert scorer.score(viewer, candidates) == scorer.score(viewer, candidates)


def test_importing_the_scorer_module_does_not_import_lightgbm():
    code = (
        "import sys; import app.ranking.lightgbm_scorer, app.ranking.factory, app.ranking.train; "
        "print('lightgbm' in sys.modules)"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"


def test_candidate_helper_type_is_used_by_the_scorer(scorer, world):
    viewer, candidates = world

    assert all(isinstance(c, Candidate) for c in candidates)
    assert len(scorer.score(viewer, candidates)) == len(candidates)
