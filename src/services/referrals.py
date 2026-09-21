import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from pravburo_ref_common.models import (
    Agent,
    DeliveryStatus,
    ReferralApplication,
    ReferralLinkVisit,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import masked_phone, normalize_phone
from src.services.deal_stages import DEFAULT_STAGE_LABEL, application_status_label, stage_label
from src.services.payouts import (
    REWARD_TYPE_LABELS,
    STATUS_LABELS,
    format_amount,
    payout_status_slug,
)

logger = logging.getLogger(__name__)

FIXATION_EXPIRY_DAYS = 180


async def record_link_visit(session: AsyncSession, agent_id: int) -> None:
    session.add(ReferralLinkVisit(agent_id=agent_id))
    await session.commit()


@dataclass(slots=True)
class LinkStats:
    visits: int
    applications: int
    contracts: int = 0

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
    # Договор заключён, когда клиент попал в воронку "Сопровождение": за это начисляется
    # аванс. Отклонённые авансы не считаем, один клиент - один договор.
    contracts = await session.scalar(
        select(func.count(func.distinct(Reward.application_id))).where(
            Reward.agent_id == agent_id,
            Reward.reward_type == RewardType.ADVANCE,
            Reward.status != RewardStatus.REJECTED,
        )
    )
    return LinkStats(visits=visits or 0, applications=applications or 0, contracts=contracts or 0)


@dataclass(frozen=True, slots=True)
class VisitDay:
    day: date
    count: int

    @property
    def day_label(self) -> str:
        return self.day.strftime("%d.%m.%Y")


async def get_visits_by_day(session: AsyncSession, agent_id: int) -> list[VisitDay]:
    """Переходы по ссылке агента по дням (по московскому времени), новые дни первыми."""
    day = func.date(func.timezone("Europe/Moscow", ReferralLinkVisit.created_at))
    rows = await session.execute(
        select(day, func.count())
        .where(ReferralLinkVisit.agent_id == agent_id)
        .group_by(day)
        .order_by(day.desc())
    )
    return [VisitDay(day=visit_day, count=count) for visit_day, count in rows.all()]


@dataclass(frozen=True, slots=True)
class ApplicationRow:
    client_name: str
    masked_phone: str
    created_at: datetime
    status: str


async def get_application_rows(session: AsyncSession, agent_id: int) -> list[ApplicationRow]:
    """Все заявки, оставленные по ссылке агента, с понятным статусом из Bitrix."""
    applications = (
        await session.scalars(
            select(ReferralApplication)
            .where(ReferralApplication.agent_id == agent_id)
            .order_by(ReferralApplication.created_at.desc())
        )
    ).all()
    return [
        ApplicationRow(
            client_name=application.full_name,
            masked_phone=masked_phone(application.phone_normalized),
            created_at=application.created_at,
            status=application_status_label(application.deal_stage_code),
        )
        for application in applications
    ]


@dataclass(frozen=True, slots=True)
class NetworkClientRow:
    """One client who generated income for this agent - either a direct
    client of theirs, or a client brought in several levels down their
    network, whose deal is generating an override for this agent."""

    client_name: str
    masked_phone: str
    created_at: datetime
    reward_summary: str
    stage: str
    reward_totals: str


def _reward_totals(rewards: list[Reward]) -> str:
    """Итог по клиенту (ТЗ): сколько выплачено и сколько ещё ожидается.
    Отклонённые начисления в сумму не входят."""
    paid = Decimal(0)
    expected = Decimal(0)
    for reward in rewards:
        if reward.amount is None:
            continue
        slug = payout_status_slug(reward)
        if slug == "paid":
            paid += reward.amount
        elif slug in ("pending", "scheduled"):
            expected += reward.amount
    if not paid and not expected:
        return "—"
    # Неразрывные пробелы: строка может переноситься только между "выплачено" и "ожидается".
    paid_label = f"Выплачено: {format_amount(paid)}".replace(" ", "\u00a0")
    expected_label = f"Ожидается: {format_amount(expected)}".replace(" ", "\u00a0")
    return f"{paid_label} · {expected_label}"


async def get_network_client_rows(session: AsyncSession, agent_id: int) -> list[NetworkClientRow]:
    """Every client this agent should see rewards for: their own direct
    clients (listed even with no reward yet), plus any client elsewhere in
    their network whose deal generated an override reward for them.

    Overrides live on Reward rows with this agent's id and an
    application_id pointing at someone else's client - a plain
    `Reward.agent_id == agent_id` query already covers both cases, so there
    is no need to walk the network tree here.
    """
    direct_applications = list(
        (
            await session.scalars(
                select(ReferralApplication).where(ReferralApplication.agent_id == agent_id)
            )
        ).all()
    )
    rewards = list((await session.scalars(select(Reward).where(Reward.agent_id == agent_id))).all())
    rewards_by_application: dict[int, list[Reward]] = defaultdict(list)
    for reward in rewards:
        rewards_by_application[reward.application_id].append(reward)

    direct_application_ids = {application.id for application in direct_applications}
    network_application_ids = set(rewards_by_application) - direct_application_ids
    network_applications = []
    if network_application_ids:
        network_applications = list(
            (
                await session.scalars(
                    select(ReferralApplication).where(
                        ReferralApplication.id.in_(network_application_ids)
                    )
                )
            ).all()
        )

    applications = direct_applications + network_applications
    applications.sort(key=lambda application: application.created_at, reverse=True)

    return [
        NetworkClientRow(
            client_name=application.full_name,
            masked_phone=masked_phone(application.phone_normalized),
            created_at=application.created_at,
            reward_summary=", ".join(
                f"{REWARD_TYPE_LABELS.get(r.reward_type, r.reward_type.value)}: "
                f"{STATUS_LABELS[payout_status_slug(r)]}"
                + (f" ({format_amount(r.amount)})" if r.amount is not None else "")
                for r in rewards_by_application.get(application.id, [])
            )
            or "Договор не заключен",
            stage=stage_label(application.deal_stage_code) or DEFAULT_STAGE_LABEL,
            reward_totals=_reward_totals(rewards_by_application.get(application.id, [])),
        )
        for application in applications
    ]


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


async def _fixation_is_active(session: AsyncSession, application: ReferralApplication) -> bool:
    """A client stays fixed to their agent forever once they've paid (a
    Reward exists), otherwise the fixation rots 180 days after the first
    application - after that, another agent may claim the same phone.
    """
    has_reward = (
        await session.scalar(
            select(Reward.id).where(Reward.application_id == application.id).limit(1)
        )
    ) is not None
    if has_reward:
        return True
    age = datetime.now(UTC) - application.created_at
    return age <= timedelta(days=FIXATION_EXPIRY_DAYS)


async def create_first_application(
    session: AsyncSession,
    agent: Agent,
    data: ApplicationInput,
    lead_delivery: LeadDeliveryGateway,
) -> tuple[ReferralApplication, bool]:
    phone = normalize_phone(data.phone)
    latest = await session.scalar(
        select(ReferralApplication)
        .where(ReferralApplication.phone_normalized == phone)
        .order_by(ReferralApplication.created_at.desc())
        .limit(1)
    )
    if latest is not None and await _fixation_is_active(session, latest):
        return latest, False

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
    await session.commit()
    await session.refresh(application)

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
