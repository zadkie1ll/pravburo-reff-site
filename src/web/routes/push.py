from typing import Annotated

from fastapi import APIRouter, Depends
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import PushSubscription
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.web.dependencies import CurrentAgent

router = APIRouter(prefix="/push", tags=["push"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: PushKeys


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, str]:
    return {"key": get_settings().vapid_public_key}


@router.post("/subscribe")
async def subscribe(
    payload: PushSubscribeRequest, agent: CurrentAgent, session: Session
) -> dict[str, str]:
    existing = await session.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    if existing is not None:
        existing.agent_id = agent.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        session.add(
            PushSubscription(
                agent_id=agent.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
            )
        )
    await session.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(
    payload: PushSubscribeRequest, agent: CurrentAgent, session: Session
) -> dict[str, str]:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.agent_id == agent.id,
        )
    )
    await session.commit()
    return {"status": "unsubscribed"}
