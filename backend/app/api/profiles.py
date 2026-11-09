"""The caller's own profile and the public view of other profiles."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, ProfileServiceDep
from app.schemas.auth import ErrorResponse
from app.schemas.profiles import ProfileOwner, ProfilePublic, ProfilePut

router = APIRouter(prefix="/profiles", tags=["profiles"])

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}


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
