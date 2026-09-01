from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.legacy_lk.models import LegacyClient, LegacyUser


@dataclass(frozen=True, slots=True)
class LegacyClientRecord:
    id: int
    name: str
    surname: str
    middlename: str | None
    email: str | None
    registered_at: datetime
    stage_id: int | None
    bitrix_id: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.surname, self.name, self.middlename) if part)


class LegacyClientGateway:
    """The only application boundary for reading legacy client data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, client_id: int) -> LegacyClientRecord | None:
        statement = (
            select(LegacyClient, LegacyUser.email, LegacyUser.date_joined)
            .join(LegacyUser, LegacyUser.id == LegacyClient.user_id)
            .where(LegacyClient.id == client_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None

        client, email, registered_at = row
        return LegacyClientRecord(
            id=client.id,
            name=client.name,
            surname=client.surname,
            middlename=client.middlename,
            email=email or None,
            registered_at=registered_at,
            stage_id=client.stage_id,
            bitrix_id=client.bitrix_id,
        )
