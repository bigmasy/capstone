"""The committed OpenAPI document must equal what the code generates."""

from pathlib import Path

from app.tools.export_openapi import DEFAULT_OUTPUT, build_spec, render_spec

REGENERATE = "cd backend && python -m app.tools.export_openapi"


def test_committed_openapi_matches_the_generated_one():
    committed_path = Path(DEFAULT_OUTPUT)

    assert committed_path.is_file(), f"{committed_path} is missing; run: {REGENERATE}"
    assert committed_path.read_text(encoding="utf-8") == render_spec(build_spec()), (
        f"docs/api/openapi.json is out of date; run: {REGENERATE}"
    )


def test_every_json_property_name_in_the_contract_is_snake_case():
    import re

    names: set[str] = set()

    def collect(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.update(properties)
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(build_spec()["components"]["schemas"])

    assert names
    assert all(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", name) for name in names), names
