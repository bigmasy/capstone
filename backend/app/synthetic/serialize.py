"""Canonical JSON form of generated profiles and the digest that pins the generator output.

The form is meant for synthetic populations only. It includes the functional layer because
the experiment needs it, so it must never be applied to real profiles.
"""

import dataclasses
import hashlib
import json
from collections.abc import Sequence
from typing import Any

from app.domain.profile import ProfileView
from app.domain.taxonomy import TAXONOMY_VERSION
from app.synthetic.params import GeneratorParams


def profile_to_dict(profile: ProfileView) -> dict[str, Any]:
    """Return a JSON-ready dict of a profile with sorted sports and capabilities.

    Coordinates are formatted with six decimals so the text does not depend on the float
    repr of the platform.

    :param profile: Synthetic profile.
    :return: Plain dict with strings, ints and lists only.
    """
    return {
        "id": str(profile.id),
        "sports": sorted([e.sport.value, e.skill.value] for e in profile.sports),
        "intensity": profile.intensity,
        "cell": [f"{profile.cell.latitude:.6f}", f"{profile.cell.longitude:.6f}"],
        "district": None if profile.district is None else profile.district.value,
        "visible": profile.is_visible,
        "capabilities": sorted(
            (
                [c.category.value, c.level, None if c.equipment is None else c.equipment.value]
                for c in profile.functional.capabilities
            ),
            key=lambda item: item[0],
        ),
    }


def population_digest(profiles: Sequence[ProfileView]) -> str:
    """Return the sha256 of the canonical JSON of the profiles, in generation order.

    The JSON is the list of profile_to_dict items dumped with sorted keys and without
    spaces. Two runs on any machine or hash seed give the same digest.

    :param profiles: Profiles in generation order.
    :return: Lowercase hex digest.
    """
    text = json.dumps([profile_to_dict(p) for p in profiles], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def population_document(
    params: GeneratorParams, seed: int, profiles: Sequence[ProfileView]
) -> dict[str, Any]:
    """Return the document the command line writes: parameters, seed, digest and profiles.

    :param params: Parameters the population was generated with.
    :param seed: Seed used.
    :param profiles: Generated profiles.
    :return: JSON-ready dict.
    """
    return {
        "taxonomyVersion": TAXONOMY_VERSION,
        "seed": seed,
        "count": len(profiles),
        "params": dataclasses.asdict(params),
        "digest": population_digest(profiles),
        "profiles": [profile_to_dict(p) for p in profiles],
    }
