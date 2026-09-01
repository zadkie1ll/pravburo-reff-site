import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.integrations.legacy_lk.database import get_legacy_session
from src.integrations.legacy_lk.gateway import LegacyClientGateway
from src.services.agents import ensure_legacy_client_agent
from src.site.crm_client import CRMClient

router = APIRouter(prefix="/webhooks/legacy", tags=["legacy webhooks"])


@router.post("/client-created")
async def legacy_client_created(
    request: Request,
    referral_session: Annotated[AsyncSession, Depends(get_session)],
    legacy_session: Annotated[AsyncSession, Depends(get_legacy_session)],
    webhook_secret: str = Header(default="", alias="X-Webhook-Secret"),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.legacy_webhook_secret or not hmac.compare_digest(
        webhook_secret, settings.legacy_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    payload = await request.json()
    client_id = int(payload.get("client_id", 0))
    client = await LegacyClientGateway(legacy_session).get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Legacy client not found")
    phone = await CRMClient().get_deal_contact_phone(client.bitrix_id) if client.bitrix_id else None
    agent, created = await ensure_legacy_client_agent(referral_session, client, phone)
    return {"status": "created" if created else "existing", "agent_id": agent.id}
