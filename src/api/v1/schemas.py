from datetime import datetime

from pydantic import BaseModel

from src.integrations.legacy_lk.gateway import LegacyClientRecord


class LegacyClientResponse(BaseModel):
    id: int
    full_name: str
    email: str | None
    registered_at: datetime
    stage_id: int | None

    @classmethod
    def from_record(cls, client: LegacyClientRecord) -> "LegacyClientResponse":
        return cls(
            id=client.id,
            full_name=client.full_name,
            email=client.email,
            registered_at=client.registered_at,
            stage_id=client.stage_id,
        )
