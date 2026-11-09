"""Registration, login and the caller's own account."""

from fastapi import APIRouter, Response, status

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
)
async def register(body: RegisterRequest, service: AuthServiceDep) -> UserResponse:
    """Create an account.

    :param body: E-mail and password.
    :param service: Authentication service.
    :raises ConflictError: If the e-mail is already registered (answered with 409).
    :return: The new account.
    """
    account = await service.register(body.email, body.password)
    return UserResponse.from_domain(account)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def login(body: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    """Exchange credentials for an access token.

    :param body: E-mail and password.
    :param service: Authentication service.
    :raises AuthenticationError: If the credentials are wrong (answered with 401).
    :return: A bearer token.
    """
    return TokenResponse(access_token=await service.login(body.email, body.password))


@router.get(
    "/me",
    response_model=UserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def read_me(current: CurrentUser) -> UserResponse:
    """Return the caller's account.

    :param current: The authenticated caller.
    :return: The account.
    """
    return UserResponse.from_domain(current)


@router.delete(
    "/me",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def delete_me(current: CurrentUser, service: AuthServiceDep) -> Response:
    """Delete the caller's account together with the profile and all data under it.

    :param current: The authenticated caller.
    :param service: Authentication service.
    :return: An empty response.
    """
    await service.delete_account(current.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
