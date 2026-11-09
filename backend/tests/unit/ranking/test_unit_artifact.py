import hashlib
import json

import pytest

from app.domain.errors import DomainError
from app.domain.matching.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.domain.taxonomy import TAXONOMY_VERSION
from app.ranking.artifact import (
    MANIFEST_FILE,
    MODEL_FILE,
    ModelArtifactError,
    load_artifact,
    write_artifact,
)

MODEL_TEXT = "tree\nversion=v4\nnum_class=1\nend of trees\n"


def _write(directory, **overrides):
    values = {
        "hyperparameters": {"num_leaves": 7, "learning_rate": 0.1},
        "seeds": {"train": 3},
        "counts": {"rows": 10, "queries": 2, "events": 10},
        "metrics": {"baseline": {"ndcg@10": 0.5}, "model": {"ndcg@10": 0.6}},
        "lightgbm_version": "4.6.0",
    }
    values.update(overrides)
    return write_artifact(directory, MODEL_TEXT, **values)


def _rewrite_manifest(directory, **changes):
    path = directory / MANIFEST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_round_trip_keeps_the_model_and_the_manifest(tmp_path):
    manifest = _write(tmp_path)

    loaded = load_artifact(tmp_path)

    assert loaded.model_text == MODEL_TEXT
    assert loaded.manifest == manifest
    assert manifest.feature_names == FEATURE_NAMES
    assert manifest.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert manifest.taxonomy_version == TAXONOMY_VERSION
    assert manifest.model_sha256 == hashlib.sha256(MODEL_TEXT.encode()).hexdigest()
    assert manifest.model_version.startswith("lgbm-")
    assert manifest.counts == {"rows": 10, "queries": 2, "events": 10}
    assert manifest.metrics["model"]["ndcg@10"] == 0.6


def test_written_files_are_text_and_contain_no_local_paths(tmp_path):
    _write(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([MODEL_FILE, MANIFEST_FILE])
    assert (tmp_path / MODEL_FILE).read_text(encoding="utf-8") == MODEL_TEXT
    assert str(tmp_path) not in (tmp_path / MANIFEST_FILE).read_text(encoding="utf-8")


def test_writing_twice_gives_identical_bytes(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    _write(first)
    _write(second)

    for name in (MODEL_FILE, MANIFEST_FILE):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_tampered_model_is_rejected(tmp_path):
    _write(tmp_path)
    (tmp_path / MODEL_FILE).write_text(MODEL_TEXT + "x", encoding="utf-8")

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_tampered_hash_is_rejected(tmp_path):
    _write(tmp_path)
    _rewrite_manifest(tmp_path, model_sha256="0" * 64)

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


@pytest.mark.parametrize(
    "changes",
    [
        {"feature_schema_version": FEATURE_SCHEMA_VERSION + 1},
        {"taxonomy_version": "9.9.9"},
        {"feature_names": list(reversed(FEATURE_NAMES))},
        {"feature_names": list(FEATURE_NAMES[:-1])},
    ],
)
def test_version_and_schema_mismatches_are_rejected(tmp_path, changes):
    _write(tmp_path)
    _rewrite_manifest(tmp_path, **changes)

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_explicit_expectations_override_the_defaults(tmp_path):
    _write(tmp_path)

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path, expected_taxonomy_version="2.0.0")
    assert load_artifact(tmp_path, expected_taxonomy_version=TAXONOMY_VERSION).model_text


@pytest.mark.parametrize("missing", [MODEL_FILE, MANIFEST_FILE])
def test_missing_files_are_rejected(tmp_path, missing):
    _write(tmp_path)
    (tmp_path / missing).unlink()

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_missing_directory_is_rejected(tmp_path):
    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path / "nope")


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"model_sha256": 5}', "{}"])
def test_corrupt_manifest_is_rejected(tmp_path, content):
    _write(tmp_path)
    (tmp_path / MANIFEST_FILE).write_text(content, encoding="utf-8")

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_a_binary_blob_with_a_matching_hash_is_still_rejected(tmp_path):
    # Whatever sits in model.txt is never unpickled; anything that is not a LightGBM text
    # model is refused even when the manifest was regenerated for it
    blob = b"\x80\x04\x95pickle"
    _write(tmp_path)
    (tmp_path / MODEL_FILE).write_bytes(blob)
    _rewrite_manifest(tmp_path, model_sha256=hashlib.sha256(blob).hexdigest())

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_a_text_file_that_is_not_a_model_is_rejected(tmp_path):
    text = "hello"
    _write(tmp_path)
    (tmp_path / MODEL_FILE).write_text(text, encoding="utf-8")
    _rewrite_manifest(tmp_path, model_sha256=hashlib.sha256(text.encode()).hexdigest())

    with pytest.raises(ModelArtifactError):
        load_artifact(tmp_path)


def test_the_error_is_a_domain_error_with_a_generic_message(tmp_path):
    with pytest.raises(DomainError) as info:
        load_artifact(tmp_path / "secret-location")

    assert "secret-location" not in info.value.message
