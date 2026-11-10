"""Registration, login, token authentication and account deletion."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.mail import Mail, MailSender
from app.core.mail_templates import confirmation_mail, password_reset_mail
from app.core.security import PasswordHasher, TokenCodec
from app.domain.account import Account
from app.domain.errors import AuthenticationError, NotFoundError
from app.domain.password_reset import InvalidResetError
from app.domain.verification import (
    InvalidVerificationError,
    generate_token,
    hash_token,
)
from app.repository.password_reset import PasswordResetRepository
from app.repository.users import UserRepository
from app.repository.verification import VerificationRepository

logger = logging.getLogger(__name__)

# One message for an unknown e-mail and for a wrong password, so the response never tells
# which of the two it was.
_BAD_CREDENTIALS = "Incorrect e-mail or password"
_INVALID_TOKEN = "Could not validate credentials"  # noqa: S105


def _utc_now() -> datetime:
    """Return the current time as timezone-aware UTC."""
    return datetime.now(UTC)


# Hands a message to something that sends it after the response has gone out.
Defer = Callable[[Callable[[Mail], Awaitable[None]], Mail], None]


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    """How the one-time links of e-mail confirmation and password reset behave.

    :param base_url: Origin of the web client, the start of the link in the message.
    :param ttl: How long a confirmation link works.
    :param resend_after: Minimum time between two messages of one kind to the same account.
    :param reset_ttl: How long a password-reset link works.
    """

    base_url: str
    ttl: timedelta
    resend_after: timedelta
    reset_ttl: timedelta = timedelta(hours=1)


class AuthService:
    """Account scenarios.

    :param users: Repository of user accounts.
    :param hasher: Password hashing.
    :param tokens: Access token codec.
    :param verifications: Repository of confirmation tokens.
    :param mail: Delivers the confirmation message.
    :param policy: Link lifetime and resend interval.
    :param resets: Repository of password-reset tokens.
    :param defer: Sends the reset message after the response; None sends it at once. A reset
        request answers the same way for every address, so the time it takes must not depend
        on whether a message was sent.
    :param clock: Source of the current time; replaced in tests.
    """

    def __init__(  # noqa: PLR0913
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenCodec,
        verifications: VerificationRepository,
        mail: MailSender,
        policy: VerificationPolicy,
        resets: PasswordResetRepository,
        defer: Defer | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Keep the collaborators."""
        self.resets = resets
        self.defer = defer
        self.users = users
        self.hasher = hasher
        self.tokens = tokens
        self.verifications = verifications
        self.mail = mail
        self.policy = policy
        self.clock = clock

    async def register(self, email: str, password: str) -> Account:
        """Create an account.

        Hashing is CPU-bound, so it runs in a worker thread and does not block the event loop.

        :param email: E-mail address; stored lower-cased.
        :param password: Plain password that satisfies the password policy.
        :raises ConflictError: If the e-mail is already registered; the message is generic.
        :return: The new account.
        """
        password_hash = await asyncio.to_thread(self.hasher.hash, password)
        account = await self.users.create_user(email, password_hash)
        await self._send_confirmation(account)
        return account

    async def register_confirmed(self, email: str, password: str) -> Account:
        """Create an account that needs no e-mail confirmation (the demo accounts).

        Nothing is sent. Used only by the seeding tool; the API never calls it.

        :param email: E-mail address; stored lower-cased.
        :param password: Plain password.
        :raises ConflictError: If the e-mail is already registered.
        :return: The new, already confirmed account.
        """
        password_hash = await asyncio.to_thread(self.hasher.hash, password)
        return await self.users.create_user(email, password_hash, verified_at=self.clock())

    async def confirm_email(self, token: str) -> None:
        """Confirm an account with the token from the message.

        :param token: Token as it appears in the link.
        :raises InvalidVerificationError: If the token is unknown, already used or expired.
        """
        if await self.verifications.consume(hash_token(token), self.clock()) is None:
            raise InvalidVerificationError

    async def resend_confirmation(self, account: Account) -> None:
        """Send the confirmation message again.

        Quietly does nothing for an account that is already confirmed or was sent a message
        less than ``resend_after`` ago, so the answer never depends on either fact and a script
        cannot use the route to flood an address.

        :param account: The caller.
        """
        if account.is_verified:
            return
        last = await self.verifications.latest_issue_time(account.id)
        if last is not None and self.clock() - last < self.policy.resend_after:
            return
        await self._send_confirmation(account)

    async def issue_confirmation_link(self, account: Account) -> str:
        """Create a new confirmation link and return it without sending anything.

        Earlier links of the account stop working. Used by the message itself and by the
        administrator's command, never by an HTTP route.

        :param account: Account to confirm.
        :return: The full link, with the token in the fragment.
        """
        token = generate_token()
        now = self.clock()
        await self.verifications.issue(account.id, hash_token(token), now, now + self.policy.ttl)
        # The token sits in the fragment: it is not sent to any server, proxy log or referrer
        return f"{self.policy.base_url}/verify-email#token={token}"

    async def _send_confirmation(self, account: Account) -> None:
        """Issue a link and mail it; a delivery problem never fails the caller.

        Registration must succeed even when the mail server is down: the person can ask for the
        message again. Only the class of the problem is logged, never the address.

        :param account: Account to confirm.
        """
        link = await self.issue_confirmation_link(account)
        minutes = int(self.policy.ttl.total_seconds() // 60)
        await self._send_quietly(confirmation_mail(account.email, link, minutes))

    async def _send_quietly(self, mail: Mail) -> None:
        """Send a message; a delivery problem is logged by its class and never raised.

        :param mail: The message.
        """
        try:
            await self.mail.send(mail)
        except Exception as error:
            logger.warning("mail was not sent (%s)", type(error).__name__)

    async def request_password_reset(self, email: str) -> None:
        """Send a password-reset link to an address, if an account has it.

        Nothing tells the caller whether the address is known or whether a message was
        sent: an unknown address and one that was sent a link a moment ago are both silent,
        and the message goes out after the response, so the time taken does not give it away
        either.

        :param email: Address typed by the person.
        """
        account = await self.users.get_user_by_email(email)
        if account is None:
            return
        last = await self.resets.latest_issue_time(account.id)
        if last is not None and self.clock() - last < self.policy.resend_after:
            return
        link = await self.issue_reset_link(account)
        minutes = int(self.policy.reset_ttl.total_seconds() // 60)
        mail = password_reset_mail(account.email, link, minutes)
        if self.defer is None:
            await self._send_quietly(mail)
        else:
            self.defer(self._send_quietly, mail)

    async def issue_reset_link(self, account: Account) -> str:
        """Create a new password-reset link and return it without sending anything.

        Earlier links of the account stop working. Used by the message itself and by the
        administrator's command, never returned by an HTTP route.

        :param account: Account whose password may be reset.
        :return: The full link, with the token in the fragment.
        """
        token = generate_token()
        now = self.clock()
        await self.resets.issue(account.id, hash_token(token), now, now + self.policy.reset_ttl)
        return f"{self.policy.base_url}/reset-password#token={token}"

    async def reset_password(self, token: str, new_password: str) -> None:
        """Set a new password with the token from the message.

        The link is a proof of the mailbox, so an account that was not confirmed yet becomes
        confirmed. Access tokens issued before the change stop working.

        :param token: Token as it appears in the link.
        :param new_password: The new plain password, already checked against the policy.
        :raises InvalidResetError: If the token is unknown, already used or expired.
        """
        password_hash = await asyncio.to_thread(self.hasher.hash, new_password)
        if await self.resets.consume(hash_token(token), self.clock(), password_hash) is None:
            raise InvalidResetError

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

        The user is loaded on every call, so a token of a deleted account stops working at once,
        and so does a token issued before the password was reset.

        :param token: Encoded access token.
        :raises AuthenticationError: If the token is invalid or its user no longer exists.
        :return: The account.
        """
        user_id, issued_at = self.tokens.decode_with_issue_time(token)
        account = await self.users.get_user_by_id(user_id)
        if account is None:
            raise AuthenticationError(_INVALID_TOKEN)
        changed = account.password_changed_at
        # The token carries whole seconds only, so compare with the change rounded down
        if changed is not None and issued_at < changed.replace(microsecond=0):
            raise AuthenticationError(_INVALID_TOKEN)
        return account

    async def delete_account(self, user_id: UUID) -> None:
        """Delete an account with its profile and everything stored under it.

        :param user_id: Identifier of the account to delete.
        :raises NotFoundError: If there is no such account.
        """
        if not await self.users.remove_user(user_id):
            raise NotFoundError("Account not found")
