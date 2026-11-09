"""Model artifact: a directory with the LightGBM text model and a manifest that describes it.

The model is stored as text (``model.txt``), never as a pickle, so loading it cannot run
code. The manifest records what the model was trained on and the sha256 of the text; the
loader refuses an artifact whose hash, feature schema, feature names or taxonomy version do
not match the running code.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.errors import DomainError
from app.domain.matching.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.domain.taxonomy import TAXONOMY_VERSION

MODEL_FILE = "model.txt"
MANIFEST_FILE = "manifest.json"

_TEXT_MODEL_PREFIX = "tree"
_VERSION_PREFIX = "lgbm-"
_VERSION_HASH_CHARS = 12


class ModelArtifactError(DomainError):
    """The model artifact is missing, damaged or incompatible with this code.

    The message names the kind of problem only, never a path or a value from the files.
    """


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """What is known about a trained model.

    :param model_version: Version string reported by the scorer, derived from the hash.
    :param feature_names: Names of the feature columns, in order.
    :param feature_schema_version: Version of the feature schema the model was trained on.
    :param taxonomy_version: Taxonomy version of the training data.
    :param hyperparameters: Training hyperparameters.
    :param seeds: Seeds used for data generation, splits and training.
    :param counts: Numbers of rows, queries and events.
    :param metrics: Validation metrics of the baseline and of the model.
    :param lightgbm_version: Version of LightGBM that wrote the model.
    :param model_sha256: Hex sha256 of the bytes of ``model.txt``.
    """

    model_version: str
    feature_names: tuple[str, ...]
    feature_schema_version: int
    taxonomy_version: str
    hyperparameters: dict[str, Any]
    seeds: dict[str, int]
    counts: dict[str, int]
    metrics: dict[str, dict[str, float]]
    lightgbm_version: str
    model_sha256: str

    def to_json(self) -> str:
        """Return the manifest as stable JSON text (sorted keys, indented).

        :return: JSON text ending with a newline.
        """
        data = {
            "model_version": self.model_version,
            "feature_names": list(self.feature_names),
            "feature_schema_version": self.feature_schema_version,
            "taxonomy_version": self.taxonomy_version,
            "hyperparameters": self.hyperparameters,
            "seeds": self.seeds,
            "counts": self.counts,
            "metrics": self.metrics,
            "lightgbm_version": self.lightgbm_version,
            "model_sha256": self.model_sha256,
        }
        return json.dumps(data, sort_keys=True, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "ArtifactManifest":
        """Parse a manifest, checking the types of its fields.

        :param text: JSON text of a manifest.
        :raises ModelArtifactError: If the text is not a complete, well-typed manifest.
        :return: The manifest.
        """
        try:
            data = json.loads(text)
            names = data["feature_names"]
            if not (isinstance(names, list) and all(isinstance(n, str) for n in names)):
                raise TypeError("feature_names")
            manifest = cls(
                model_version=_text(data["model_version"]),
                feature_names=tuple(names),
                feature_schema_version=_integer(data["feature_schema_version"]),
                taxonomy_version=_text(data["taxonomy_version"]),
                hyperparameters=_mapping(data["hyperparameters"]),
                seeds=_mapping(data["seeds"]),
                counts=_mapping(data["counts"]),
                metrics=_mapping(data["metrics"]),
                lightgbm_version=_text(data["lightgbm_version"]),
                model_sha256=_text(data["model_sha256"]),
            )
        except (ValueError, KeyError, TypeError) as error:
            raise ModelArtifactError("model manifest is damaged") from error
        return manifest


@dataclass(frozen=True, slots=True)
class LoadedArtifact:
    """A verified artifact.

    :param manifest: The manifest.
    :param model_text: The text of the model, whose hash matches the manifest.
    """

    manifest: ArtifactManifest
    model_text: str


def _text(value: object) -> str:
    """Return the value if it is a string, else raise TypeError."""
    if not isinstance(value, str):
        raise TypeError("expected a string")
    return value


def _integer(value: object) -> int:
    """Return the value if it is an int (not a bool), else raise TypeError."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("expected an integer")
    return value


def _mapping(value: object) -> Any:
    """Return the value if it is a dict, else raise TypeError."""
    if not isinstance(value, dict):
        raise TypeError("expected an object")
    return value


def write_artifact(
    directory: Path,
    model_text: str,
    *,
    hyperparameters: dict[str, Any],
    seeds: dict[str, int],
    counts: dict[str, int],
    metrics: dict[str, dict[str, float]],
    lightgbm_version: str,
) -> ArtifactManifest:
    """Write the model and its manifest into a directory, creating it if needed.

    The output is a function of the arguments only (no timestamps, no paths), so the same
    inputs give the same bytes.

    :param directory: Target directory.
    :param model_text: Text of the LightGBM model.
    :param hyperparameters: Training hyperparameters.
    :param seeds: Seeds used.
    :param counts: Numbers of rows, queries and events.
    :param metrics: Validation metrics of the baseline and of the model.
    :param lightgbm_version: Version of LightGBM.
    :return: The manifest that was written.
    """
    sha = hashlib.sha256(model_text.encode("utf-8")).hexdigest()
    manifest = ArtifactManifest(
        model_version=_VERSION_PREFIX + sha[:_VERSION_HASH_CHARS],
        feature_names=FEATURE_NAMES,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        hyperparameters=hyperparameters,
        seeds=seeds,
        counts=counts,
        metrics=metrics,
        lightgbm_version=lightgbm_version,
        model_sha256=sha,
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MODEL_FILE).write_bytes(model_text.encode("utf-8"))
    (directory / MANIFEST_FILE).write_bytes(manifest.to_json().encode("utf-8"))
    return manifest


def load_artifact(
    directory: Path,
    *,
    expected_feature_schema_version: int = FEATURE_SCHEMA_VERSION,
    expected_taxonomy_version: str = TAXONOMY_VERSION,
    expected_feature_names: tuple[str, ...] = FEATURE_NAMES,
) -> LoadedArtifact:
    """Read and verify an artifact.

    :param directory: Directory with ``model.txt`` and ``manifest.json``.
    :param expected_feature_schema_version: Schema version the running code uses.
    :param expected_taxonomy_version: Taxonomy version the running code uses.
    :param expected_feature_names: Feature columns the running code produces.
    :raises ModelArtifactError: If a file is missing or damaged, the hash does not match, the
        file is not a LightGBM text model, or a version or the feature names differ.
    :return: The verified artifact.
    """
    try:
        manifest_text = (directory / MANIFEST_FILE).read_text(encoding="utf-8")
        model_bytes = (directory / MODEL_FILE).read_bytes()
    except (OSError, UnicodeDecodeError) as error:
        raise ModelArtifactError("model artifact is missing or unreadable") from error
    manifest = ArtifactManifest.from_json(manifest_text)
    if hashlib.sha256(model_bytes).hexdigest() != manifest.model_sha256:
        raise ModelArtifactError("model file does not match its manifest")
    if manifest.feature_schema_version != expected_feature_schema_version:
        raise ModelArtifactError("model was trained on another feature schema")
    if manifest.feature_names != expected_feature_names:
        raise ModelArtifactError("model was trained on other features")
    if manifest.taxonomy_version != expected_taxonomy_version:
        raise ModelArtifactError("model was trained on another taxonomy version")
    try:
        model_text = model_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelArtifactError("model file is not a text model") from error
    if not model_text.startswith(_TEXT_MODEL_PREFIX):
        raise ModelArtifactError("model file is not a text model")
    return LoadedArtifact(manifest=manifest, model_text=model_text)
