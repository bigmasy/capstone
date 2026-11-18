"""The caller's own profile and the public view of other profiles."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, ProfileServiceDep
from app.domain.photo import (
    PHOTO_ACCEPTED_MEDIA_TYPES,
    PHOTO_MAX_UPLOAD_BYTES,
    PHOTO_MEDIA_TYPE,
    PHOTO_TOO_LARGE_CODE,
    PhotoRejectedError,
)
from app.schemas.auth import ErrorResponse
from app.schemas.profiles import PhotoRejectedResponse, ProfileOwner, ProfilePublic, ProfilePut

router = APIRouter(prefix="/profiles", tags=["profiles"])

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_PHOTO_REJECTED: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": PhotoRejectedResponse}
}


@router.put("/me", response_model=ProfileOwner, responses=_UNAUTHORIZED)
async def put_my_profile(
    body: ProfilePut, current: CurrentUser, service: ProfileServiceDep
) -> ProfileOwner:
    """Create or fully replace the caller's profile.

    The exact location is coarsened to a grid cell before it is stored and is never returned.
    Latitude and longitude are optional on an update: omit both to keep the stored cell. The
    first save needs both. Capabilities are stored only while ``functional_data_consent`` is
    true.

    :param body: The complete profile; the location is both coordinates or neither.
    :param current: The authenticated caller.
    :param service: Profile service.
    :raises LocationRequiredError: If there is no profile yet and the body has no location
        (answered with 422).
    :return: The stored profile as its owner sees it.
    """
    return ProfileOwner.from_owner(await service.put_profile(current.id, body.to_draft()))


@router.get("/me", response_model=ProfileOwner, responses={**_UNAUTHORIZED, **_NOT_FOUND})
async def get_my_profile(current: CurrentUser, service: ProfileServiceDep) -> ProfileOwner:
    """Return the caller's own profile.

    :param current: The authenticated caller.
    :param service: Profile service.
    :raises NotFoundError: If the caller has no profile yet (answered with 404).
    :return: The profile as its owner sees it.
    """
    return ProfileOwner.from_owner(await service.get_my_profile(current.id))


@router.delete(
    "/me",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def delete_my_profile(current: CurrentUser, service: ProfileServiceDep) -> Response:
    """Delete the caller's profile; the account stays.

    :param current: The authenticated caller.
    :param service: Profile service.
    :raises NotFoundError: If the caller has no profile (answered with 404).
    :return: An empty response.
    """
    await service.delete_my_profile(current.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


_PHOTO_UPLOAD: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            media_type: {"schema": {"type": "string", "format": "binary"}}
            for media_type in PHOTO_ACCEPTED_MEDIA_TYPES
        },
    }
}


async def _read_limited(request: Request) -> bytes:
    """Read the request body, refusing one that is larger than a photograph may be.

    The declared length is checked first, and the stream is counted as it arrives, so a body
    without a length or with a false one is still cut off at the limit.

    :param request: The upload request.
    :raises PhotoRejectedError: If the body is larger than the limit.
    :return: The whole body.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > PHOTO_MAX_UPLOAD_BYTES:
        raise PhotoRejectedError(PHOTO_TOO_LARGE_CODE)
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > PHOTO_MAX_UPLOAD_BYTES:
            raise PhotoRejectedError(PHOTO_TOO_LARGE_CODE)
        chunks.append(chunk)
    return b"".join(chunks)


@router.put(
    "/me/photo",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_UNAUTHORIZED, **_NOT_FOUND, **_PHOTO_REJECTED},
    openapi_extra=_PHOTO_UPLOAD,
)
async def put_my_photo(
    request: Request, current: CurrentUser, service: ProfileServiceDep
) -> Response:
    """Upload the caller's photograph, replacing the previous one.

    The body is the picture itself (JPEG, PNG or WebP, at most 2 MB), not a form. It is decoded
    and stored again as a small square JPEG, so the original file and its metadata are not kept.

    :param request: The upload; its body is the picture.
    :param current: The authenticated caller.
    :param service: Profile service.
    :raises PhotoRejectedError: If the body is too large or is not a picture (answered with 422).
    :raises NotFoundError: If the caller has no profile yet (answered with 404).
    :return: An empty response.
    """
    await service.put_photo(current.id, await _read_limited(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/me/photo",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def delete_my_photo(current: CurrentUser, service: ProfileServiceDep) -> Response:
    """Delete the caller's photograph; the answer is the same when there was none.

    :param current: The authenticated caller.
    :param service: Profile service.
    :raises NotFoundError: If the caller has no profile (answered with 404).
    :return: An empty response.
    """
    await service.delete_photo(current.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{profile_id}/photo",
    response_class=Response,
    responses={
        status.HTTP_200_OK: {"content": {PHOTO_MEDIA_TYPE: {}}},
        **_UNAUTHORIZED,
        **_NOT_FOUND,
    },
)
async def get_profile_photo(
    profile_id: UUID, current: CurrentUser, service: ProfileServiceDep
) -> Response:
    """Return the photograph of a profile as a JPEG.

    The owner always gets their own. Anyone else gets it only while the profile is visible; a
    hidden profile, a missing profile and a profile without a photograph all answer 404.

    :param profile_id: Identifier of the profile.
    :param current: The authenticated caller.
    :param service: Profile service.
    :raises NotFoundError: If there is nothing the caller may see (answered with 404).
    :return: The picture, cacheable only by the caller's own browser.
    """
    content = await service.get_photo(profile_id, current.id)
    return Response(
        content=content,
        media_type=PHOTO_MEDIA_TYPE,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/{profile_id}", response_model=ProfilePublic, responses={**_UNAUTHORIZED, **_NOT_FOUND}
)
async def get_profile(
    profile_id: UUID, current: CurrentUser, service: ProfileServiceDep
) -> ProfilePublic:
    """Return the public view of a visible profile.

    The same answer, 404, is given for a missing profile and for a hidden one.

    :param profile_id: Identifier of the profile.
    :param current: The authenticated caller; any signed-in user may look.
    :param service: Profile service.
    :raises NotFoundError: If the profile is missing or hidden (answered with 404).
    :return: Display name, district, intensity and sports.
    """
    return ProfilePublic.from_domain(await service.get_public_profile(profile_id))
