import calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from pravburo_ref_common.models import (
    Agent,
    PayoutSettings,
    ReferralApplication,
    Reward,
    RewardStatus,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.payouts import REWARD_TYPE_LABELS, format_amount

STATUS_LABELS = {
    "pending": "Ожидает решения",
    "scheduled": "Запланировано",
    "overdue": "Просрочено",
    "paid": "Выплачено",
    "rejected": "Отклонено",
}

DEFAULT_OVERDUE_DAYS = 14

MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} {year}"


async def get_overdue_days(session: AsyncSession) -> int:
    settings = await session.get(PayoutSettings, 1)
    return settings.overdue_days if settings is not None else DEFAULT_OVERDUE_DAYS


async def set_overdue_days(session: AsyncSession, value: int) -> None:
    settings = await session.get(PayoutSettings, 1)
    if settings is None:
        settings = PayoutSettings(id=1, overdue_days=value)
        session.add(settings)
    else:
        settings.overdue_days = value
    await session.commit()


@dataclass(slots=True)
class PayoutRow:
    reward: Reward
    agent_name: str
    client_name: str
    type_label: str
    amount_label: str
    status_slug: str
    status_label: str
    target_date: date | None


def _status_slug(reward: Reward, overdue_days: int, today: date) -> str:
    if reward.status == RewardStatus.REJECTED:
        return "rejected"
    if reward.status == RewardStatus.PENDING:
        return "pending"
    if reward.paid_at is not None:
        return "paid"
    if reward.decided_at is not None:
        due = reward.decided_at.date() + timedelta(days=overdue_days)
        if due < today:
            return "overdue"
    return "scheduled"


def _target_date(reward: Reward, overdue_days: int) -> date | None:
    if reward.paid_at is not None:
        return reward.paid_at.date()
    if reward.decided_at is not None:
        return reward.decided_at.date() + timedelta(days=overdue_days)
    return None


async def list_payout_rows(
    session: AsyncSession, status: str = "", overdue_days: int | None = None
) -> list[PayoutRow]:
    if overdue_days is None:
        overdue_days = await get_overdue_days(session)
    today = datetime.now(UTC).date()

    stmt = (
        select(Reward, ReferralApplication.full_name, Agent.display_name, Agent.email)
        .join(ReferralApplication, ReferralApplication.id == Reward.application_id)
        .join(Agent, Agent.id == Reward.agent_id)
        .order_by(Reward.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    result = []
    for reward, client_name, agent_display_name, agent_email in rows:
        slug = _status_slug(reward, overdue_days, today)
        if status and status != slug:
            continue
        result.append(
            PayoutRow(
                reward=reward,
                agent_name=agent_display_name or agent_email or f"#{reward.agent_id}",
                client_name=client_name,
                type_label=REWARD_TYPE_LABELS.get(reward.reward_type, reward.reward_type.value),
                amount_label=format_amount(reward.amount),
                status_slug=slug,
                status_label=STATUS_LABELS.get(slug, slug),
                target_date=_target_date(reward, overdue_days),
            )
        )
    return result


@dataclass(slots=True)
class CalendarDay:
    date: date
    in_month: bool
    is_today: bool
    rows: list[PayoutRow]


def build_calendar(
    rows: list[PayoutRow], year: int, month: int, today: date
) -> list[list[CalendarDay]]:
    by_date: dict[date, list[PayoutRow]] = {}
    for row in rows:
        if row.target_date is not None:
            by_date.setdefault(row.target_date, []).append(row)

    cal = calendar.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append(
            [
                CalendarDay(
                    date=day,
                    in_month=day.month == month,
                    is_today=day == today,
                    rows=by_date.get(day, []),
                )
                for day in week
            ]
        )
    return weeks


async def mark_paid(session: AsyncSession, reward_id: int) -> bool:
    reward = await session.get(Reward, reward_id)
    if reward is None or reward.status != RewardStatus.APPROVED or reward.paid_at is not None:
        return False
    reward.paid_at = datetime.now(UTC)
    await session.commit()
    return True
