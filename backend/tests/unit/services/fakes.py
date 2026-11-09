"""In-memory stand-ins for the repositories; they record what reaches the storage layer."""

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

    async def create_user(self, email: str, password_hash: str) -> Account:
        if await self.get_user_by_email(email):
            raise ConflictError("Registration could not be completed")
        account = Account(
            id=uuid4(),
            email=email.lower(),
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self.accounts[account.id] = account
        return account

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        old = self.accounts[user_id]
        self.accounts[user_id] = Account(
            id=old.id, email=old.email, password_hash=password_hash, created_at=old.created_at
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
