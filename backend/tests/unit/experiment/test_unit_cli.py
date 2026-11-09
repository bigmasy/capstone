import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.experiment.__main__ import main
from app.experiment.config import SMOKE

BACKEND_DIR = Path(__file__).resolve().parents[3]


def test_h2_command_writes_json_with_config_seeds_and_versions(tmp_path):
    out = tmp_path / "h2.json"

    assert main(["h2", "--config", "smoke", "--out", str(out)]) == 0

    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["hypothesis"] == "h2"
    assert result["config"] == SMOKE.to_dict()
    assert result["seeds"] == [SMOKE.base_seed, SMOKE.base_seed + 1]
    assert "numpy" in result["versions"]


def test_result_goes_to_stdout_without_out(capsys):
    assert main(["h2", "--config", "smoke"]) == 0

    assert json.loads(capsys.readouterr().out)["hypothesis"] == "h2"


def test_config_file_and_world_override(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**SMOKE.to_dict(), "n_generations": 3}), encoding="utf-8")
    out = tmp_path / "h2.json"

    assert main(["h2", "--config", str(path), "--world", "additive", "--out", str(out)]) == 0

    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["config"]["world"] == "additive"
    assert len(result["generations"]) == 3


def test_unknown_command_world_and_config_are_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main(["h3", "--config", "smoke"])
    with pytest.raises(SystemExit):
        main(["h2", "--config", "smoke", "--world", "nope"])
    with pytest.raises(SystemExit):
        main(["h2", "--config", str(tmp_path / "missing.json")])
    bad = tmp_path / "bad.json"
    bad.write_text('{"nonsense": 1}', encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["h2", "--config", str(bad)])


def _run(hypothesis: str, hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "app.experiment", hypothesis, "--config", "smoke"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.mark.ml
@pytest.mark.parametrize("hypothesis", ["h1", "h2"])
def test_results_are_identical_across_hash_seeds(hypothesis):
    pytest.importorskip("lightgbm")

    outputs = {_run(hypothesis, seed) for seed in ("0", "777")}

    assert len(outputs) == 1


@pytest.mark.ml
def test_h1_command_runs_the_smoke_configuration_and_exports_an_artifact(tmp_path):
    pytest.importorskip("lightgbm")
    out = tmp_path / "h1.json"

    code = main(
        ["h1", "--config", "smoke", "--out", str(out), "--artifact-dir", str(tmp_path / "model")]
    )

    result = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0
    assert result["hypothesis"] == "h1"
    assert (tmp_path / "model" / "model.txt").is_file()
    assert (tmp_path / "model" / "manifest.json").is_file()


@pytest.mark.ml
def test_train_command_writes_a_loadable_artifact_deterministically(tmp_path):
    pytest.importorskip("lightgbm")
    from app.ranking.artifact import load_artifact

    for name in ("first", "second"):
        assert main(["train", "--out", str(tmp_path / name), "--config", "smoke"]) == 0

    first = (tmp_path / "first" / "model.txt").read_bytes()
    assert first == (tmp_path / "second" / "model.txt").read_bytes()
    assert load_artifact(tmp_path / "first").manifest.seeds["generation"] == SMOKE.base_seed


@pytest.mark.ml
def test_train_command_seed_changes_the_data_and_the_model(tmp_path):
    pytest.importorskip("lightgbm")

    assert main(["train", "--out", str(tmp_path / "a"), "--config", "smoke", "--seed", "5"]) == 0
    assert main(["train", "--out", str(tmp_path / "b"), "--config", "smoke", "--seed", "6"]) == 0

    assert (tmp_path / "a" / "model.txt").read_bytes() != (
        tmp_path / "b" / "model.txt"
    ).read_bytes()


def test_train_command_needs_an_output_directory():
    with pytest.raises(SystemExit):
        main(["train", "--config", "smoke"])


def test_the_demo_preset_is_a_valid_configuration():
    from app.experiment.config import DEMO, load_config

    assert load_config("demo") is DEMO
    assert DEMO.n_profiles > SMOKE.n_profiles
