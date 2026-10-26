def payload(name="Orest", sports=("swimming",), lat=50.4501, lon=30.5234, intensity=3, **extra):
    body = {
        "displayName": name,
        "district": "Shevchenkivskyi",
        "location": {"latitude": lat, "longitude": lon},
        "intensity": intensity,
        "sports": [{"sport": s} for s in sports],
        "capabilities": [{"category": "mobility_lower", "level": 2, "equipment": "wheelchair_active"}],
    }
    body.update(extra)
    return body


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_profile_returns_private_view_without_exact_coordinates(client):
    r = client.post("/api/v1/profiles", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["capabilities"][0]["category"] == "mobility_lower"
    text = r.text
    assert "50.4501" not in text and "30.5234" not in text
    assert "latitude" not in text and "area_lat" not in text


def test_public_profile_has_no_private_fields(client):
    pid = client.post("/api/v1/profiles", json=payload()).json()["id"]
    r = client.get(f"/api/v1/profiles/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "displayName", "district", "intensity", "sports"}
    assert "mobility_lower" not in r.text and "wheelchair" not in r.text


def test_unknown_profile_is_404(client):
    assert client.get("/api/v1/profiles/unknown").status_code == 404
    assert client.get("/api/v1/profiles/unknown/matches").status_code == 404


def test_extra_fields_are_rejected(client):
    r = client.post("/api/v1/profiles", json=payload(id="custom-id"))
    assert r.status_code == 422


def test_invalid_intensity_is_rejected(client):
    assert client.post("/api/v1/profiles", json=payload(intensity=9)).status_code == 422


def test_matches_sorted_and_expose_distance_band_only(client):
    me = client.post("/api/v1/profiles", json=payload("Me")).json()["id"]
    client.post("/api/v1/profiles", json=payload("Nearby", lat=50.452, lon=30.526))
    client.post("/api/v1/profiles", json=payload("Far", lat=50.60, lon=30.80, intensity=5))
    client.post("/api/v1/profiles", json=payload("Other sport", sports=("archery",)))
    client.post("/api/v1/profiles", json=payload("Hidden", isVisible=False))
    r = client.get(f"/api/v1/profiles/{me}/matches")
    assert r.status_code == 200
    items = r.json()
    names = [i["profile"]["displayName"] for i in items]
    assert names[0] == "Nearby"
    assert "Me" not in names and "Other sport" not in names and "Hidden" not in names
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert all(i["distance"] in {"under 5 km", "5–10 km", "10–25 km", "over 25 km"} for i in items)
    assert "mobility_lower" not in r.text


def test_limit_is_bounded(client):
    me = client.post("/api/v1/profiles", json=payload()).json()["id"]
    assert client.get(f"/api/v1/profiles/{me}/matches?limit=0").status_code == 422
    assert client.get(f"/api/v1/profiles/{me}/matches?limit=1000").status_code == 422


def test_hidden_owner_gets_matches_but_is_not_listed_for_others(client):
    hidden = client.post("/api/v1/profiles", json=payload("Hidden", isVisible=False)).json()["id"]
    other = client.post("/api/v1/profiles", json=payload("Visible")).json()["id"]
    own = client.get(f"/api/v1/profiles/{hidden}/matches")
    assert own.status_code == 200
    assert [i["profile"]["displayName"] for i in own.json()] == ["Visible"]
    theirs = client.get(f"/api/v1/profiles/{other}/matches")
    assert theirs.json() == []
