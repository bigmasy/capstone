import ast
import dataclasses
import inspect
import math

import pytest

from app.domain.taxonomy import SkillLevel, SportCode
from app.experiment import world as world_module
from app.experiment.world import WORLD_NAMES, Goal, World, get_world_spec
from app.synthetic import GeneratorParams, generate_profiles
from tests.unit.domain.builders import make_profile


def _pairs():
    profiles = generate_profiles(GeneratorParams(count=40), 7)
    return [(a, b) for a in profiles for b in profiles if a.id != b.id][:300]


@pytest.mark.parametrize("name", WORLD_NAMES)
def test_probabilities_are_in_the_unit_interval_and_deterministic(name):
    world = World(get_world_spec(name), seed=3)
    again = World(get_world_spec(name), seed=3)

    for viewer, candidate in _pairs():
        p = world.acceptance_probability(viewer, candidate)
        assert 0.0 < p < 1.0
        assert p == again.acceptance_probability(viewer, candidate)


def test_the_three_named_worlds_exist_and_unknown_names_are_rejected():
    assert set(WORLD_NAMES) == {"baseline_like", "additive", "interactions"}
    with pytest.raises(ValueError):
        get_world_spec("nope")


def test_other_seed_changes_noise_and_latents():
    spec = get_world_spec("additive")
    viewer, candidate = _pairs()[0]

    a = World(spec, seed=1).acceptance_probability(viewer, candidate)
    b = World(spec, seed=2).acceptance_probability(viewer, candidate)

    assert a != b


def test_pair_noise_is_per_ordered_pair_and_independent_of_call_order():
    world = World(get_world_spec("additive"), seed=5)
    a, b = make_profile(1), make_profile(2)

    forward_first = (world.pair_noise(a.id, b.id), world.pair_noise(b.id, a.id))
    backward_first = (world.pair_noise(b.id, a.id), world.pair_noise(a.id, b.id))

    assert forward_first == backward_first[::-1]
    assert forward_first[0] != forward_first[1]


def test_latent_goal_and_responsiveness_depend_on_seed_and_id_only():
    world = World(get_world_spec("additive"), seed=5)
    profile = make_profile(9, intensity=5)

    assert world.goal_of(profile) == World(get_world_spec("additive"), seed=5).goal_of(profile)
    assert world.responsiveness_of(profile) == world.responsiveness_of(profile)
    assert isinstance(world.goal_of(profile), Goal)


def test_goal_follows_intensity_on_average():
    world = World(get_world_spec("additive"), seed=1)
    easy = [world.goal_of(make_profile(n, intensity=1)) for n in range(1, 300)]
    hard = [world.goal_of(make_profile(n, intensity=5)) for n in range(1, 300)]

    assert easy.count(Goal.RECREATION) > hard.count(Goal.RECREATION)
    assert hard.count(Goal.COMPETITION) > easy.count(Goal.COMPETITION)


def _zero_noise(name, **changes):
    spec = dataclasses.replace(
        get_world_spec(name), noise_sd=0.0, responsiveness_sd=0.0, goal_weight=0.0, **changes
    )
    return World(spec, seed=1)


def test_more_shared_sports_and_better_skill_match_raise_the_logit():
    world = _zero_noise("additive")
    viewer = make_profile(1, sports=[(SportCode.SWIMMING, SkillLevel.ADVANCED)])
    same = make_profile(2, sports=[(SportCode.SWIMMING, SkillLevel.ADVANCED)])
    off = make_profile(3, sports=[(SportCode.SWIMMING, SkillLevel.BEGINNER)])
    more = make_profile(
        4,
        sports=[
            (SportCode.SWIMMING, SkillLevel.ADVANCED),
            (SportCode.CYCLING, SkillLevel.ADVANCED),
        ],
    )
    viewer_two = make_profile(
        5,
        sports=[
            (SportCode.SWIMMING, SkillLevel.ADVANCED),
            (SportCode.CYCLING, SkillLevel.ADVANCED),
        ],
    )

    assert world.logit(viewer, same) > world.logit(viewer, off)
    assert world.logit(viewer_two, more) > world.logit(viewer, same)


def test_sport_overlap_saturates():
    world = _zero_noise("additive")
    codes = [SportCode.SWIMMING, SportCode.CYCLING, SportCode.ARCHERY, SportCode.ATHLETICS]
    viewers = [make_profile(10 + n, sports=codes[: n + 1]) for n in range(4)]
    cands = [make_profile(20 + n, sports=codes[: n + 1]) for n in range(4)]

    logits = [world.logit(v, c) for v, c in zip(viewers, cands, strict=True)]
    steps = [b - a for a, b in zip(logits, logits[1:], strict=False)]

    assert all(s > 0 for s in steps)
    assert steps[0] > steps[1] > steps[2]


def test_distance_decays_exponentially_with_the_cell_centre_distance():
    world = _zero_noise("additive")
    viewer = make_profile(1, lat=50.45, lon=30.52)
    near = make_profile(2, lat=50.45, lon=30.52)
    far = make_profile(3, lat=50.45, lon=30.70)

    gap = world.logit(viewer, near) - world.logit(viewer, far)

    spec = world.spec
    km = 111.195 * math.cos(math.radians(50.45)) * 0.18
    expected = spec.distance_weight * (1 - math.exp(-km / spec.distance_scale_km))
    assert gap == pytest.approx(expected, rel=0.02)


def test_intensity_penalty_is_asymmetric_in_the_additive_world():
    world = _zero_noise("additive")
    viewer = make_profile(1, intensity=3)
    harder = make_profile(2, intensity=5)
    easier = make_profile(3, intensity=1)
    equal = make_profile(4, intensity=3)

    base = world.logit(viewer, equal)
    # The candidate decides: a viewer who asks for more than the candidate prefers costs more
    harder_viewer = make_profile(5, intensity=5)
    easier_viewer = make_profile(6, intensity=1)
    cand = make_profile(7, intensity=3)
    cost_up = base - world.logit(harder_viewer, cand)
    cost_down = base - world.logit(easier_viewer, cand)
    assert cost_up > cost_down > 0
    assert world.logit(viewer, harder) < base
    assert world.logit(viewer, easier) < base


def test_baseline_like_world_penalises_intensity_symmetrically():
    world = _zero_noise("baseline_like")
    cand = make_profile(7, intensity=3)
    base = world.logit(make_profile(1, intensity=3), cand)

    up = base - world.logit(make_profile(2, intensity=5), cand)
    down = base - world.logit(make_profile(3, intensity=1), cand)

    assert up == pytest.approx(down)


def test_bottleneck_functional_compatibility_is_set_by_the_worst_category():
    world = _zero_noise("additive")
    viewer = make_profile(1, caps=[("mobility_lower", 4, None), ("vision", 4, None)])
    good = make_profile(2, caps=[("mobility_lower", 4, None), ("vision", 4, None)])
    one_bad = make_profile(3, caps=[("mobility_lower", 4, None), ("vision", 0, None)])
    both_mid = make_profile(4, caps=[("mobility_lower", 2, None), ("vision", 2, None)])

    # The mean of one_bad (0.5) equals the mean of both_mid (0.5), the minimum differs
    assert world.logit(viewer, good) > world.logit(viewer, both_mid) > world.logit(viewer, one_bad)


def test_shared_equipment_adds_a_bonus():
    world = _zero_noise("additive")
    viewer = make_profile(1, caps=[("mobility_lower", 2, "wheelchair_active")])
    same = make_profile(2, caps=[("mobility_lower", 2, "wheelchair_active")])
    other = make_profile(3, caps=[("mobility_lower", 2, "handcycle")])

    assert world.logit(viewer, same) - world.logit(viewer, other) == pytest.approx(
        world.spec.equipment_bonus
    )


def test_interactions_world_makes_distance_matter_more_for_limited_mobility():
    additive = _zero_noise("additive")
    interactions = _zero_noise("interactions")
    viewer = make_profile(1, lat=50.45, lon=30.52)
    near_mobile = make_profile(2, lat=50.45, lon=30.52, caps=[("mobility_lower", 4, None)])
    far_mobile = make_profile(3, lat=50.45, lon=30.80, caps=[("mobility_lower", 4, None)])
    near_limited = make_profile(4, lat=50.45, lon=30.52, caps=[("mobility_lower", 1, None)])
    far_limited = make_profile(5, lat=50.45, lon=30.80, caps=[("mobility_lower", 1, None)])

    def drop(world, near, far):
        return world.logit(viewer, near) - world.logit(viewer, far)

    assert drop(interactions, near_mobile, far_mobile) == pytest.approx(
        drop(additive, near_mobile, far_mobile), rel=0.35
    )
    assert drop(interactions, near_limited, far_limited) > 1.5 * drop(
        additive, near_limited, far_limited
    )


def test_goal_match_raises_acceptance_when_goals_are_equal():
    spec = dataclasses.replace(get_world_spec("additive"), noise_sd=0.0, responsiveness_sd=0.0)
    world = World(spec, seed=2)
    people = [make_profile(n, intensity=3) for n in range(1, 120)]
    same = [(a, b) for a in people[:30] for b in people if world.goal_of(a) == world.goal_of(b)]
    differ = [
        (a, b)
        for a in people[:30]
        for b in people
        if abs(world.goal_of(a).value - world.goal_of(b).value) == 2
    ]
    assert same and differ

    mean_same = sum(world.logit(a, b) for a, b in same) / len(same)
    mean_differ = sum(world.logit(a, b) for a, b in differ) / len(differ)

    assert mean_same > mean_differ


def test_world_module_does_not_import_the_baseline_or_its_weights():
    tree = ast.parse(inspect.getsource(world_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    app_imports = {m for m in imported if m.startswith("app.")}
    assert not {m for m in app_imports if m.startswith("app.domain.matching")}
    assert "app.domain.functional" not in app_imports
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"DEFAULT_WEIGHTS", "DEFAULT_TABLES", "WeightedScorer", "Weights"}
