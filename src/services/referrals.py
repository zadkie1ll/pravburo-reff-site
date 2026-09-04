import logging
from dataclasses import dataclass
from typing import Protocol

from pravburo_ref_common.models import (
    Agent,
    DeliveryStatus,
    ReferralApplication,
    ReferralLinkVisit,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import normalize_phone

logger = logging.getLogger(__name__)


async def record_link_visit(session: AsyncSession, agent_id: int) -> None:
    session.add(ReferralLinkVisit(agent_id=agent_id))
    await session.commit()


@dataclass(slots=True)
class LinkStats:
    visits: int
    applications: int

    @property
    def conversion_rate_label(self) -> str:
        if not self.visits:
            return "—"
        return f"{round(self.applications / self.visits * 100)}%"


async def get_link_stats(session: AsyncSession, agent_id: int) -> LinkStats:
    visits = await session.scalar(
        select(func.count())
        .select_from(ReferralLinkVisit)
        .where(ReferralLinkVisit.agent_id == agent_id)
    )
    applications = await session.scalar(
        select(func.count())
        .select_from(ReferralApplication)
        .where(ReferralApplication.agent_id == agent_id)
    )
    return LinkStats(visits=visits or 0, applications=applications or 0)


@dataclass(slots=True)
class ActivityStats:
    applications: int
    paying_clients: int

    @property
    def conversion_rate_label(self) -> str:
        if not self.applications:
            return "—"
        return f"{round(self.paying_clients / self.applications * 100)}%"


def get_activity_stats(
    application_ids: list[int], rewards_by_application: dict[int, list]
) -> ActivityStats:
    """A client "paid" once any (non-override) reward exists for their
    application - reward creation is triggered by a CRM deal stage change
    (advance / deposit), so its mere presence means real money moved.
    """
    paying_clients = sum(
        1 for app_id in application_ids if rewards_by_application.get(app_id)
    )
    return ActivityStats(applications=len(application_ids), paying_clients=paying_clients)


class LeadDeliveryGateway(Protocol):
    async def create_lead(self, application: ReferralApplication, agent_name: str) -> str: ...


@dataclass(slots=True)
class ApplicationInput:
    full_name: str
    phone: str
    preferred_call_time_msk: str = ""
    city: str = ""
    debt_amount: str = ""
    situation: str = ""


async def create_first_application(
    session: AsyncSession,
    agent: Agent,
    data: ApplicationInput,
    lead_delivery: LeadDeliveryGateway,
) -> tuple[ReferralApplication, bool]:
    phone = normalize_phone(data.phone)
    application = ReferralApplication(
        agent_id=agent.id,
        full_name=data.full_name.strip(),
        phone_normalized=phone,
        preferred_call_time_msk=data.preferred_call_time_msk.strip() or None,
        city=data.city.strip() or None,
        debt_amount=data.debt_amount.strip() or None,
        situation=data.situation.strip() or None,
    )
    session.add(application)
    try:
        await session.commit()
        await session.refresh(application)
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(ReferralApplication).where(ReferralApplication.phone_normalized == phone)
        )
        if existing is None:
            raise
        return existing, False

    try:
        application.bitrix_lead_id = await lead_delivery.create_lead(
            application, agent.display_name
        )
        application.delivery_status = DeliveryStatus.SENT
    except Exception as exc:
        logger.warning("Bitrix lead delivery failed: application_id=%s", application.id)
        application.delivery_status = DeliveryStatus.FAILED
        application.delivery_error = type(exc).__name__
    await session.commit()
    return application, True
