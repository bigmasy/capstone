"""H1: does the learned ranker beat the weighted baseline on nDCG@k?

One generation is an independent run of the whole pipeline: generate a population, split
its viewers 60/20/20, log feedback for the train and validation viewers, fit B1 and the
ranker on the training labels (invited rows only), select on the validation viewers and
evaluate every method on the test viewers against the true acceptance probabilities of the
world. The methods are compared through per-generation mean differences.

The main comparison is the ranker against B1 (the baseline whose weights were fitted on the
same labels), not against the untouched default weights B0.
"""

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from app.domain.matching.weights import DEFAULT_WEIGHTS, Weights
from app.domain.profile import ProfileView
from app.experiment.baselines import FittedBaseline, baseline_scores, select_b1, weight_grid
from app.experiment.config import ExperimentConfig
from app.experiment.dataset import evaluation_lists, logged_queries, split_viewers
from app.experiment.feedback import FeedbackLog, simulate_feedback
from app.experiment.metrics import mean_ndcg
from app.experiment.report import library_versions
from app.experiment.stats import decide, paired_summary
from app.experiment.world import World, get_world_spec
from app.ranking.artifact import ArtifactManifest
from app.ranking.features import QueryData
from app.ranking.train import (
    TrainedModel,
    booster_scores,
    export_artifact,
    filter_trainable,
    load_booster,
    train_ranker,
)
from app.synthetic.generator import generate_profiles

ScoreFn = Callable[[np.ndarray], np.ndarray]

PRIMARY = ("lightgbm", "B1")


def _ndcg_table(
    lists: Sequence[tuple[np.ndarray, np.ndarray]], score: ScoreFn, ks: Sequence[int]
) -> dict[str, dict[str, float | int]]:
    """Mean nDCG@k of one method over evaluation lists, with the exclusion counts."""
    table: dict[str, dict[str, float | int]] = {}
    for k in ks:
        summary = mean_ndcg(((score(x), gains) for x, gains in lists), k)
        if summary.mean is None:
            raise ValueError("no evaluation list has a positive gain")
        table[str(k)] = {
            "mean": summary.mean,
            "n_queries": summary.n_queries,
            "n_excluded": summary.n_excluded,
        }
    return table


def _observed_ndcg(queries: Sequence[QueryData], score: ScoreFn, k: int) -> float:
    """Mean nDCG@k on logged queries with their observed binary labels."""
    value = mean_ndcg(((score(q.X), q.y) for q in queries), k).mean
    return float("nan") if value is None else value


def _weights_fn(weights: Weights) -> ScoreFn:
    """Score function of the weighted baseline with the given weights."""
    return lambda matrix: baseline_scores(matrix, weights)


def _booster_fn(booster: Any) -> ScoreFn:
    """Score function of a loaded LightGBM booster."""
    return lambda matrix: booster_scores(booster, matrix)


def _weights_dict(weights: Weights) -> dict[str, int]:
    """Weights as a plain dict."""
    return asdict(weights)


@dataclass(frozen=True)
class _GenerationData:
    """Population, split, feedback log and labelled queries of one generation."""

    seed: int
    profiles: list[ProfileView]
    world: World
    test_viewers: list[ProfileView]
    log: FeedbackLog
    train_queries: list[QueryData]
    valid_queries: list[QueryData]
    n_train_viewers: int
    n_valid_viewers: int


def _prepare_generation(config: ExperimentConfig, generation: int) -> _GenerationData:
    """Generate the population, split the viewers and log the feedback of a generation."""
    seed = config.base_seed + generation
    profiles = generate_profiles(replace(config.generator, count=config.n_profiles), seed)
    by_id = {p.id: p for p in profiles}
    world = World(get_world_spec(config.world), seed)
    train_v, valid_v, test_v = split_viewers(profiles, config.split, seed)
    log = simulate_feedback(train_v + valid_v, profiles, world, config.feedback, seed)
    return _GenerationData(
        seed=seed,
        profiles=profiles,
        world=world,
        test_viewers=test_v,
        log=log,
        train_queries=logged_queries(log, train_v, by_id),
        valid_queries=logged_queries(log, valid_v, by_id),
        n_train_viewers=len(train_v),
        n_valid_viewers=len(valid_v),
    )


def _export(
    model: TrainedModel,
    directory: Path,
    config: ExperimentConfig,
    data: _GenerationData,
    metrics: dict[str, float],
) -> ArtifactManifest:
    """Export the plain model of a generation with the validation nDCG of both methods."""
    primary_k = config.primary_k
    return export_artifact(
        model,
        directory,
        seeds={"generation": data.seed, "train": config.train.seed, "split": data.seed},
        n_events=len(data.log.impressions),
        metrics={
            "baseline": {f"ndcg@{primary_k}": metrics["B1"]},
            "model": {f"ndcg@{primary_k}": metrics["lightgbm"]},
        },
    )


def _fit_b1(config: ExperimentConfig, data: _GenerationData) -> FittedBaseline:
    """Choose the B1 weights on the validation queries."""
    return select_b1(
        filter_trainable(data.valid_queries)[0], config.primary_k, weight_grid(config.grid_step)
    )


def train_artifact(
    config: ExperimentConfig, directory: Path, generation: int = 0
) -> ArtifactManifest:
    """Train the plain ranker on one generation and export it as an artifact.

    This is the first half of ``run_generation`` without the evaluation on the test viewers.
    The same configuration and seeds give the same model on the same machine.

    :param config: Experiment configuration; ``base_seed`` and ``train.seed`` fix the run.
    :param directory: Target directory of the artifact.
    :param generation: Index of the generation; its seed is ``base_seed + generation``.
    :raises ValueError: If the generation has no usable training query.
    :return: The manifest that was written.
    """
    data = _prepare_generation(config, generation)
    model = train_ranker(data.train_queries, data.valid_queries, config.train)
    b1 = _fit_b1(config, data)
    booster = load_booster(model.model_text)
    metrics = {
        "B1": _observed_ndcg(data.valid_queries, _weights_fn(b1.weights), config.primary_k),
        "lightgbm": _observed_ndcg(data.valid_queries, _booster_fn(booster), config.primary_k),
    }
    return _export(model, directory, config, data, metrics)


def run_generation(
    config: ExperimentConfig, generation: int, artifact_dir: Path | None = None
) -> dict[str, Any]:
    """Run the pipeline once and report every method's nDCG on the test viewers.

    :param config: Experiment configuration.
    :param generation: Index of the generation; its seed is ``base_seed + generation``.
    :param artifact_dir: If given, the plain model is exported there as an artifact.
    :return: JSON-ready result of the generation.
    """
    data = _prepare_generation(config, generation)
    profiles, world, log = data.profiles, data.world, data.log
    train_q, valid_q = data.train_queries, data.valid_queries
    test_v = data.test_viewers
    primary_k = config.primary_k

    b1 = _fit_b1(config, data)
    scorers: dict[str, ScoreFn] = {
        "B0": _weights_fn(DEFAULT_WEIGHTS),
        "B1": _weights_fn(b1.weights),
    }
    models: dict[str, TrainedModel] = {}
    variants = {"lightgbm": config.train}
    if config.ipw_ablation:
        variants["lightgbm_ipw"] = replace(config.train, use_ipw=True)
    for name, train_config in variants.items():
        model = train_ranker(train_q, valid_q, train_config)
        models[name] = model
        booster = load_booster(model.model_text)
        scorers[name] = _booster_fn(booster)

    lists = evaluation_lists(test_v, profiles, world, config.feedback.max_candidates)
    ndcg = {name: _ndcg_table(lists, fn, config.ks) for name, fn in scorers.items()}
    validation = {name: _observed_ndcg(valid_q, fn, primary_k) for name, fn in scorers.items()}
    invited = log.invited_rows()
    if artifact_dir is not None and generation == 0:
        _export(models["lightgbm"], artifact_dir, config, data, validation)
    return {
        "generation": generation,
        "seed": data.seed,
        "viewers": {
            "train": data.n_train_viewers,
            "valid": data.n_valid_viewers,
            "test": len(test_v),
            "test_without_candidates": len(test_v) - len(lists),
        },
        "logged": {
            "impressions": len(log.impressions),
            "invited_rows": len(invited),
            "accepted_rate": sum(bool(i.accepted) for i in invited) / max(1, len(invited)),
            "train_queries": models["lightgbm"].n_train_queries,
            "valid_queries": models["lightgbm"].n_valid_queries,
        },
        "b1": {"weights": _weights_dict(b1.weights), "selection_ndcg": b1.validation_ndcg},
        "models": {
            name: {
                "best_iteration": model.best_iteration,
                "dropped_train_queries": model.n_dropped_train_queries,
                "dropped_valid_queries": model.n_dropped_valid_queries,
            }
            for name, model in models.items()
        },
        "ndcg": ndcg,
        "validation_ndcg": validation,
    }


def _comparison_pairs(config: ExperimentConfig) -> list[tuple[str, str]]:
    """Pairs (method, reference) that are compared, the primary one first."""
    pairs = [PRIMARY, ("lightgbm", "B0"), ("B1", "B0")]
    if config.ipw_ablation:
        pairs += [("lightgbm_ipw", "B1"), ("lightgbm_ipw", "lightgbm")]
    return pairs


def run_h1(config: ExperimentConfig, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Run H1 over all generations and compare the methods with paired statistics.

    :param config: Experiment configuration.
    :param artifact_dir: If given, the model of generation 0 is exported there.
    :return: JSON-ready result with the configuration, seeds, versions, per-generation
        values, paired comparisons and the decision on the primary comparison.
    """
    generations = [run_generation(config, g, artifact_dir) for g in range(config.n_generations)]
    comparisons: dict[str, dict[str, Any]] = {}
    for method, reference in _comparison_pairs(config):
        by_k: dict[str, Any] = {}
        for k in config.ks:
            diffs = [
                g["ndcg"][method][str(k)]["mean"] - g["ndcg"][reference][str(k)]["mean"]
                for g in generations
            ]
            by_k[str(k)] = paired_summary(
                diffs, resamples=config.bootstrap_resamples, seed=config.bootstrap_seed
            ).as_dict()
        comparisons[f"{method}_vs_{reference}"] = by_k
    primary = paired_summary(
        [
            g["ndcg"][PRIMARY[0]][str(config.primary_k)]["mean"]
            - g["ndcg"][PRIMARY[1]][str(config.primary_k)]["mean"]
            for g in generations
        ],
        resamples=config.bootstrap_resamples,
        seed=config.bootstrap_seed,
    )
    return {
        "hypothesis": "h1",
        "config": config.to_dict(),
        "seeds": [config.base_seed + g for g in range(config.n_generations)],
        "versions": library_versions(),
        "generations": generations,
        "comparisons": comparisons,
        "decision": {
            "primary": f"{PRIMARY[0]}_vs_{PRIMARY[1]}@{config.primary_k}",
            "rule": "lower bound of the bootstrap interval > 0 and mean difference >= min_delta",
            "min_delta": config.min_delta,
            "supported": decide(primary, min_delta=config.min_delta),
        },
    }
