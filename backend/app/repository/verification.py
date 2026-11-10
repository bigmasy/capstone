"""Database access for e-mail confirmation tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import EmailVerification, User
from app.repository.users import as_utc


class VerificationRepository:
    """Stores the digests of confirmation tokens and consumes them once.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def issue(
        self, user_id: UUID, token_hash: str, created_at: datetime, expires_at: datetime
    ) -> None:
        """Store a new token digest; earlier tokens of the user stop working.

        :param user_id: Owner of the account.
        :param token_hash: Digest of the token that was e-mailed.
        :param created_at: Issue time.
        :param expires_at: Instant after which the token is no longer accepted.
        """
        await self.db.execute(delete(EmailVerification).where(EmailVerification.user_id == user_id))
        self.db.add(
            EmailVerification(
                user_id=user_id,
                token_hash=token_hash,
                created_at=created_at,
                expires_at=expires_at,
            )
        )
        await self.db.commit()

    async def latest_issue_time(self, user_id: UUID) -> datetime | None:
        """Return when the user was last sent a token.

        :param user_id: Owner of the account.
        :return: The latest issue time (UTC), or None if no token was ever issued.
        """
        result = await self.db.execute(
            select(func.max(EmailVerification.created_at)).where(
                EmailVerification.user_id == user_id
            )
        )
        moment = result.scalar_one_or_none()
        return None if moment is None else as_utc(moment)

    async def consume(self, token_hash: str, now: datetime) -> UUID | None:
        """Use a token once and mark its account as verified, in one transaction.

        The conditional UPDATE makes two simultaneous uses of the same link race-safe: only
        one of them matches a row that is still unused.

        :param token_hash: Digest of the submitted token.
        :param now: Current time.
        :return: The verified user, or None if the token is unknown, used or expired.
        """
        result = await self.db.execute(
            update(EmailVerification)
            .where(
                EmailVerification.token_hash == token_hash,
                EmailVerification.used_at.is_(None),
                EmailVerification.expires_at > now,
            )
            .values(used_at=now)
            .returning(EmailVerification.user_id)
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            await self.db.rollback()
            return None
        await self.db.execute(
            update(User)
            .where(User.id == user_id, User.email_verified_at.is_(None))
            .values(email_verified_at=now)
        )
        await self.db.commit()
        return user_id
