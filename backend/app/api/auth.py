"""Registration, login and the caller's own account."""

from fastapi import APIRouter, Response, status

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import (
    ErrorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
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


@router.post(
    "/verify-email",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse}},
)
async def verify_email(body: VerifyEmailRequest, service: AuthServiceDep) -> Response:
    """Confirm the e-mail address with the token from the message.

    No sign-in is needed: the link is opened from a mailbox, possibly on another device.

    :param body: The token.
    :param service: Authentication service.
    :raises InvalidVerificationError: If the token is unknown, used or expired (answered 400).
    :return: An empty response.
    """
    await service.confirm_email(body.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/resend-verification",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def resend_verification(current: CurrentUser, service: AuthServiceDep) -> Response:
    """Send the confirmation message again.

    The answer is always 204, whether or not a message was sent: an account that is already
    confirmed, or was sent one a moment ago, gets nothing and learns nothing.

    :param current: The authenticated caller.
    :param service: Authentication service.
    :return: An empty response.
    """
    await service.resend_confirmation(current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/forgot-password",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def forgot_password(body: ForgotPasswordRequest, service: AuthServiceDep) -> Response:
    """Ask for a password-reset link to be sent to an address.

    The answer is always 204: an unknown address, a known one and one that was sent a link a
    moment ago cannot be told apart, and the message goes out after the response.

    :param body: The address.
    :param service: Authentication service.
    :return: An empty response.
    """
    await service.request_password_reset(body.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reset-password",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse}},
)
async def reset_password(body: ResetPasswordRequest, service: AuthServiceDep) -> Response:
    """Set a new password with the token from the message.

    No sign-in is needed: the person forgot the password. Tokens issued before the change stop
    working.

    :param body: The token and the new password.
    :param service: Authentication service.
    :raises InvalidResetError: If the token is unknown, used or expired (answered 400).
    :return: An empty response.
    """
    await service.reset_password(body.token, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
