"""HTTP tests of GET /api/v1/matches on SQLite with the weighted baseline."""

from typing import Any

import httpx

from tests.integration.helpers import Actor, make_profile_body, sign_up, sign_up_with_profile

URL = "/api/v1/matches"
VISION = {"category": "vision", "level": 4}
HEARING = {"category": "hearing", "level": 4}
ENDURANCE = {"category": "endurance", "level": 4}
ITEM_KEYS = {
    "id",
    "display_name",
    "district_code",
    "intensity",
    "sports",
    "distance_band",
    "breakdown",
    "rank_source",
    "rank_influence",
}
BREAKDOWN_KEYS = {"sport", "distance", "intensity", "functional", "total"}


async def add(client: httpx.AsyncClient, **overrides: Any) -> tuple[Actor, dict[str, Any]]:
    """Register a user with a profile; defaults put everybody in the same grid cell."""
    return await sign_up_with_profile(client, **overrides)


async def feed(client: httpx.AsyncClient, actor: Actor, **params: Any) -> httpx.Response:
    return await client.get(URL, params=params, headers=actor.headers)


async def test_the_feed_requires_a_token(client: httpx.AsyncClient):
    anonymous = await client.get(URL)
    forged = await client.get(URL, headers={"Authorization": "Bearer not.a.token"})

    assert anonymous.status_code == forged.status_code == 401
    assert anonymous.headers["www-authenticate"] == "Bearer"


async def test_a_caller_without_a_profile_gets_404(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await feed(client, actor)

    assert response.status_code == 404
    assert response.json() == {"detail": "Profile not found"}


async def test_an_empty_feed_is_a_valid_page(client: httpx.AsyncClient):
    me, _ = await add(client)

    response = await feed(client, me)

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "skip": 0,
        "limit": 20,
        "total": 0,
        "max_points": {"sport": 30, "distance": 30, "intensity": 15},
    }


async def test_the_feed_lists_visible_partners_best_first_with_the_breakdown(
    client: httpx.AsyncClient,
):
    me, _ = await add(client, intensity=3)
    close, close_profile = await add(client, display_name="Close", intensity=3)
    apart, _ = await add(client, display_name="Apart", intensity=1, latitude=50.60)
    _, hidden = await add(client, display_name="Hidden", is_visible=False)
    _, unrelated = await add(client, sports=[{"sport": "archery", "skill": "beginner"}])

    response = await feed(client, me)

    assert response.status_code == 200
    body = response.json()
    assert [item["display_name"] for item in body["items"]] == ["Close", "Apart"]
    assert body["total"] == 2
    ids = {item["id"] for item in body["items"]}
    assert hidden["id"] not in ids and unrelated["id"] not in ids
    first, second = body["items"]
    assert set(first) == ITEM_KEYS
    assert set(first["breakdown"]) == BREAKDOWN_KEYS
    assert first["id"] == close_profile["id"]
    assert first["rank_source"] == "baseline" and first["rank_influence"] is None
    assert first["breakdown"]["total"] > second["breakdown"]["total"]
    assert first["distance_band"] == "under 5 km" and second["distance_band"] == "10–25 km"
    assert first["sports"] == [{"sport": "swimming", "skill": "intermediate"}]
    assert first["district_code"] == "kyiv_podilskyi"
    assert apart.user_id not in response.text


async def test_the_breakdown_adds_up_in_tenths_and_the_functional_part_is_a_level(
    client: httpx.AsyncClient,
):
    me, _ = await add(client, intensity=3, capabilities=[VISION, HEARING])
    await add(client, intensity=4, capabilities=[VISION, HEARING])

    [item] = (await feed(client, me)).json()["items"]

    breakdown = item["breakdown"]
    assert breakdown["functional"] == "high"
    # Same cell, one shared sport of one: 30 + 30 + 25 (functional, high) and 15 * (1 - 1/4) =
    # 11.25 rounded to tenths half to even, as the baseline always does
    assert breakdown["sport"] == 30.0 and breakdown["distance"] == 30.0
    assert breakdown["intensity"] == 11.2
    assert breakdown["total"] == 96.2
    assert isinstance(breakdown["functional"], str)


async def test_the_response_never_carries_location_distance_or_capabilities(
    client: httpx.AsyncClient,
):
    me, _ = await add(client, capabilities=[VISION, HEARING])
    await add(
        client,
        latitude=50.4711,
        longitude=30.5612,
        contact="t.me/secret-contact",
        capabilities=[
            VISION,
            {"category": "hearing", "level": 2, "equipment": "hearing_aid"},
        ],
    )

    response = await feed(client, me)

    text = response.text
    for forbidden in (
        "50.4711",
        "30.5612",
        "50.47",
        "30.56",
        "latitude",
        "longitude",
        "distance_km",
        "contact",
        "secret-contact",
        "capabilities",
        "equipment",
        "hearing_aid",
        "vision",
        "hearing",
        "email",
        "@example.org",
    ):
        assert forbidden not in text, forbidden


async def test_a_single_shared_category_does_not_reveal_the_candidates_level(
    client: httpx.AsyncClient,
):
    me, _ = await add(client, capabilities=[VISION, HEARING])
    # One shared category, the candidate far from the viewer's abilities in it
    await add(
        client, display_name="Probe", capabilities=[{"category": "vision", "level": 0}, ENDURANCE]
    )
    # Two shared categories: the real level may be shown
    await add(client, display_name="Match", capabilities=[VISION, HEARING])

    items = {i["display_name"]: i for i in (await feed(client, me)).json()["items"]}

    assert items["Probe"]["breakdown"]["functional"] == "medium"
    assert items["Match"]["breakdown"]["functional"] == "high"


async def test_withdrawn_consent_removes_a_candidates_functional_data_from_matching(
    client: httpx.AsyncClient,
):
    me, _ = await add(client, capabilities=[VISION, HEARING])
    other, _ = await add(client, display_name="Other", capabilities=[VISION, HEARING])
    before = (await feed(client, me)).json()["items"][0]["breakdown"]["functional"]

    await client.put(
        "/api/v1/profiles/me",
        json=make_profile_body(display_name="Other", functional_data_consent=False),
        headers=other.headers,
    )
    after = (await feed(client, me)).json()["items"][0]["breakdown"]["functional"]

    assert (before, after) == ("high", "medium")


async def test_pagination_walks_one_ordering(client: httpx.AsyncClient):
    me, _ = await add(client)
    for number in range(7):
        await add(client, display_name=f"P{number}", latitude=50.45 + 0.04 * number)

    everything = (await feed(client, me, limit=50)).json()
    first = (await feed(client, me, limit=3)).json()
    second = (await feed(client, me, skip=3, limit=3)).json()
    third = (await feed(client, me, skip=6, limit=3)).json()
    beyond = (await feed(client, me, skip=30, limit=3)).json()

    walked = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert walked == [i["id"] for i in everything["items"]]
    assert [len(p["items"]) for p in (first, second, third, beyond)] == [3, 3, 1, 0]
    assert {p["total"] for p in (first, second, third, beyond)} == {7}
    assert (second["skip"], second["limit"]) == (3, 3)


async def test_out_of_range_paging_is_a_sanitised_422(client: httpx.AsyncClient):
    me, _ = await add(client)

    for params in ({"limit": 51}, {"limit": 0}, {"skip": -1}, {"limit": "many"}):
        response = await feed(client, me, **params)
        assert response.status_code == 422, params
        for error in response.json()["detail"]:
            assert set(error) == {"type", "loc", "msg"}


async def test_the_radius_can_only_narrow_the_search_to_a_distance_band(
    client: httpx.AsyncClient,
):
    me, _ = await add(client)
    await add(client, display_name="Near")
    await add(client, display_name="Mid", latitude=50.53)  # about 9 km north
    await add(client, display_name="Far", latitude=50.60)  # about 17 km north

    def names(response: httpx.Response) -> list[str]:
        return [i["display_name"] for i in response.json()["items"]]

    assert names(await feed(client, me, radius_km=5)) == ["Near"]
    assert names(await feed(client, me, radius_km=10)) == ["Near", "Mid"]
    assert names(await feed(client, me, radius_km=25)) == ["Near", "Mid", "Far"]
    assert names(await feed(client, me)) == ["Near", "Mid", "Far"]
    for bad in (7, 0, -5, 100, "x"):
        assert (await feed(client, me, radius_km=bad)).status_code == 422, bad


async def test_the_sport_filter_and_unknown_sports(client: httpx.AsyncClient):
    both = [
        {"sport": "swimming", "skill": "beginner"},
        {"sport": "archery", "skill": "beginner"},
    ]
    me, _ = await add(client, sports=both)
    await add(client, display_name="Swimmer")
    await add(client, display_name="Archer", sports=[both[1]])

    archers = (await feed(client, me, sport="archery")).json()["items"]
    unknown = await feed(client, me, sport="quidditch")

    assert [i["display_name"] for i in archers] == ["Archer"]
    assert unknown.status_code == 422


async def test_every_caller_gets_a_feed_of_their_own_and_a_profile_id_cannot_be_chosen(
    client: httpx.AsyncClient,
):
    alice, alice_profile = await add(client, display_name="Alice")
    bob, bob_profile = await add(client, display_name="Bob")
    carol, carol_profile = await add(client, display_name="Carol")

    for_alice = await feed(client, alice, profile_id=bob_profile["id"], user_id=bob.user_id)
    for_bob = await feed(client, bob)

    names_alice = {i["display_name"] for i in for_alice.json()["items"]}
    names_bob = {i["display_name"] for i in for_bob.json()["items"]}
    assert names_alice == {"Bob", "Carol"}
    assert names_bob == {"Alice", "Carol"}
    assert alice_profile["id"] not in for_alice.text
    assert bob_profile["id"] in for_alice.text and carol_profile["id"] in for_alice.text
    assert carol.user_id not in for_alice.text


async def test_a_hidden_viewer_still_sees_the_feed_but_nobody_sees_them(
    client: httpx.AsyncClient,
):
    hidden, hidden_profile = await add(client, display_name="Hidden", is_visible=False)
    seen, _ = await add(client, display_name="Seen")

    for_hidden = await feed(client, hidden)
    for_seen = await feed(client, seen)

    assert [i["display_name"] for i in for_hidden.json()["items"]] == ["Seen"]
    assert for_seen.json()["items"] == []
    assert hidden_profile["id"] not in for_seen.text


async def test_deleting_a_profile_removes_it_from_other_feeds(client: httpx.AsyncClient):
    me, _ = await add(client)
    gone, _ = await add(client, display_name="Gone")
    assert len((await feed(client, me)).json()["items"]) == 1

    await client.delete("/api/v1/profiles/me", headers=gone.headers)

    assert (await feed(client, me)).json()["items"] == []
