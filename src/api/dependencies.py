from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.legacy_lk.database import get_legacy_session
from src.integrations.legacy_lk.gateway import LegacyClientGateway


def get_legacy_client_gateway(
    session: Annotated[AsyncSession, Depends(get_legacy_session)],
) -> LegacyClientGateway:
    return LegacyClientGateway(session)


LegacyGatewayDependency = Annotated[LegacyClientGateway, Depends(get_legacy_client_gateway)]
