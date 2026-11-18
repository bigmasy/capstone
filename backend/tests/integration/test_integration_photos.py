"""The profile photograph over HTTP: upload, privacy of the stored picture, visibility."""

import io

import httpx
from PIL import Image

from app.domain.photo import PHOTO_MAX_UPLOAD_BYTES, PHOTO_SIDE_PX
from tests.integration.helpers import make_profile_body, sign_up, sign_up_with_profile

JPEG = {"Content-Type": "image/jpeg"}
GPS_INFO_TAG = 0x8825


def picture(fmt: str = "JPEG", size: tuple[int, int] = (640, 480), **save: object) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 120, 90)).save(out, format=fmt, **save)
    return out.getvalue()


def picture_with_location() -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "CanaryCamera"
    exif.get_ifd(GPS_INFO_TAG)[2] = (50.0, 27.0, 3.6)
    return picture(exif=exif)


async def upload(client: httpx.AsyncClient, headers: dict[str, str], content: bytes):
    return await client.put("/api/v1/profiles/me/photo", headers=headers | JPEG, content=content)


async def test_an_uploaded_picture_is_stored_as_a_small_square_jpeg(client: httpx.AsyncClient):
    owner, profile = await sign_up_with_profile(client)
    assert profile["has_photo"] is False

    response = await upload(client, owner.headers, picture("PNG", (900, 300)))

    assert response.status_code == 204
    me = (await client.get("/api/v1/profiles/me", headers=owner.headers)).json()
    assert me["has_photo"] is True
    photo = await client.get(f"/api/v1/profiles/{profile['id']}/photo", headers=owner.headers)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert photo.headers["cache-control"].startswith("private")
    stored = Image.open(io.BytesIO(photo.content))
    assert stored.format == "JPEG"
    assert stored.size == (PHOTO_SIDE_PX, PHOTO_SIDE_PX)


async def test_the_stored_picture_carries_no_metadata_of_the_upload(client: httpx.AsyncClient):
    owner, profile = await sign_up_with_profile(client)
    original = picture_with_location()
    assert b"CanaryCamera" in original

    assert (await upload(client, owner.headers, original)).status_code == 204

    photo = await client.get(f"/api/v1/profiles/{profile['id']}/photo", headers=owner.headers)
    assert b"CanaryCamera" not in photo.content
    assert b"Exif" not in photo.content
    assert not Image.open(io.BytesIO(photo.content)).getexif()


async def test_other_people_see_the_picture_only_while_the_profile_is_visible(
    client: httpx.AsyncClient,
):
    owner, profile = await sign_up_with_profile(client)
    viewer = await sign_up(client)
    await upload(client, owner.headers, picture())
    url = f"/api/v1/profiles/{profile['id']}/photo"

    assert (await client.get(url, headers=viewer.headers)).status_code == 200
    public = await client.get(f"/api/v1/profiles/{profile['id']}", headers=viewer.headers)
    assert public.json()["has_photo"] is True

    hidden = await client.put(
        "/api/v1/profiles/me", headers=owner.headers, json=make_profile_body(is_visible=False)
    )
    assert hidden.status_code == 200 and hidden.json()["has_photo"] is True
    assert (await client.get(url, headers=viewer.headers)).status_code == 404
    assert (await client.get(url, headers=owner.headers)).status_code == 200


async def test_the_feed_says_who_has_a_picture(client: httpx.AsyncClient):
    viewer, _ = await sign_up_with_profile(client)
    with_photo, _ = await sign_up_with_profile(client, display_name="With")
    await sign_up_with_profile(client, display_name="Without")
    await upload(client, with_photo.headers, picture())

    items = (await client.get("/api/v1/matches", headers=viewer.headers)).json()["items"]

    assert {item["display_name"]: item["has_photo"] for item in items} == {
        "With": True,
        "Without": False,
    }


async def test_a_file_that_is_not_a_picture_is_refused_without_echo(client: httpx.AsyncClient):
    owner, _ = await sign_up_with_profile(client)

    response = await upload(client, owner.headers, b"<svg onload=alert(1)>canary-upload</svg>")

    assert response.status_code == 422
    assert response.json()["code"] == "photo_invalid"
    assert "canary-upload" not in response.text
    me = (await client.get("/api/v1/profiles/me", headers=owner.headers)).json()
    assert me["has_photo"] is False


async def test_a_truncated_picture_is_refused(client: httpx.AsyncClient):
    owner, _ = await sign_up_with_profile(client)

    response = await upload(client, owner.headers, picture()[:200])

    assert response.status_code == 422
    assert response.json()["code"] == "photo_invalid"


async def test_an_upload_over_the_limit_is_refused(client: httpx.AsyncClient):
    owner, _ = await sign_up_with_profile(client)

    response = await upload(client, owner.headers, b"\xff" * (PHOTO_MAX_UPLOAD_BYTES + 1))

    assert response.status_code == 422
    assert response.json()["code"] == "photo_too_large"


async def test_a_picture_needs_a_profile_and_a_token(client: httpx.AsyncClient):
    without_profile = await sign_up(client)

    assert (await upload(client, without_profile.headers, picture())).status_code == 404
    assert (await upload(client, {}, picture())).status_code == 401
    assert (
        await client.delete("/api/v1/profiles/me/photo", headers=without_profile.headers)
    ).status_code == 404


async def test_deleting_the_picture_is_repeatable(client: httpx.AsyncClient):
    owner, profile = await sign_up_with_profile(client)
    await upload(client, owner.headers, picture())

    for _ in range(2):
        gone = await client.delete("/api/v1/profiles/me/photo", headers=owner.headers)
        assert gone.status_code == 204

    me = (await client.get("/api/v1/profiles/me", headers=owner.headers)).json()
    assert me["has_photo"] is False
    photo = await client.get(f"/api/v1/profiles/{profile['id']}/photo", headers=owner.headers)
    assert photo.status_code == 404


async def test_a_new_upload_replaces_the_previous_picture(client: httpx.AsyncClient):
    owner, profile = await sign_up_with_profile(client)
    url = f"/api/v1/profiles/{profile['id']}/photo"
    await upload(client, owner.headers, picture())
    first = (await client.get(url, headers=owner.headers)).content

    out = io.BytesIO()
    Image.new("RGB", (400, 400), (200, 40, 40)).save(out, format="WEBP")
    assert (await upload(client, owner.headers, out.getvalue())).status_code == 204

    assert (await client.get(url, headers=owner.headers)).content != first
