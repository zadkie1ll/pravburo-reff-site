from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from pravburo_ref_common.models import ReferralApplication, Reward, RewardStatus, RewardType
from sqlalchemy import exists, extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.deal_stages import DEFAULT_PAYOUT_STAGE_LABEL, PAYOUT_STAGE_LABELS

REWARD_TYPE_LABELS = {
    RewardType.ADVANCE: "Аванс",
    RewardType.MAIN: "Основная выплата",
    RewardType.OVERRIDE: "Бонус за сеть",
    RewardType.BONUS_FULL_PAYMENT: "Бонус за 100% оплату",
    RewardType.QUARTERLY_BONUS: "Квартальный бонус",
}

STATUS_LABELS = {
    "pending": "Ожидает решения",
    "scheduled": "Запланировано",
    "paid": "Выплачено",
    "rejected": "Отклонено",
}


# Статусы страницы "Выплаты" для партнёра: этапы до договора (из Bitrix, выплаты ещё нет)
# и состояние самой выплаты. Для партнёра "ждёт решения админа" = "Запланировано".
PAGE_STATUS_LABELS = {
    "analysis": DEFAULT_PAYOUT_STAGE_LABEL,
    "deposit": PAYOUT_STAGE_LABELS["UC_4FX5NE"],
    "ignored": PAYOUT_STAGE_LABELS["UC_1BEALQ"],
    "scheduled": "Запланировано",
    "paid": "Выплачено",
    "rejected": "Отклонено",
}
STAGE_STATUS_SLUGS = {"UC_4FX5NE": "deposit", "UC_1BEALQ": "ignored"}


def payout_status_slug(reward: Reward) -> str:
    if reward.status == RewardStatus.REJECTED:
        return "rejected"
    if reward.status == RewardStatus.PENDING:
        return "pending"
    return "paid" if reward.paid_at is not None else "scheduled"


def page_status_slug(reward: Reward) -> str:
    slug = payout_status_slug(reward)
    return "scheduled" if slug == "pending" else slug


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
    reward: Reward | None  # None - у клиента ещё нет выплаты (он на этапе до договора)
    client_name: str
    type_label: str
    status_label: str
    status_slug: str
    amount_label: str
    payout_date_label: str
    rejection_reason: str = ""


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

    status_filter = "scheduled" if filters.status == "pending" else filters.status  # старые ссылки

    rows = (await session.execute(statement)).all()
    result = []
    for reward, full_name in rows:
        slug = page_status_slug(reward)
        if status_filter and status_filter != slug:
            continue
        result.append(
            PayoutRow(
                reward=reward,
                client_name=full_name,
                type_label=REWARD_TYPE_LABELS.get(reward.reward_type, reward.reward_type.value),
                status_label=PAGE_STATUS_LABELS[slug],
                status_slug=slug,
                amount_label=format_amount(reward.amount),
                payout_date_label=reward.paid_at.strftime("%d.%m.%Y") if reward.paid_at else "—",
                rejection_reason=(reward.rejection_reason or "") if slug == "rejected" else "",
            )
        )

    # Клиенты без выплаты: показываем этап до договора. Фильтры по месяцу выплаты и по типу
    # выплаты к ним не применимы, поэтому при включённом фильтре такие строки скрыты.
    if not filters.month and not filters.reward_type:
        has_reward = exists().where(
            Reward.application_id == ReferralApplication.id, Reward.agent_id == agent_id
        )
        applications = (
            await session.scalars(
                select(ReferralApplication)
                .where(ReferralApplication.agent_id == agent_id, ~has_reward)
                .order_by(ReferralApplication.created_at.desc())
            )
        ).all()
        for application in applications:
            slug = STAGE_STATUS_SLUGS.get(application.deal_stage_code or "", "analysis")
            if status_filter and status_filter != slug:
                continue
            result.append(
                PayoutRow(
                    reward=None,
                    client_name=application.full_name,
                    type_label="—",
                    status_label=PAGE_STATUS_LABELS[slug],
                    status_slug=slug,
                    amount_label="—",
                    payout_date_label="—",
                )
            )
    return result


@dataclass(slots=True)
class PendingGroup:
    label: str
    amount_label: str


@dataclass(slots=True)
class FinanceSummary:
    total_paid_label: str
    this_month_label: str
    pending_total_label: str
    pending_groups: list[PendingGroup]


def build_finance_summary(rewards: list[Reward]) -> FinanceSummary:
    total_paid = Decimal(0)
    this_month = Decimal(0)
    pending_by_slug: dict[str, Decimal] = {}
    now = datetime.now(UTC)

    for reward in rewards:
        if reward.amount is None:
            continue
        if reward.paid_at is not None:
            total_paid += reward.amount
            if reward.paid_at.year == now.year and reward.paid_at.month == now.month:
                this_month += reward.amount
            continue
        slug = payout_status_slug(reward)
        if slug in ("pending", "scheduled"):
            pending_by_slug[slug] = pending_by_slug.get(slug, Decimal(0)) + reward.amount

    pending_labels = {
        "pending": "Ожидает подтверждения",
        "scheduled": "Ждём выплаты",
    }
    pending_groups = [
        PendingGroup(label=pending_labels[slug], amount_label=format_amount(amount))
        for slug, amount in pending_by_slug.items()
        if amount
    ]
    pending_total = sum(pending_by_slug.values(), Decimal(0))

    return FinanceSummary(
        total_paid_label=format_amount(total_paid),
        this_month_label=format_amount(this_month),
        pending_total_label=format_amount(pending_total),
        pending_groups=pending_groups,
    )
