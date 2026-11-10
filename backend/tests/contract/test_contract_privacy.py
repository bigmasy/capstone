"""Walk the generated OpenAPI document: what may appear in a response of a non-owner route."""

from typing import Any

import pytest

from app.tools.export_openapi import build_spec

# Operations whose success response describes the caller's own data.
OWNER_OPERATIONS = {
    ("get", "/api/v1/profiles/me"),
    ("put", "/api/v1/profiles/me"),
    ("get", "/api/v1/auth/me"),
    ("post", "/api/v1/auth/register"),
}
# Invitation routes answer to the two participants. They carry the other party's public profile
# and, after acceptance, its contact, which is why they have their own allowlist below.
INVITATION_OPERATIONS = {
    ("get", "/api/v1/invitations"),
    ("post", "/api/v1/invitations"),
    ("get", "/api/v1/invitations/{invitation_id}"),
    ("post", "/api/v1/invitations/{invitation_id}/accept"),
    ("post", "/api/v1/invitations/{invitation_id}/decline"),
    ("post", "/api/v1/invitations/{invitation_id}/cancel"),
}
# Static code lists: no person's data, checked by a separate test below.
# Public reference data that holds no profile data at all: the code lists and the news digest
REFERENCE_OPERATIONS = {("get", "/api/v1/taxonomy"), ("get", "/api/v1/news")}

# Every property name that a response of any other route may contain.
ALLOWED_PROPERTIES = {
    # public profile
    "id",
    "display_name",
    "district_code",
    "intensity",
    "sports",
    "sport",
    "skill",
    # matching feed (checked more strictly by the tests on MATCH_PROPERTIES)
    "items",
    "skip",
    "limit",
    "total",
    "distance_band",
    "breakdown",
    "distance",
    "functional",
    "rank_source",
    "rank_influence",
    "max_points",
    # login
    "access_token",
    "token_type",
    # probes
    "status",
    # errors
    "detail",
    "loc",
    "msg",
    "type",
}
INVITATION_ALLOWED = ALLOWED_PROPERTIES | {
    "direction",
    "created_at",
    "expires_at",
    "responded_at",
    "sender",
    "recipient",
    "contact",
    # Machine code of the 409 that asks for a contact on the caller's own profile
    "code",
}
DENIED_WORDS = {
    "capabilities",
    "capability",
    "equipment",
    "category",
    "level",
    "latitude",
    "longitude",
    "area",
    "email",
    "password",
    "contact",
}
# Exactly what an item of the matching feed may carry. The learned score, the exact distance,
# the location and any numeric functional contribution are absent by design.
MATCH_PROPERTIES = {
    "items",
    "skip",
    "limit",
    "total",
    "id",
    "display_name",
    "district_code",
    "intensity",
    "sports",
    "sport",
    "skill",
    "distance_band",
    "breakdown",
    "distance",
    "functional",
    "rank_source",
    "rank_influence",
    # Denominators of the shown points; sport, distance and intensity only (checked below)
    "max_points",
}
TAXONOMY_ALLOWED = {
    "version",
    "sports",
    "categories",
    "equipment",
    "code",
    "districts",
    "skills",
    "capability_levels",
    "intensities",
}


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return build_spec()


def resolve(spec: dict[str, Any], node: Any) -> Any:
    """Follow a ``$ref`` to the schema it points at."""
    while isinstance(node, dict) and "$ref" in node:
        target: Any = spec
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def property_names(spec: dict[str, Any], node: Any, seen: set[str] | None = None) -> set[str]:
    """Collect every property name reachable from a schema."""
    seen = seen if seen is not None else set()
    names: set[str] = set()
    if isinstance(node, dict) and "$ref" in node:
        if node["$ref"] in seen:
            return names
        seen.add(node["$ref"])
    node = resolve(spec, node)
    if not isinstance(node, dict):
        return names
    for name, child in node.get("properties", {}).items():
        names.add(name)
        names |= property_names(spec, child, seen)
    for key in ("items", "additionalProperties"):
        if isinstance(node.get(key), dict):
            names |= property_names(spec, node[key], seen)
    for key in ("anyOf", "allOf", "oneOf", "prefixItems"):
        for child in node.get(key, []):
            names |= property_names(spec, child, seen)
    return names


def operations(spec: dict[str, Any]):
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            yield method, path, operation


def response_properties(
    spec: dict[str, Any], operation: dict[str, Any], *, errors_only: bool
) -> set[str]:
    names: set[str] = set()
    for code, response in operation["responses"].items():
        if errors_only and code.startswith("2"):
            continue
        for content in response.get("content", {}).values():
            names |= property_names(spec, content.get("schema", {}))
    return names


def is_denied(name: str) -> bool:
    return bool(DENIED_WORDS & set(name.lower().split("_")))


def test_non_owner_responses_use_only_allowlisted_properties(spec: dict[str, Any]):
    checked = 0
    for method, path, operation in operations(spec):
        key = (method, path)
        if key in REFERENCE_OPERATIONS or key in INVITATION_OPERATIONS:
            continue
        names = response_properties(spec, operation, errors_only=key in OWNER_OPERATIONS)
        checked += 1
        assert names <= ALLOWED_PROPERTIES, (key, sorted(names - ALLOWED_PROPERTIES))
        assert not [n for n in names if is_denied(n)], (key, names)

    assert checked >= 8


def test_the_public_profile_route_is_among_the_checked_ones(spec: dict[str, Any]):
    operation = spec["paths"]["/api/v1/profiles/{profile_id}"]["get"]

    names = response_properties(spec, operation, errors_only=False)

    assert {"id", "display_name", "district_code", "intensity", "sports"} <= names


def test_invitation_responses_use_only_their_own_allowlist(spec: dict[str, Any]):
    for method, path in INVITATION_OPERATIONS:
        operation = spec["paths"][path][method]
        names = response_properties(spec, operation, errors_only=False)

        assert names <= INVITATION_ALLOWED, (method, path, sorted(names - INVITATION_ALLOWED))
        # Contact is the only denied word that may appear, and only through the partner
        assert not [n for n in names if is_denied(n) and n != "contact"], (method, path)


def test_the_invitation_routes_are_all_listed_here(spec: dict[str, Any]):
    documented = {
        (method, path)
        for path, item in spec["paths"].items()
        if path.startswith("/api/v1/invitations")
        for method in item
    }

    assert documented == INVITATION_OPERATIONS


def test_contact_appears_only_inside_the_partner_of_an_invitation(spec: dict[str, Any]):
    schemas = spec["components"]["schemas"]

    holders = {
        name for name, schema in schemas.items() if "contact" in schema.get("properties", {})
    }

    # The invitation itself never carries a contact: the other party's profile does, and the
    # server fills it only for an accepted invitation. The owner view and the profile body have
    # their own contact.
    assert holders == {"InvitationPartner", "ProfileOwner", "ProfilePut"}
    for name in ("InvitationIncoming", "InvitationOutgoing"):
        assert "contact" not in schemas[name]["properties"]


def test_the_contact_required_error_documents_its_code_on_exactly_two_operations(
    spec: dict[str, Any],
):
    carriers = set()
    for method, path, operation in operations(spec):
        conflict = operation["responses"].get("409", {})
        schema = conflict.get("content", {}).get("application/json", {}).get("schema", {})
        if "code" in property_names(spec, schema):
            carriers.add((method, path))

    assert carriers == {
        ("post", "/api/v1/invitations"),
        ("post", "/api/v1/invitations/{invitation_id}/accept"),
    }
    code = spec["components"]["schemas"]["ContactRequiredResponse"]["properties"]["code"]
    assert code["const"] == "contact_required"


def test_invitation_responses_have_no_location_or_functional_fields(spec: dict[str, Any]):
    banned = {"latitude", "longitude", "area_lat", "area_lon", "cell", "area_center", "email"}
    for method, path in INVITATION_OPERATIONS:
        names = response_properties(spec, spec["paths"][path][method], errors_only=False)

        assert not banned & names, (method, path)
        assert not {"capabilities", "equipment", "category", "level"} & names, (method, path)


def test_the_invitation_request_forbids_extra_properties_and_carries_no_free_text(
    spec: dict[str, Any],
):
    schema = spec["components"]["schemas"]["InvitationCreate"]

    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"recipient_profile_id"}


def test_no_invitation_schema_has_a_free_text_field(spec: dict[str, Any]):
    for name, schema in spec["components"]["schemas"].items():
        if name.startswith("Invitation"):
            assert "message" not in schema.get("properties", {}), name


def test_owner_responses_still_have_no_location(spec: dict[str, Any]):
    for method, path in OWNER_OPERATIONS:
        names = response_properties(spec, spec["paths"][path][method], errors_only=False)
        banned = {"latitude", "longitude", "area_lat", "area_lon", "cell", "area_center"}
        assert not banned & names, (method, path)
        assert "password" not in names and "password_hash" not in names


def test_taxonomy_holds_code_lists_only(spec: dict[str, Any]):
    operation = spec["paths"]["/api/v1/taxonomy"]["get"]

    names = response_properties(spec, operation, errors_only=False)

    assert names <= TAXONOMY_ALLOWED
    assert not {"name", "label", "description", "email", "latitude"} & names


def test_news_digest_holds_links_titles_and_names_only(spec: dict[str, Any]):
    operation = spec["paths"]["/api/v1/news"]["get"]

    names = response_properties(spec, operation, errors_only=False)

    assert {"columns", "id", "items", "title", "url", "source", "published_at"} >= names - {
        "detail",
        "loc",
        "msg",
        "type",
    }
    assert not {"email", "contact", "latitude", "user_id", "token"} & names


def test_request_schemas_of_the_profile_route_forbid_extra_properties(spec: dict[str, Any]):
    for name in ("ProfilePut", "SportItem", "CapabilityItem", "RegisterRequest", "LoginRequest"):
        assert spec["components"]["schemas"][name]["additionalProperties"] is False, name


def test_the_walker_detects_a_leak():
    leaky = {"components": {"schemas": {"Leak": {"properties": {"latitude": {}, "id": {}}}}}}

    names = property_names(leaky, {"$ref": "#/components/schemas/Leak"})

    assert names == {"latitude", "id"}
    assert (
        is_denied("area_lat")
        and is_denied("latitude")
        and is_denied("owner_email")
        and is_denied("skill_level")
    )


def test_the_matching_feed_exposes_exactly_the_documented_properties(spec: dict[str, Any]):
    operation = spec["paths"]["/api/v1/matches"]["get"]

    names = response_properties(spec, operation, errors_only=False)

    assert names - {"detail", "loc", "msg", "type"} == MATCH_PROPERTIES
    assert not {"score", "raw_score", "distance_km", "contribution", "points"} & names


def test_the_functional_criterion_of_a_match_is_a_level_and_never_a_number(spec: dict[str, Any]):
    schemas = spec["components"]["schemas"]

    functional = resolve(spec, schemas["MatchBreakdown"]["properties"]["functional"])
    influence = resolve(spec, schemas["MatchRankInfluence"]["properties"]["functional"])

    assert functional["enum"] == ["low", "medium", "high"]
    assert influence["enum"] == ["raises", "neutral", "lowers"]
    for other in ("sport", "distance", "intensity", "total"):
        assert schemas["MatchBreakdown"]["properties"][other]["type"] == "number"


def test_only_the_maxima_of_the_shown_criteria_are_exposed_as_numbers(spec: dict[str, Any]):
    schemas = spec["components"]["schemas"]

    maxima = schemas["MatchMaxPoints"]["properties"]
    feed = schemas["MatchFeed"]["properties"]

    # No maximum for the functional criterion: it is a level and must not become a number
    assert set(maxima) == {"sport", "distance", "intensity"}
    assert all(resolve(spec, node)["type"] == "integer" for node in maxima.values())
    assert resolve(spec, feed["max_points"]) == schemas["MatchMaxPoints"]


def test_the_rank_source_and_the_distance_band_are_closed_label_sets(spec: dict[str, Any]):
    schemas = spec["components"]["schemas"]

    assert resolve(spec, schemas["MatchItem"]["properties"]["rank_source"])["enum"] == [
        "baseline",
        "learned",
    ]
    assert len(resolve(spec, schemas["MatchItem"]["properties"]["distance_band"])["enum"]) == 4


def test_the_matching_query_is_bounded(spec: dict[str, Any]):
    parameters = {p["name"]: p for p in spec["paths"]["/api/v1/matches"]["get"]["parameters"]}

    limit = parameters["limit"]["schema"]
    assert limit["maximum"] == 50 and limit["minimum"] == 1
    assert parameters["skip"]["schema"]["minimum"] == 0
    assert set(parameters) == {"skip", "limit", "radius_km", "sport"}


def test_the_profile_request_makes_the_location_optional_but_keeps_its_ranges(
    spec: dict[str, Any],
):
    schema = spec["components"]["schemas"]["ProfilePut"]

    assert not {"latitude", "longitude"} & set(schema["required"])
    assert schema["additionalProperties"] is False
    for name, bound in (("latitude", 90), ("longitude", 180)):
        field = schema["properties"][name]
        branches = [branch for branch in field["anyOf"] if branch.get("type") == "number"]
        assert [(b["minimum"], b["maximum"]) for b in branches] == [(-bound, bound)], name
        assert {"type": "null"} in field["anyOf"], name
        # The rule is documented in the contract itself, not only in the code
        assert "omit both" in field["description"], name
        assert "never returned" in field["description"], name


def test_the_location_stays_input_only(spec: dict[str, Any]):
    schemas = spec["components"]["schemas"]
    holders = {
        name
        for name, schema in schemas.items()
        if {"latitude", "longitude"} & set(schema.get("properties", {}))
    }

    assert holders == {"ProfilePut"}
