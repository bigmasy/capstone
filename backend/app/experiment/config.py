"""Configuration of the experiment harness and its named presets."""

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.experiment.feedback import FeedbackParams
from app.experiment.world import WORLD_NAMES
from app.ranking.train import TrainConfig
from app.synthetic.params import GeneratorParams

SPLIT_SHARES = (0.6, 0.2, 0.2)


@dataclass(frozen=True)
class ExperimentConfig:
    """Everything that defines a run of H1 or H2; echoed into the result.

    :param world: Name of the ground-truth world.
    :param n_profiles: Population size of one generation (H1).
    :param n_generations: Number of independent generations.
    :param base_seed: Seed of generation 0; generation g uses ``base_seed + g``.
    :param generator: Distribution parameters of the population; ``count`` is overridden.
    :param feedback: Logging policy and invitation behaviour.
    :param train: Hyperparameters of the ranker.
    :param split: Shares of train, validation and test viewers.
    :param ks: Cut-offs of the nDCG; the first one is primary.
    :param grid_step: Step of the B1 weight grid (must divide 100).
    :param bootstrap_resamples: Resamples of the bootstrap interval.
    :param bootstrap_seed: Seed of the bootstrap.
    :param min_delta: Smallest mean nDCG difference counted as supported (decision rule).
    :param ipw_ablation: Also train a model with inverse-propensity weights.
    :param radii_km: Radii of the binary filter (H2).
    :param primary_radius_km: Radius of the main comparison (H2).
    :param densities: Population sizes of the density sweep (H2); nested prefixes of one
        population.
    :raises ValueError: If a value is out of range.
    """

    world: str = "interactions"
    n_profiles: int = 400
    n_generations: int = 30
    base_seed: int = 1000
    generator: GeneratorParams = field(default_factory=GeneratorParams)
    feedback: FeedbackParams = field(default_factory=FeedbackParams)
    train: TrainConfig = field(default_factory=TrainConfig)
    split: tuple[float, float, float] = SPLIT_SHARES
    ks: tuple[int, ...] = (10, 5, 20)
    grid_step: int = 5
    bootstrap_resamples: int = 10_000
    bootstrap_seed: int = 20260101
    min_delta: float = 0.01
    ipw_ablation: bool = False
    radii_km: tuple[float, ...] = (5.0, 10.0, 25.0)
    primary_radius_km: float = 10.0
    densities: tuple[int, ...] = (20, 40, 80, 160, 320, 640)

    def __post_init__(self) -> None:
        """Validate the configuration."""
        if self.world not in WORLD_NAMES:
            raise ValueError("unknown world")
        if self.n_profiles < 10 or self.n_generations < 2:
            raise ValueError("need at least 10 profiles and 2 generations")
        if len(self.split) != 3 or min(self.split) <= 0 or abs(sum(self.split) - 1.0) > 1e-9:
            raise ValueError("split must be three positive shares that add up to 1")
        if not self.ks or min(self.ks) < 1:
            raise ValueError("ks needs positive cut-offs")
        if self.grid_step < 1 or 100 % self.grid_step:
            raise ValueError("grid_step must divide 100")
        if self.bootstrap_resamples < 1:
            raise ValueError("bootstrap_resamples must be positive")
        if not self.radii_km or self.primary_radius_km not in self.radii_km:
            raise ValueError("primary_radius_km must be one of radii_km")
        if not self.densities or min(self.densities) < 2:
            raise ValueError("densities need sizes of at least 2")

    @property
    def primary_k(self) -> int:
        """The cut-off of the primary comparison."""
        return self.ks[0]

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as plain JSON-ready data.

        :return: Nested dict with lists instead of tuples.
        """
        data: dict[str, Any] = json.loads(json.dumps(dataclasses.asdict(self)))
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        """Build a configuration from plain data; missing keys keep their defaults.

        :param data: Dict as produced by ``to_dict`` or written by hand.
        :raises ValueError: If a key is unknown or a value is invalid.
        :return: The configuration.
        """
        nested = {"generator": GeneratorParams, "feedback": FeedbackParams, "train": TrainConfig}
        values: dict[str, Any] = {}
        try:
            for key, value in data.items():
                value = _tuples(value)
                values[key] = nested[key](**value) if key in nested else value
            return cls(**values)
        except TypeError as error:
            raise ValueError("configuration has an unknown or malformed field") from error


def _tuples(value: Any) -> Any:
    """Turn lists into tuples recursively (JSON has no tuples, the dataclasses use them)."""
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


FULL = ExperimentConfig()
DEMO_PROFILES = 1000

# Runs in seconds: tiny population, two generations, few small trees
SMOKE = ExperimentConfig(
    n_profiles=60,
    n_generations=2,
    train=TrainConfig(
        seed=0, n_estimators=15, num_leaves=5, min_child_samples=5, early_stopping_rounds=5
    ),
    bootstrap_resamples=200,
    radii_km=(5.0, 10.0),
    primary_radius_km=10.0,
    densities=(20, 40, 60),
)

# The artifact of the demo stack: big enough for the model to learn something, small enough to
# train in well under two minutes on a laptop.
DEMO = ExperimentConfig(
    n_profiles=DEMO_PROFILES,
    n_generations=2,
    train=TrainConfig(seed=0, n_estimators=100, num_leaves=7, min_child_samples=10),
)

PRESETS = {"smoke": SMOKE, "full": FULL, "demo": DEMO}


def load_config(spec: str) -> ExperimentConfig:
    """Return a preset by name or read a JSON file.

    :param spec: ``smoke``, ``full`` or the path of a JSON configuration file.
    :raises ValueError: If the file is not valid JSON or the configuration is invalid.
    :raises OSError: If the file cannot be read.
    :return: The configuration.
    """
    if spec in PRESETS:
        return PRESETS[spec]
    try:
        data = json.loads(Path(spec).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("configuration file is not valid JSON") from error
    if not isinstance(data, dict):
        raise ValueError("configuration file must hold a JSON object")
    return ExperimentConfig.from_dict(data)
