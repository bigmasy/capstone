import ast
import inspect
import json
import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

import pytest

from app.domain.privacy import coarsen
from app.domain.taxonomy import CategoryCode, SportCode
from app.synthetic import GeneratorParams, generate_profiles, generator
from app.synthetic.__main__ import main
from app.synthetic.serialize import population_digest

BACKEND_DIR = Path(__file__).resolve().parents[3]

# Computed by population_digest(generate_profiles(GeneratorParams(count=60), seed=42)): sha256
# of the canonical JSON (sorted keys, no spaces) of the profiles, see app.synthetic.serialize.
# Update deliberately when the generator or its parameters change.
GOLDEN_DIGEST = "2f564dfc021fefd39e1413557f2ffaaeb56c11200d88f518f7daddeded03fa19"


def test_same_arguments_give_identical_output_and_other_seed_differs():
    params = GeneratorParams(count=20)

    a, b = generate_profiles(params, 1), generate_profiles(params, 1)

    assert a == b
    assert [p.id for p in a] != [p.id for p in generate_profiles(params, 2)]


def test_ids_are_unique_version_4_uuids_derived_from_the_seed():
    profiles = generate_profiles(GeneratorParams(count=60), 42)

    assert len({p.id for p in profiles}) == 60
    assert all(isinstance(p.id, UUID) and p.id.version == 4 for p in profiles)


def test_smaller_count_is_a_prefix_of_a_larger_one():
    small = generate_profiles(GeneratorParams(count=5), 9)
    large = generate_profiles(GeneratorParams(count=12), 9)

    assert small == large[:5]


def test_global_random_state_is_not_touched():
    random.seed(123)
    before = random.getstate()

    generate_profiles(GeneratorParams(count=10), 5)

    assert random.getstate() == before


def test_locations_are_cell_centres_not_exact_points():
    for profile in generate_profiles(GeneratorParams(count=40), 3):
        again = coarsen(profile.cell.latitude, profile.cell.longitude)
        assert again == profile.cell


def test_population_covers_the_taxonomy_and_special_cases():
    profiles = generate_profiles(GeneratorParams(count=400), 42)

    sports = {e.sport for p in profiles for e in p.sports}
    categories = {c.category for p in profiles for c in p.functional.capabilities}
    assert sports == set(SportCode)
    assert categories == set(CategoryCode)
    assert any(not p.functional.capabilities for p in profiles)
    assert any(p.district is None for p in profiles)
    hidden = sum(not p.is_visible for p in profiles)
    assert 0 < hidden < len(profiles) * 0.15
    assert set(Counter(p.intensity for p in profiles)) == {1, 2, 3, 4, 5}


def test_params_change_the_population():
    params = GeneratorParams(count=20, visible_share=0.0)

    assert not any(p.is_visible for p in generate_profiles(params, 1))


def test_output_matches_the_golden_digest():
    digest = population_digest(generate_profiles(GeneratorParams(count=60), 42))

    assert digest == GOLDEN_DIGEST


def test_generator_does_not_depend_on_matching():
    # The simulated population must not be shaped by the scoring it will later be used to test
    modules = {
        n.module
        for n in ast.walk(ast.parse(inspect.getsource(generator)))
        if isinstance(n, ast.ImportFrom) and n.module
    }

    assert not {m for m in modules if m.startswith("app.domain.matching")}


@pytest.mark.parametrize(
    "overrides",
    [
        {"count": 0},
        {"cluster_weights": (0, 0, 0, 0)},
        {"cluster_weights": (1.0,)},
        {"cluster_weights": (-1, 1, 1, 1)},
        {"visible_share": 1.5},
        {"scatter_share": float("nan")},
        {"cluster_sigma_km": -1.0},
        {"intensity_weights": (1, 1, 1)},
        {"sports_count_weights": ((0, 1.0),)},
        {"sports_count_weights": ((99, 1.0),)},
        {"sport_weights": (("not_a_sport", 1.0),)},
        {"cluster_districts": ("a", "b", "c", "d")},
        {"pattern_weights": (("unknown", 1.0),)},
        {"affected_level_weights": (1.0,) * 6},
        {"extra_level_weights": ((9, 1.0),)},
        {"anchor": (95.0, 30.0)},
    ],
)
def test_invalid_generator_params_are_rejected(overrides):
    with pytest.raises(ValueError):
        GeneratorParams(**overrides)


def test_cli_generate_writes_a_document(tmp_path, capsys):
    out = tmp_path / "profiles.json"

    assert main(["generate", "--seed", "42", "--count", "7", "--out", str(out)]) == 0

    document = json.loads(out.read_text(encoding="utf-8"))
    assert (document["seed"], document["count"], len(document["profiles"])) == (42, 7, 7)
    assert document["digest"] == population_digest(generate_profiles(GeneratorParams(count=7), 42))
    assert capsys.readouterr().out == ""
    assert main(["generate", "--seed", "42", "--count", "7"]) == 0
    assert json.loads(capsys.readouterr().out) == document


def test_cli_rejects_non_positive_count():
    with pytest.raises(SystemExit):
        main(["generate", "--count", "0"])


def _run_cli(hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "app.synthetic", "generate", "--seed", "11", "--count", "80"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_output_is_identical_across_hash_seeds():
    outputs = {_run_cli(seed) for seed in ("0", "1", "12345")}

    assert len(outputs) == 1
