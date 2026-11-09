"""Registration, login, token authentication and account deletion."""

import asyncio
from uuid import UUID

from app.core.security import PasswordHasher, TokenCodec
from app.domain.account import Account
from app.domain.errors import AuthenticationError, NotFoundError
from app.repository.users import UserRepository

# One message for an unknown e-mail and for a wrong password, so the response never tells
# which of the two it was.
_BAD_CREDENTIALS = "Incorrect e-mail or password"
_INVALID_TOKEN = "Could not validate credentials"  # noqa: S105


class AuthService:
    """Account scenarios.

    :param users: Repository of user accounts.
    :param hasher: Password hashing.
    :param tokens: Access token codec.
    """

    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenCodec) -> None:
        """Keep the collaborators."""
        self.users = users
        self.hasher = hasher
        self.tokens = tokens

    async def register(self, email: str, password: str) -> Account:
        """Create an account.

        Hashing is CPU-bound, so it runs in a worker thread and does not block the event loop.

        :param email: E-mail address; stored lower-cased.
        :param password: Plain password that satisfies the password policy.
        :raises ConflictError: If the e-mail is already registered; the message is generic.
        :return: The new account.
        """
        password_hash = await asyncio.to_thread(self.hasher.hash, password)
        return await self.users.create_user(email, password_hash)

    async def login(self, email: str, password: str) -> str:
        """Check the credentials and issue an access token.

        For an unknown e-mail the password is verified against a dummy hash, so the work done
        and the answer are the same as for a wrong password.

        :param email: E-mail address.
        :param password: Plain password.
        :raises AuthenticationError: If the e-mail is unknown or the password is wrong.
        :return: Encoded access token.
        """
        account = await self.users.get_user_by_email(email)
        stored = account.password_hash if account else self.hasher.dummy_hash
        matches = await asyncio.to_thread(self.hasher.verify, stored, password)
        if account is None or not matches:
            raise AuthenticationError(_BAD_CREDENTIALS)
        if self.hasher.needs_rehash(account.password_hash):
            # The hashing cost was raised since the password was set; upgrade it while the
            # plain password is at hand.
            fresh = await asyncio.to_thread(self.hasher.hash, password)
            await self.users.update_password_hash(account.id, fresh)
        return self.tokens.issue(account.id)

    async def authenticate(self, token: str) -> Account:
        """Resolve a token to the current account.

        The user is loaded on every call, so a token of a deleted account stops working at once.

        :param token: Encoded access token.
        :raises AuthenticationError: If the token is invalid or its user no longer exists.
        :return: The account.
        """
        account = await self.users.get_user_by_id(self.tokens.decode(token))
        if account is None:
            raise AuthenticationError(_INVALID_TOKEN)
        return account

    async def delete_account(self, user_id: UUID) -> None:
        """Delete an account with its profile and everything stored under it.

        :param user_id: Identifier of the account to delete.
        :raises NotFoundError: If there is no such account.
        """
        if not await self.users.remove_user(user_id):
            raise NotFoundError("Account not found")
