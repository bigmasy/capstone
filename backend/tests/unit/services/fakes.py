"""In-memory stand-ins for the repositories; they record what reaches the storage layer."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.account import Account, OwnerProfile, ProfileRecord, PublicProfile
from app.domain.errors import ConflictError


class FakeUserRepository:
    def __init__(self) -> None:
        self.accounts: dict[UUID, Account] = {}
        self.removed: list[UUID] = []

    async def get_user_by_id(self, user_id: UUID) -> Account | None:
        return self.accounts.get(user_id)

    async def get_user_by_email(self, email: str) -> Account | None:
        return next((a for a in self.accounts.values() if a.email == email.lower()), None)

    async def create_user(
        self, email: str, password_hash: str, verified_at: datetime | None = None
    ) -> Account:
        if await self.get_user_by_email(email):
            raise ConflictError("Registration could not be completed")
        account = Account(
            id=uuid4(),
            email=email.lower(),
            password_hash=password_hash,
            created_at=datetime.now(UTC),
            email_verified_at=verified_at,
        )
        self.accounts[account.id] = account
        return account

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.accounts[user_id] = replace(self.accounts[user_id], password_hash=password_hash)

    async def is_email_verified(self, user_id: UUID) -> bool:
        account = self.accounts.get(user_id)
        return account is not None and account.is_verified

    async def mark_email_verified(self, user_id: UUID, now: datetime) -> bool:
        if user_id not in self.accounts:
            return False
        self.accounts[user_id] = replace(self.accounts[user_id], email_verified_at=now)
        return True

    async def set_password(self, user_id: UUID, password_hash: str, now: datetime) -> None:
        self.accounts[user_id] = replace(
            self.accounts[user_id], password_hash=password_hash, password_changed_at=now
        )

    async def remove_user(self, user_id: UUID) -> bool:
        self.removed.append(user_id)
        return self.accounts.pop(user_id, None) is not None


class FakeProfileRepository:
    def __init__(self) -> None:
        self.by_user: dict[UUID, OwnerProfile] = {}
        self.records: list[ProfileRecord] = []

    async def get_profile_by_user_id(self, user_id: UUID) -> OwnerProfile | None:
        return self.by_user.get(user_id)

    async def get_public_profile_by_id(self, profile_id: UUID) -> PublicProfile | None:
        for owner in self.by_user.values():
            if owner.id == profile_id and owner.is_visible:
                return PublicProfile(
                    id=owner.id,
                    display_name=owner.display_name,
                    district=owner.district,
                    intensity=owner.intensity,
                    sports=owner.sports,
                )
        return None

    async def replace_profile(self, user_id: UUID, record: ProfileRecord) -> OwnerProfile:
        self.records.append(record)
        previous = self.by_user.get(user_id)
        now = datetime.now(UTC)
        owner = OwnerProfile(
            id=previous.id if previous else uuid4(),
            user_id=user_id,
            display_name=record.display_name,
            district=record.district,
            intensity=record.intensity,
            is_visible=record.is_visible,
            sports=record.sports,
            capabilities=record.capabilities,
            functional_consent_at=record.functional_consent_at,
            contact=record.contact,
            created_at=previous.created_at if previous else now,
            updated_at=now,
        )
        self.by_user[user_id] = owner
        return owner

    async def remove_profile(self, user_id: UUID) -> bool:
        return self.by_user.pop(user_id, None) is not None


class FakeVerificationRepository:
    """Keeps token digests in memory and verifies accounts through the fake user repository."""

    def __init__(self, users: FakeUserRepository) -> None:
        self.users = users
        # digest -> [user id, created, expires, used]
        self.tokens: dict[str, list] = {}

    async def issue(
        self, user_id: UUID, token_hash: str, created_at: datetime, expires_at: datetime
    ) -> None:
        self.tokens = {h: t for h, t in self.tokens.items() if t[0] != user_id}
        self.tokens[token_hash] = [user_id, created_at, expires_at, None]

    async def latest_issue_time(self, user_id: UUID) -> datetime | None:
        times = [t[1] for t in self.tokens.values() if t[0] == user_id]
        return max(times) if times else None

    async def consume(self, token_hash: str, now: datetime) -> UUID | None:
        record = self.tokens.get(token_hash)
        if record is None or record[3] is not None or record[2] <= now:
            return None
        record[3] = now
        await self.users.mark_email_verified(record[0], now)
        return record[0]


class FakeResetRepository:
    """Keeps reset-token digests in memory and changes the password through the fake users."""

    def __init__(self, users: FakeUserRepository) -> None:
        self.users = users
        # digest -> [user id, created, expires, used]
        self.tokens: dict[str, list] = {}

    async def issue(
        self, user_id: UUID, token_hash: str, created_at: datetime, expires_at: datetime
    ) -> None:
        self.tokens = {h: t for h, t in self.tokens.items() if t[0] != user_id}
        self.tokens[token_hash] = [user_id, created_at, expires_at, None]

    async def latest_issue_time(self, user_id: UUID) -> datetime | None:
        times = [t[1] for t in self.tokens.values() if t[0] == user_id]
        return max(times) if times else None

    async def consume(self, token_hash: str, now: datetime, password_hash: str) -> UUID | None:
        record = self.tokens.get(token_hash)
        if record is None or record[3] is not None or record[2] <= now:
            return None
        record[3] = now
        await self.users.set_password(record[0], password_hash, now)
        await self.users.mark_email_verified(record[0], now)
        return record[0]
