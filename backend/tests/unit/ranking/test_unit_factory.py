import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.domain.matching.weighted import WeightedScorer
from app.ranking.artifact import MANIFEST_FILE, MODEL_FILE
from app.ranking.factory import build_scorer
from app.ranking.lightgbm_scorer import LightGBMScorer
from app.ranking.train import TrainConfig, export_artifact, train_ranker
from tests.unit.ranking.data import make_queries

pytest.importorskip("lightgbm")
pytestmark = pytest.mark.ml


@dataclass
class FakeSettings:
    RANKER_ENABLED: bool = True


@pytest.fixture(scope="module")
def good_artifact(tmp_path_factory) -> Path:
    model = train_ranker(
        make_queries(1, 30),
        make_queries(2, 10),
        TrainConfig(seed=1, n_estimators=10, num_leaves=5, min_child_samples=5),
    )
    directory = tmp_path_factory.mktemp("good")
    export_artifact(model, directory, seeds={"train": 1}, n_events=10, metrics={})
    return directory


def _copy(source: Path, target: Path) -> Path:
    target.mkdir()
    for name in (MODEL_FILE, MANIFEST_FILE):
        (target / name).write_bytes((source / name).read_bytes())
    return target


def test_a_valid_artifact_gives_the_learned_scorer(good_artifact):
    assert isinstance(build_scorer(FakeSettings(), good_artifact), LightGBMScorer)


def test_no_directory_gives_the_baseline():
    assert isinstance(build_scorer(FakeSettings(), None), WeightedScorer)


def test_missing_artifact_gives_the_baseline(tmp_path):
    assert isinstance(build_scorer(FakeSettings(), tmp_path / "missing"), WeightedScorer)


def test_disabled_ranker_gives_the_baseline(good_artifact):
    assert isinstance(
        build_scorer(FakeSettings(RANKER_ENABLED=False), good_artifact), WeightedScorer
    )


def test_settings_without_ranker_fields_are_accepted(good_artifact):
    assert isinstance(build_scorer(object(), good_artifact), LightGBMScorer)


def test_corrupt_model_gives_the_baseline(good_artifact, tmp_path):
    directory = _copy(good_artifact, tmp_path / "bad")
    (directory / MODEL_FILE).write_text("tree\ngarbage", encoding="utf-8")

    assert isinstance(build_scorer(FakeSettings(), directory), WeightedScorer)


def test_a_model_that_lightgbm_cannot_parse_gives_the_baseline(good_artifact, tmp_path):
    import hashlib

    directory = _copy(good_artifact, tmp_path / "unparsable")
    text = "tree\nthis is not a model"
    (directory / MODEL_FILE).write_text(text, encoding="utf-8")
    manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest["model_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")

    assert isinstance(build_scorer(FakeSettings(), directory), WeightedScorer)


@pytest.mark.parametrize(
    "changes",
    [{"feature_schema_version": 99}, {"taxonomy_version": "0.0.1"}, {"model_sha256": "0" * 64}],
)
def test_version_or_hash_mismatch_gives_the_baseline(good_artifact, tmp_path, changes):
    directory = _copy(good_artifact, tmp_path / "mismatch")
    manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest.update(changes)
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")

    assert isinstance(build_scorer(FakeSettings(), directory), WeightedScorer)


def test_a_model_with_a_different_number_of_features_gives_the_baseline(tmp_path):
    from app.ranking.artifact import write_artifact as write

    model = train_ranker(
        [q.__class__(q.X[:, :5], q.y) for q in make_queries(1, 30)],
        [],
        TrainConfig(seed=1, n_estimators=5, num_leaves=5, min_child_samples=5),
    )
    write(
        tmp_path,
        model.model_text,
        hyperparameters={},
        seeds={},
        counts={},
        metrics={},
        lightgbm_version="4.6.0",
    )

    assert isinstance(build_scorer(FakeSettings(), tmp_path), WeightedScorer)


def test_missing_lightgbm_gives_the_baseline(good_artifact, monkeypatch):
    def refuse(*args, **kwargs):
        raise ImportError("no lightgbm")

    monkeypatch.setattr(LightGBMScorer, "from_directory", classmethod(refuse))

    assert isinstance(build_scorer(FakeSettings(), good_artifact), WeightedScorer)
