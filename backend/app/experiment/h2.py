"""H2: when the population gets sparse, does the continuous list stay non-empty more often?

The binary filter keeps a candidate only if they share a sport and lie within the radius R
of the viewer (distance between cell centres). The continuous list keeps every candidate
that shares a sport and orders them by score, so distance lowers a score but never removes
a candidate.

By construction the binary list is a part of the continuous one, so the continuous list is
non-empty whenever the binary one is, and the difference of the shares can never be
negative. The statement is therefore close to a tautology; what the experiment measures is
the size of the gain for a given radius and density, with generation-level confidence
intervals. The density sweep uses nested prefixes of one generated population.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.domain.matching.feed import eligible_candidates
from app.domain.profile import ProfileView
from app.experiment.config import ExperimentConfig
from app.experiment.report import library_versions
from app.experiment.stats import paired_summary
from app.synthetic.generator import generate_profiles

NOTES = (
    "The binary list is a subset of the continuous list, so the continuous list is non-empty "
    "whenever the binary one is: the comparison is tautological in sign and informative only "
    "in the size of the difference.",
    "Viewers are all profiles of the subset; candidates must be visible, not the viewer and "
    "share at least one sport. Distances are between grid cell centres.",
    "The minimum-shared-categories rule withholds functional data but never removes a "
    "candidate, so these list sizes are the sizes of the product feed.",
)


@dataclass(frozen=True, slots=True)
class ListSizes:
    """Sizes of the candidate lists of one viewer.

    :param continuous: Candidates of the continuous list (shared sport, any distance).
    :param binary: Candidates of the binary filter for each radius in km.
    """

    continuous: int
    binary: dict[float, int]


def list_sizes(
    viewer: ProfileView, profiles: Sequence[ProfileView], radii_km: Sequence[float]
) -> ListSizes:
    """Return how many candidates the continuous list and each binary filter keep.

    :param viewer: The viewer.
    :param profiles: Population to choose from.
    :param radii_km: Radii of the binary filter.
    :return: The sizes.
    """
    candidates = eligible_candidates(viewer, profiles)
    return ListSizes(
        continuous=len(candidates),
        binary={r: sum(c.distance_km <= r for c in candidates) for r in radii_km},
    )


def _cell(
    viewers: Sequence[ProfileView], subset: Sequence[ProfileView], radii: Sequence[float]
) -> dict[str, Any]:
    """Shares of non-empty lists and mean sizes for one population size."""
    sizes = [list_sizes(v, subset, radii) for v in viewers]
    n = len(sizes)

    def block(counts: list[int]) -> dict[str, float]:
        return {
            "nonempty_share": sum(c > 0 for c in counts) / n,
            "mean_size": sum(counts) / n,
        }

    return {
        "viewers": n,
        "continuous": block([s.continuous for s in sizes]),
        "binary": {str(r): block([s.binary[r] for s in sizes]) for r in radii},
    }


def run_generation(config: ExperimentConfig, generation: int) -> dict[str, Any]:
    """Run the density sweep on one generated population.

    :param config: Experiment configuration.
    :param generation: Index of the generation; its seed is ``base_seed + generation``.
    :return: JSON-ready result keyed by population size.
    """
    seed = config.base_seed + generation
    population = generate_profiles(replace(config.generator, count=max(config.densities)), seed)
    sizes = {}
    for n in config.densities:
        subset = population[:n]
        sizes[str(n)] = _cell(subset, subset, config.radii_km)
    return {"generation": generation, "seed": seed, "sizes": sizes}


def run_h2(config: ExperimentConfig) -> dict[str, Any]:
    """Run H2 over all generations with paired generation-level differences.

    :param config: Experiment configuration.
    :return: JSON-ready result with the configuration, seeds, versions, per-generation shares
        and, for each radius and size, the summary of continuous minus binary.
    """
    generations = [run_generation(config, g) for g in range(config.n_generations)]
    comparisons: dict[str, dict[str, Any]] = {}
    for radius in config.radii_km:
        by_size: dict[str, Any] = {}
        for n in config.densities:
            diffs = [
                g["sizes"][str(n)]["continuous"]["nonempty_share"]
                - g["sizes"][str(n)]["binary"][str(radius)]["nonempty_share"]
                for g in generations
            ]
            by_size[str(n)] = paired_summary(
                diffs, resamples=config.bootstrap_resamples, seed=config.bootstrap_seed
            ).as_dict()
        comparisons[f"R={radius}"] = by_size
    return {
        "hypothesis": "h2",
        "config": config.to_dict(),
        "seeds": [config.base_seed + g for g in range(config.n_generations)],
        "versions": library_versions(),
        "primary_radius_km": config.primary_radius_km,
        "generations": generations,
        "comparisons": comparisons,
        "notes": list(NOTES),
    }
