"""Helpers shared by the experiment runners: library versions and JSON output."""

import json
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from app.domain.matching.features import FEATURE_SCHEMA_VERSION
from app.domain.taxonomy import TAXONOMY_VERSION


def _version(package: str) -> str | None:
    """Installed version of a package, or None if it is not installed."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def library_versions() -> dict[str, Any]:
    """Return the versions that identify the environment of a run.

    :return: Python, platform, library, taxonomy and feature schema versions.
    """
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": _version("numpy"),
        "scipy": _version("scipy"),
        "lightgbm": _version("lightgbm"),
        "scikit-learn": _version("scikit-learn"),
        "taxonomy": TAXONOMY_VERSION,
        "feature_schema": FEATURE_SCHEMA_VERSION,
    }


def dump_json(data: dict[str, Any]) -> str:
    """Serialise a result as stable, human-readable JSON.

    :param data: JSON-ready result.
    :return: Text with sorted keys, ending with a newline.
    """
    return json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"


def write_result(data: dict[str, Any], out: str | None) -> None:
    """Write a result to a file, or to standard output when no path is given.

    :param data: JSON-ready result.
    :param out: Target path or None.
    """
    text = dump_json(data)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
