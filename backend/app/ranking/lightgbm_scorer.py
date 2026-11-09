"""The learned scorer: LightGBM lambdarank behind the domain ``Scorer`` port.

LightGBM is imported only when an artifact is loaded, so the API starts without it. The
numbers the caller may see always come from the baseline: the breakdown of a result is the
baseline breakdown, and the model contributes only a rank order plus a coarse, qualitative
influence per criterion.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.domain.matching.features import FEATURE_NAMES
from app.domain.matching.scorer import (
    Candidate,
    Criterion,
    RankInfluence,
    RankSource,
    Scored,
    Scorer,
)
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.profile import ProfileView
from app.ranking.artifact import ArtifactManifest, ModelArtifactError, load_artifact
from app.ranking.features import feature_matrix

# Features that belong to each criterion of the baseline breakdown; together they cover the
# whole schema, so the influence of the criteria adds up to the influence of the model
CRITERION_FEATURES: dict[str, tuple[str, ...]] = {
    "sport": (
        "n_shared_sports",
        "sport_jaccard",
        "min_skill_gap_shared",
        "viewer_n_sports",
        "cand_n_sports",
    ),
    "distance": ("distance_band",),
    "intensity": (
        "viewer_intensity",
        "cand_intensity",
        "intensity_diff_signed",
        "intensity_diff_abs",
    ),
    "functional": ("functional_level",),
}

# A contribution counts as raising or lowering when it is more than this share of the spread
# (standard deviation) of the model scores in the list away from the list average
INFLUENCE_THRESHOLD = 0.25

_Float = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CriterionInfluence:
    """Qualitative effect of each criterion on the position of one candidate.

    :param sport: Effect of the sport features.
    :param distance: Effect of the distance band.
    :param intensity: Effect of the intensity features.
    :param functional: Effect of the functional level.
    """

    sport: RankInfluence
    distance: RankInfluence
    intensity: RankInfluence
    functional: RankInfluence

    def as_mapping(self) -> dict[Criterion, RankInfluence]:
        """Return the influences keyed by criterion, the form carried by ``Scored``.

        :return: One entry per criterion of the breakdown.
        """
        return {
            Criterion.SPORT: self.sport,
            Criterion.DISTANCE: self.distance,
            Criterion.FUNCTIONAL: self.functional,
            Criterion.INTENSITY: self.intensity,
        }


def _classify(centred: _Float, spread: float) -> list[RankInfluence]:
    """Turn centred contributions into qualitative influences relative to the list spread."""
    if spread <= 1e-12:
        return [RankInfluence.NEUTRAL] * len(centred)
    limit = INFLUENCE_THRESHOLD * spread
    return [
        RankInfluence.RAISES
        if value > limit
        else RankInfluence.LOWERS
        if value < -limit
        else RankInfluence.NEUTRAL
        for value in centred
    ]


def _centred(values: _Float) -> _Float:
    """Subtract the list mean (summed exactly, so the order of the list does not matter)."""
    mean = math.fsum(values.tolist()) / len(values)
    return values - mean


class LightGBMScorer:
    """Scorer that orders candidates by a LightGBM lambdarank model.

    :param booster: Loaded LightGBM booster.
    :param manifest: Manifest of the artifact the booster came from.
    :param baseline: Scorer whose breakdown is reported; defaults to the weighted baseline.
    """

    name = "lightgbm"
    rank_source = RankSource.LEARNED

    def __init__(
        self, booster: Any, manifest: ArtifactManifest, baseline: Scorer | None = None
    ) -> None:
        """Create the scorer from a loaded booster."""
        self._booster = booster
        self._baseline = baseline or WeightedScorer(DEFAULT_WEIGHTS)
        self.manifest = manifest
        self.version = manifest.model_version
        self.n_features = int(booster.num_feature())

    @classmethod
    def from_directory(cls, directory: Path) -> "LightGBMScorer":
        """Load a verified artifact and build the scorer.

        :param directory: Directory with ``model.txt`` and ``manifest.json``.
        :raises ImportError: If LightGBM is not installed.
        :raises ModelArtifactError: If the artifact is missing, damaged or incompatible.
        :return: The scorer.
        """
        import lightgbm as lgb  # noqa: PLC0415 - loaded lazily so the API starts without it

        artifact = load_artifact(directory)
        try:
            booster = lgb.Booster(model_str=artifact.model_text)
        except lgb.basic.LightGBMError as error:
            raise ModelArtifactError("model file could not be parsed") from error
        if booster.num_feature() != len(FEATURE_NAMES):
            raise ModelArtifactError("model has another number of features")
        return cls(booster, artifact.manifest)

    def raw_scores(self, matrix: _Float) -> _Float:
        """Return the raw model scores of feature rows.

        :param matrix: Feature matrix with the columns of FEATURE_NAMES.
        :raises ValueError: If the number of columns is not the number of features.
        :return: One raw score per row.
        """
        self._check(matrix)
        if len(matrix) == 0:
            return np.zeros(0)
        return np.asarray(
            self._booster.predict(matrix, raw_score=True, num_threads=1), dtype=np.float64
        )

    def contributions(self, matrix: _Float) -> _Float:
        """Return the TreeSHAP contributions of feature rows.

        :param matrix: Feature matrix with the columns of FEATURE_NAMES.
        :raises ValueError: If the number of columns is not the number of features.
        :return: Array of shape (rows, features + 1); the last column is the bias, and each
            row adds up to the raw score of that row.
        """
        self._check(matrix)
        if len(matrix) == 0:
            return np.zeros((0, self.n_features + 1))
        return np.asarray(
            self._booster.predict(matrix, pred_contrib=True, num_threads=1), dtype=np.float64
        )

    def criterion_influences(
        self, viewer: ProfileView, candidates: Sequence[Candidate]
    ) -> list[CriterionInfluence]:
        """Return the qualitative effect of every criterion on every candidate.

        The contributions of the features of a criterion are summed and centred over the
        viewer's list, so "raises" means "more than the average candidate of this list".

        :param viewer: The viewer.
        :param candidates: Candidates of the list.
        :return: One entry per candidate, in the order given.
        """
        if not candidates:
            return []
        matrix = feature_matrix(viewer, candidates)
        return self._influences(matrix)

    def score(self, viewer: ProfileView, candidates: Sequence[Candidate]) -> list[Scored]:
        """Score every candidate for the viewer, in the order given.

        ``Scored.score`` carries the raw rank score of the model. It is not calibrated, has
        no fixed range and may be negative: it only orders candidates of one list, and it
        must not be shown as a percentage or compared across lists. The breakdown is the
        baseline breakdown, and ``rank_influence`` maps every criterion to the coarse effect
        of its features on the candidate's position relative to the list average.

        :param viewer: The viewer.
        :param candidates: Candidates to score.
        :return: One result per candidate, in the same order.
        """
        if not candidates:
            return []
        baseline = self._baseline.score(viewer, candidates)
        matrix = feature_matrix(viewer, candidates)
        influences = self._influences(matrix)
        raw = self.raw_scores(matrix)
        return [
            Scored(
                candidate=item.candidate,
                score=float(raw[index]),
                breakdown=item.breakdown,
                rank_influence=influences[index].as_mapping(),
            )
            for index, item in enumerate(baseline)
        ]

    def keeps(self, scored: Scored) -> bool:
        """Keep every candidate: a raw learned score is relative and may be negative.

        Eligibility (visible, not the viewer, a shared sport) is decided before scoring, so
        the sign of the score carries no meaning here.

        :param scored: A result of this scorer.
        :return: Always True.
        """
        return True

    def _check(self, matrix: _Float) -> None:
        """Raise unless the matrix has one column per model feature."""
        if matrix.ndim != 2 or matrix.shape[1] != self.n_features:
            raise ValueError("feature matrix does not match the model")

    def _influences(self, matrix: _Float) -> list[CriterionInfluence]:
        """Per-criterion influence of every row of a non-empty matrix."""
        contributions = self.contributions(matrix)[:, :-1]
        raw = self.raw_scores(matrix)
        spread = float(np.std(raw))
        columns = {name: index for index, name in enumerate(FEATURE_NAMES)}
        per_criterion = {
            criterion: _classify(
                _centred(contributions[:, [columns[name] for name in names]].sum(axis=1)), spread
            )
            for criterion, names in CRITERION_FEATURES.items()
        }
        return [
            CriterionInfluence(
                sport=per_criterion["sport"][i],
                distance=per_criterion["distance"][i],
                intensity=per_criterion["intensity"][i],
                functional=per_criterion["functional"][i],
            )
            for i in range(len(matrix))
        ]
