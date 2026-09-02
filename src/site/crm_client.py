import logging

import httpx
from pravburo_ref_common.contracts import LeadCreate
from pravburo_ref_common.models import ReferralApplication

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class CRMClient:
    async def create_lead(self, application: ReferralApplication, agent_name: str) -> str:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.crm_service_url.rstrip('/')}/internal/leads",
                headers={"X-Internal-Token": settings.internal_service_token},
                json=LeadCreate(
                    application_id=application.id,
                    agent_id=application.agent_id,
                    agent_name=agent_name,
                    full_name=application.full_name,
                    phone_normalized=application.phone_normalized,
                    preferred_call_time_msk=application.preferred_call_time_msk,
                    city=application.city,
                    debt_amount=application.debt_amount,
                    situation=application.situation,
                ).model_dump(mode="json"),
            )
        response.raise_for_status()
        result = response.json()
        lead_id = result.get("lead_id")
        if result.get("status") != "created" or not lead_id:
            raise RuntimeError("CRM service did not confirm lead creation")
        logger.info(
            "CRM lead creation confirmed: application_id=%s lead_id=%s",
            application.id,
            lead_id,
        )
        return str(lead_id)

    async def get_deal_contact_phone(self, deal_id: str) -> str | None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{settings.crm_service_url.rstrip('/')}/internal/deals/{deal_id}/contact-phone",
                headers={"X-Internal-Token": settings.internal_service_token},
            )
        response.raise_for_status()
        value = response.json().get("phone")
        return str(value) if value else None
