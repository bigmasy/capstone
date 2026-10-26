import pytest

from app.db import get_db
from app.main import app
from app.models import Profile
from app.privacy import fuzz_location
from app.schemas import MAX_CAPABILITIES, MAX_SPORTS
from tests.test_api import payload

LAT, LON = 50.4501, 30.5234
COORD_MARKERS = ("50.4501", "30.5234", "latitude", "longitude", "area_lat", "area_lon")


def assert_no_coordinates(text):
    for marker in COORD_MARKERS:
        assert marker not in text, marker


def without(body, key):
    return {k: v for k, v in body.items() if k != key}


def test_validation_error_for_missing_name_does_not_echo_input(client):
    r = client.post("/api/v1/profiles", json=without(payload(), "displayName"))
    assert r.status_code == 422
    assert_no_coordinates(r.text)
    for item in r.json()["detail"]:
        assert set(item) == {"type", "loc", "msg"}


def test_validation_error_for_out_of_range_latitude_does_not_echo_value(client):
    body = payload()
    body["location"]["latitude"] = 91.5
    r = client.post("/api/v1/profiles", json=body)
    assert r.status_code == 422
    assert "91.5" not in r.text
    assert "50.4501" not in r.text and "30.5234" not in r.text
    for item in r.json()["detail"]:
        assert set(item) == {"type", "loc", "msg"}


def test_validation_error_for_invalid_intensity_does_not_echo_input(client):
    r = client.post("/api/v1/profiles", json=payload(intensity=9))
    assert r.status_code == 422
    assert_no_coordinates(r.text)
    for item in r.json()["detail"]:
        assert set(item) == {"type", "loc", "msg"}


def test_validation_error_for_malformed_json_does_not_echo_input(client):
    r = client.post(
        "/api/v1/profiles",
        content='{"location": {"latitude": 50.4501, "longitude": 30.5234},',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert_no_coordinates(r.text)


def test_profile_and_matches_responses_have_no_coordinates(client):
    me = client.post("/api/v1/profiles", json=payload("Me")).json()["id"]
    client.post("/api/v1/profiles", json=payload("Nearby", lat=50.452, lon=30.526))
    profile = client.get(f"/api/v1/profiles/{me}")
    matches = client.get(f"/api/v1/profiles/{me}/matches")
    assert profile.status_code == matches.status_code == 200
    assert len(matches.json()) == 1
    assert_no_coordinates(profile.text)
    assert_no_coordinates(matches.text)
    assert "50.452" not in matches.text and "30.526" not in matches.text


def test_stored_location_is_cell_center_not_input(client):
    pid = client.post("/api/v1/profiles", json=payload()).json()["id"]
    session_factory = app.dependency_overrides[get_db]()
    db = next(session_factory)
    try:
        stored = db.get(Profile, pid)
        assert (stored.area_lat, stored.area_lon) != (LAT, LON)
        assert (stored.area_lat, stored.area_lon) == fuzz_location(LAT, LON)
    finally:
        session_factory.close()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["location"].update(extra=1),
        lambda b: b["sports"][0].update(extra=1),
        lambda b: b["capabilities"][0].update(extra=1),
    ],
    ids=["location", "sports", "capabilities"],
)
def test_nested_extra_fields_are_rejected(client, mutate):
    body = payload()
    mutate(body)
    r = client.post("/api/v1/profiles", json=body)
    assert r.status_code == 422
    assert_no_coordinates(r.text)


def test_invalid_sport_level_is_rejected(client):
    body = payload()
    body["sports"][0]["level"] = "expert"
    assert client.post("/api/v1/profiles", json=body).status_code == 422


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
def test_valid_sport_levels_are_accepted(client, level):
    body = payload()
    body["sports"][0]["level"] = level
    assert client.post("/api/v1/profiles", json=body).status_code == 201


@pytest.mark.parametrize("intensity,status", [(0, 422), (1, 201), (5, 201), (6, 422)])
def test_intensity_bounds(client, intensity, status):
    assert client.post("/api/v1/profiles", json=payload(intensity=intensity)).status_code == status


@pytest.mark.parametrize("level,status", [(-1, 422), (0, 201), (4, 201), (5, 422)])
def test_capability_level_bounds(client, level, status):
    body = payload()
    body["capabilities"][0]["level"] = level
    assert client.post("/api/v1/profiles", json=body).status_code == status


@pytest.mark.parametrize("name", ["", " ", "   \t "])
def test_blank_display_name_is_rejected(client, name):
    assert client.post("/api/v1/profiles", json=payload(name)).status_code == 422


def test_display_name_is_trimmed(client):
    r = client.post("/api/v1/profiles", json=payload("  Orest  "))
    assert r.status_code == 201
    assert r.json()["displayName"] == "Orest"


@pytest.mark.parametrize("value", ["", " ", "   \t "])
def test_sport_is_stripped_and_blank_sport_is_rejected(client, value):
    r = client.post("/api/v1/profiles", json=payload(sports=[value]))
    assert r.status_code == 422
    r = client.post("/api/v1/profiles", json=payload(sports=["  swimming  "]))
    assert r.status_code == 201
    assert r.json()["sports"][0]["sport"] == "swimming"


def test_sports_and_capabilities_have_upper_bounds(client):
    assert (MAX_SPORTS, MAX_CAPABILITIES) == (10, 20)
    sports = [f"sport{i}" for i in range(10)]
    assert client.post("/api/v1/profiles", json=payload(sports=sports)).status_code == 201
    too_many = sports + ["extra"]
    assert client.post("/api/v1/profiles", json=payload(sports=too_many)).status_code == 422

    capability = {"category": "mobility_lower", "level": 1}
    body = payload(capabilities=[capability] * 20)
    assert client.post("/api/v1/profiles", json=body).status_code == 201
    body = payload(capabilities=[capability] * 21)
    assert client.post("/api/v1/profiles", json=body).status_code == 422


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.update(displayName="Ore\x00st"),
        lambda b: b.update(district="Shev\x00chenkivskyi"),
        lambda b: b["sports"][0].update(sport="swim\x00ming"),
        lambda b: b["capabilities"][0].update(category="mobility\x00_lower"),
        lambda b: b["capabilities"][0].update(equipment="wheel\x00chair"),
    ],
    ids=["displayName", "district", "sport", "category", "equipment"],
)
def test_nul_character_is_rejected(client, mutate):
    body = payload()
    mutate(body)
    r = client.post("/api/v1/profiles", json=body)
    assert r.status_code == 422
    assert_no_coordinates(r.text)


@pytest.mark.parametrize("field", ["district", "equipment"])
def test_blank_optional_text_is_rejected_when_present(client, field):
    body = payload()
    if field == "district":
        body["district"] = "   "
    else:
        body["capabilities"][0]["equipment"] = "   "
    assert client.post("/api/v1/profiles", json=body).status_code == 422


def test_category_is_stripped_and_blank_category_is_rejected(client):
    body = payload()
    body["capabilities"][0]["category"] = "  mobility_lower  "
    r = client.post("/api/v1/profiles", json=body)
    assert r.status_code == 201
    assert r.json()["capabilities"][0]["category"] == "mobility_lower"
    body["capabilities"][0]["category"] = "   "
    assert client.post("/api/v1/profiles", json=body).status_code == 422
