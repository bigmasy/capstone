"""Database access for user accounts."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.domain.account import Account
from app.domain.errors import ConflictError

# Generic on purpose: the message must not confirm that a given e-mail is registered.
_CONFLICT_MESSAGE = "Registration could not be completed"


def as_utc(moment: datetime) -> datetime:
    """Return a timestamp as timezone-aware UTC (SQLite drops the zone, PostgreSQL keeps it)."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _to_account(row: User) -> Account:
    """Map an ORM row to the domain record."""
    return Account(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        created_at=as_utc(row.created_at),
    )


class UserRepository:
    """All database operations on user accounts.

    :param session: Database session of the current request.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Keep the session."""
        self.db = session

    async def get_user_by_id(self, user_id: UUID) -> Account | None:
        """Load an account by its identifier.

        :param user_id: Identifier of the user.
        :return: The account, or None if it does not exist.
        """
        row = await self.db.get(User, user_id, populate_existing=True)
        return None if row is None else _to_account(row)

    async def get_user_by_email(self, email: str) -> Account | None:
        """Load an account by e-mail address, ignoring case.

        :param email: E-mail address.
        :return: The account, or None if it does not exist.
        """
        result = await self.db.execute(select(User).where(User.email == email.strip().lower()))
        row = result.scalar_one_or_none()
        return None if row is None else _to_account(row)

    async def create_user(self, email: str, password_hash: str) -> Account:
        """Create an account; the e-mail is stored lower-cased.

        :param email: E-mail address.
        :param password_hash: Argon2id hash of the password.
        :raises ConflictError: If the e-mail is already registered.
        :return: The new account.
        """
        row = User(email=email.strip().lower(), password_hash=password_hash)
        self.db.add(row)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError(_CONFLICT_MESSAGE) from exc
        await self.db.refresh(row)
        return _to_account(row)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        """Replace the stored hash, used when the hashing parameters were strengthened.

        :param user_id: Identifier of the user.
        :param password_hash: New Argon2id hash.
        """
        await self.db.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )
        await self.db.commit()

    async def remove_user(self, user_id: UUID) -> bool:
        """Delete an account; the profile and everything below it go with it (ON DELETE CASCADE).

        :param user_id: Identifier of the user.
        :return: True if an account was deleted, False if there was none.
        """
        result = await self.db.execute(delete(User).where(User.id == user_id))
        await self.db.commit()
        # A DELETE statement always yields a cursor result; the typing stubs say Result.
        return bool(cast(CursorResult[Any], result).rowcount)
