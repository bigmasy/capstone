import json
import math
from dataclasses import replace

import pytest

from app.experiment.config import SMOKE, ExperimentConfig, load_config
from app.experiment.dataset import split_viewers
from app.synthetic import GeneratorParams, generate_profiles

pytest.importorskip("lightgbm")
pytestmark = pytest.mark.ml

from app.experiment.h1 import run_h1  # noqa: E402
from app.ranking.artifact import load_artifact  # noqa: E402


@pytest.fixture(scope="module")
def smoke_result():
    return run_h1(SMOKE)


def test_split_is_viewer_level_disjoint_and_sixty_twenty_twenty():
    profiles = generate_profiles(GeneratorParams(count=100), 3)

    train, valid, test = split_viewers(profiles, (0.6, 0.2, 0.2), seed=3)

    assert (len(train), len(valid), len(test)) == (60, 20, 20)
    ids = [p.id for part in (train, valid, test) for p in part]
    assert len(set(ids)) == 100
    assert split_viewers(profiles, (0.6, 0.2, 0.2), seed=3) == (train, valid, test)
    assert split_viewers(profiles, (0.6, 0.2, 0.2), seed=4)[0] != train


def test_smoke_run_reports_config_seeds_versions_and_generations(smoke_result):
    assert smoke_result["hypothesis"] == "h1"
    assert smoke_result["config"] == SMOKE.to_dict()
    assert smoke_result["seeds"] == [SMOKE.base_seed, SMOKE.base_seed + 1]
    assert {"python", "numpy", "scipy", "lightgbm", "taxonomy", "feature_schema"} <= set(
        smoke_result["versions"]
    )
    assert len(smoke_result["generations"]) == 2


def test_every_generation_has_all_methods_and_cut_offs(smoke_result):
    for generation in smoke_result["generations"]:
        assert set(generation["ndcg"]) == {"B0", "B1", "lightgbm"}
        for method in generation["ndcg"].values():
            assert set(method) == {"10", "5", "20"}
            for cell in method.values():
                assert 0.0 <= cell["mean"] <= 1.0
                assert cell["n_queries"] > 0
                assert cell["n_excluded"] >= 0
        assert sum(generation["viewers"][p] for p in ("train", "valid", "test")) == SMOKE.n_profiles
        assert generation["b1"]["weights"].keys() == {
            "sport",
            "distance",
            "functional",
            "intensity",
        }
        assert sum(generation["b1"]["weights"].values()) == 100


def test_comparisons_are_paired_over_generations(smoke_result):
    comparison = smoke_result["comparisons"]["lightgbm_vs_B1"]["10"]

    assert comparison["n"] == 2
    assert comparison["ci_low"] <= comparison["mean"] <= comparison["ci_high"]
    per_generation = [
        g["ndcg"]["lightgbm"]["10"]["mean"] - g["ndcg"]["B1"]["10"]["mean"]
        for g in smoke_result["generations"]
    ]
    assert comparison["mean"] == pytest.approx(sum(per_generation) / 2)
    assert set(smoke_result["comparisons"]) == {"lightgbm_vs_B1", "lightgbm_vs_B0", "B1_vs_B0"}


def test_decision_rule_is_recorded(smoke_result):
    decision = smoke_result["decision"]

    assert decision["primary"] == "lightgbm_vs_B1@10"
    assert decision["min_delta"] == 0.01
    assert isinstance(decision["supported"], bool)


def test_result_is_json_serialisable_and_deterministic(smoke_result):
    text = json.dumps(smoke_result, sort_keys=True)

    assert json.dumps(run_h1(SMOKE), sort_keys=True) == text
    assert not any(isinstance(v, float) and math.isnan(v) for v in _floats(smoke_result))


def _floats(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _floats(item)
    elif isinstance(value, list):
        for item in value:
            yield from _floats(item)
    elif isinstance(value, float):
        yield value


def test_ipw_ablation_adds_a_model_and_its_comparisons():
    result = run_h1(replace(SMOKE, ipw_ablation=True))

    assert set(result["generations"][0]["ndcg"]) == {"B0", "B1", "lightgbm", "lightgbm_ipw"}
    assert "lightgbm_ipw_vs_B1" in result["comparisons"]


def test_first_generation_can_be_exported_as_an_artifact(tmp_path):
    result = run_h1(SMOKE, artifact_dir=tmp_path / "model")

    loaded = load_artifact(tmp_path / "model")
    assert loaded.manifest.seeds["generation"] == SMOKE.base_seed
    assert set(loaded.manifest.metrics) == {"baseline", "model"}
    assert loaded.manifest.counts["queries"] == result["generations"][0]["logged"]["train_queries"]


def test_config_round_trips_through_json_and_rejects_unknown_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(SMOKE.to_dict()), encoding="utf-8")

    assert load_config(str(path)) == SMOKE
    assert load_config("smoke") is SMOKE
    with pytest.raises(ValueError):
        ExperimentConfig.from_dict({"nonsense": 1})
    with pytest.raises(ValueError):
        ExperimentConfig.from_dict({"train": {"nonsense": 1}})
    with pytest.raises(ValueError):
        ExperimentConfig(world="nope")
