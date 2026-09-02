from dataclasses import dataclass

from pravburo_ref_common.models import ReferralApplication, Reward, RewardStatus, RewardType
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

REWARD_TYPE_LABELS = {
    RewardType.ADVANCE: "Аванс",
    RewardType.MAIN: "Основная выплата",
    RewardType.BONUS_FULL_PAYMENT: "Бонус за 100% оплату",
    RewardType.QUARTERLY_BONUS: "Квартальный бонус",
}

STATUS_LABELS = {
    "pending": "Ожидает решения",
    "scheduled": "Запланировано",
    "paid": "Выплачено",
    "rejected": "Отклонено",
}


def payout_status_slug(reward: Reward) -> str:
    if reward.status == RewardStatus.REJECTED:
        return "rejected"
    if reward.status == RewardStatus.PENDING:
        return "pending"
    return "paid" if reward.paid_at is not None else "scheduled"


def format_amount(amount) -> str:
    if amount is None:
        return "—"
    return f"{amount:,.0f} ₽".replace(",", " ")


@dataclass(slots=True)
class PayoutFilters:
    month: str = ""
    reward_type: str = ""
    status: str = ""


@dataclass(slots=True)
class PayoutRow:
    reward: Reward
    client_name: str
    type_label: str
    status_label: str
    status_slug: str
    amount_label: str
    payout_date_label: str


async def get_payout_rows(
    session: AsyncSession, agent_id: int, filters: PayoutFilters
) -> list[PayoutRow]:
    statement = (
        select(Reward, ReferralApplication.full_name)
        .join(ReferralApplication, ReferralApplication.id == Reward.application_id)
        .where(Reward.agent_id == agent_id)
        .order_by(Reward.created_at.desc())
    )
    if filters.reward_type:
        statement = statement.where(Reward.reward_type == filters.reward_type)
    if filters.month:
        try:
            year_str, month_str = filters.month.split("-", 1)
            year, month = int(year_str), int(month_str)
        except ValueError:
            year = month = None
        if year and month:
            statement = statement.where(
                extract("year", Reward.paid_at) == year,
                extract("month", Reward.paid_at) == month,
            )

    rows = (await session.execute(statement)).all()
    result = []
    for reward, full_name in rows:
        slug = payout_status_slug(reward)
        if filters.status and filters.status != slug:
            continue
        result.append(
            PayoutRow(
                reward=reward,
                client_name=full_name,
                type_label=REWARD_TYPE_LABELS.get(reward.reward_type, reward.reward_type.value),
                status_label=STATUS_LABELS.get(slug, slug),
                status_slug=slug,
                amount_label=format_amount(reward.amount),
                payout_date_label=reward.paid_at.strftime("%d.%m.%Y") if reward.paid_at else "—",
            )
        )
    return result
