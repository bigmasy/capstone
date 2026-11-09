import json

from app.domain.matching.feed import eligible_candidates, rank
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.taxonomy import SportCode
from app.experiment.config import SMOKE
from app.experiment.h2 import list_sizes, run_h2
from app.synthetic import GeneratorParams, generate_profiles
from tests.unit.domain.builders import make_profile


def test_list_sizes_counts_shared_sport_and_radius_on_cell_centres():
    viewer = make_profile(1, sports=[SportCode.SWIMMING], lat=50.45, lon=30.52)
    near = make_profile(2, sports=[SportCode.SWIMMING], lat=50.45, lon=30.58)  # about 4.3 km
    mid = make_profile(3, sports=[SportCode.SWIMMING], lat=50.45, lon=30.70)  # about 12.9 km
    far = make_profile(4, sports=[SportCode.SWIMMING], lat=50.45, lon=32.00)  # over 100 km
    other_sport = make_profile(5, sports=[SportCode.ARCHERY], lat=50.45, lon=30.52)
    hidden = make_profile(6, sports=[SportCode.SWIMMING], visible=False)

    sizes = list_sizes(viewer, [viewer, near, mid, far, other_sport, hidden], (5.0, 10.0, 25.0))

    assert sizes.continuous == 3
    assert sizes.binary == {5.0: 1, 10.0: 1, 25.0: 2}


def test_continuous_list_is_non_empty_exactly_when_the_baseline_ranks_something():
    profiles = generate_profiles(GeneratorParams(count=40), 6)
    scorer = WeightedScorer(DEFAULT_WEIGHTS)

    for viewer in profiles:
        candidates = eligible_candidates(viewer, profiles)
        ranked = rank(scorer.score(viewer, candidates), len(candidates), scorer.keeps)
        assert (list_sizes(viewer, profiles, (10.0,)).continuous > 0) == bool(ranked)


def test_binary_list_is_always_part_of_the_continuous_list_and_grows_with_the_radius():
    result = run_h2(SMOKE)

    for generation in result["generations"]:
        for cell in generation["sizes"].values():
            continuous = cell["continuous"]["nonempty_share"]
            shares = [cell["binary"][r]["nonempty_share"] for r in ("5.0", "10.0")]
            assert shares[0] <= shares[1] <= continuous
            assert cell["binary"]["10.0"]["mean_size"] <= cell["continuous"]["mean_size"]


def test_density_sweep_uses_nested_prefixes_of_one_population():
    result = run_h2(SMOKE)
    seed = result["seeds"][0]
    small = result["generations"][0]["sizes"]["20"]
    profiles = generate_profiles(GeneratorParams(count=20), seed)
    viewers_with_list = sum(list_sizes(v, profiles, (10.0,)).continuous > 0 for v in profiles)

    assert small["viewers"] == 20
    assert small["continuous"]["nonempty_share"] == viewers_with_list / 20


def test_comparisons_are_paired_over_generations_and_cover_every_size_and_radius(tmp_path):
    result = run_h2(SMOKE)

    assert set(result["comparisons"]) == {"R=5.0", "R=10.0"}
    for by_size in result["comparisons"].values():
        assert set(by_size) == {"20", "40", "60"}
        for summary in by_size.values():
            assert summary["n"] == 2
            assert summary["mean"] >= 0.0
    assert result["primary_radius_km"] == 10.0
    assert "tautolog" in " ".join(result["notes"]).lower()


def test_result_is_deterministic_and_json_serialisable():
    first = json.dumps(run_h2(SMOKE), sort_keys=True)

    assert json.dumps(run_h2(SMOKE), sort_keys=True) == first
