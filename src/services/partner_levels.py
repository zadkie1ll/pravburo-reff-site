import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pravburo_ref_common.database import session_factory
from pravburo_ref_common.models import (
    PartnerLevel,
    PartnerLevelMonth,
    Reward,
    RewardStageRate,
    RewardStatus,
    RewardType,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.core.telegram import send_partner_level_close_failed_notice

logger = logging.getLogger(__name__)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

QUARTERLY_BONUS_THRESHOLD = 15
QUARTERLY_BONUS_AMOUNT = Decimal("15000")
# Month that just ended -> which quarter (1-4) it completes.
QUARTER_FOR_CLOSING_MONTH = {3: 1, 6: 2, 9: 3, 12: 4}

# Upper bound of contracts-per-month for each level below Expert; anything
# past the last threshold is Expert. Matches руководитель's formula: 1 -> Старт,
# 2-3 -> Актив, 4-5 -> Про, 6+ -> Эксперт.
_LEVEL_UPPER_BOUNDS = [
    (1, PartnerLevel.START),
    (3, PartnerLevel.ACTIVE),
    (5, PartnerLevel.PRO),
]


def contracts_word(count: int) -> str:
    """Russian plural of "договор" for `count` - "1 договор", "3 договора",
    "5 договоров" (11-14 are always the "-ов" form, per the usual exception).
    """
    if count % 100 in (11, 12, 13, 14):
        return "договоров"
    if count % 10 == 1:
        return "договор"
    if count % 10 in (2, 3, 4):
        return "договора"
    return "договоров"


def level_for_contracts(count: int) -> PartnerLevel:
    for upper_bound, level in _LEVEL_UPPER_BOUNDS:
        if count <= upper_bound:
            return level
    return PartnerLevel.EXPERT


LEVEL_ORDER = [PartnerLevel.START, PartnerLevel.ACTIVE, PartnerLevel.PRO, PartnerLevel.EXPERT]
# First contract count that reaches each level - the flip side of
# _LEVEL_UPPER_BOUNDS, used to draw the cabinet's level-progress track.
LEVEL_MIN_CONTRACTS = {
    PartnerLevel.START: 0,
    PartnerLevel.ACTIVE: 2,
    PartnerLevel.PRO: 4,
    PartnerLevel.EXPERT: 6,
}
LEVEL_RANGE_LABELS = {
    PartnerLevel.START: "1",
    PartnerLevel.ACTIVE: "2–3",
    PartnerLevel.PRO: "4–5",
    PartnerLevel.EXPERT: "6+",
}
LEVEL_LABELS = {
    PartnerLevel.START: "Старт",
    PartnerLevel.ACTIVE: "Актив",
    PartnerLevel.PRO: "Про",
    PartnerLevel.EXPERT: "Эксперт",
}


@dataclass(frozen=True, slots=True)
class LevelSegment:
    from_level: PartnerLevel
    to_level: PartnerLevel
    fill_percent: int  # quantized to the nearest 10, for a fixed CSS class


@dataclass(frozen=True, slots=True)
class LevelProgress:
    level: PartnerLevel
    contracts_count: int
    segments: list[LevelSegment]
    next_level: PartnerLevel | None
    contracts_to_next: int | None


def _quantize_to_ten(fraction: float) -> int:
    return max(0, min(100, round(fraction * 10) * 10))


def build_level_progress(contracts_count: int) -> LevelProgress:
    level = level_for_contracts(contracts_count)
    segments = [
        LevelSegment(
            from_level=LEVEL_ORDER[index],
            to_level=LEVEL_ORDER[index + 1],
            fill_percent=_quantize_to_ten(
                (contracts_count - LEVEL_MIN_CONTRACTS[LEVEL_ORDER[index]])
                / (
                    LEVEL_MIN_CONTRACTS[LEVEL_ORDER[index + 1]]
                    - LEVEL_MIN_CONTRACTS[LEVEL_ORDER[index]]
                )
            ),
        )
        for index in range(len(LEVEL_ORDER) - 1)
    ]
    level_index = LEVEL_ORDER.index(level)
    if level_index + 1 < len(LEVEL_ORDER):
        next_level = LEVEL_ORDER[level_index + 1]
        contracts_to_next = LEVEL_MIN_CONTRACTS[next_level] - contracts_count
    else:
        next_level = None
        contracts_to_next = None
    return LevelProgress(
        level=level,
        contracts_count=contracts_count,
        segments=segments,
        next_level=next_level,
        contracts_to_next=contracts_to_next,
    )


async def get_current_month_progress(session: AsyncSession, agent_id: int) -> LevelProgress:
    """Live progress for the cabinet widget - unlike PartnerLevelMonth, this
    reads the CURRENT (still open) month's contracts, so it moves as new
    contracts come in. It's a preview, not the fixed level used for payouts,
    which is only set once run_monthly_level_close closes the month.
    """
    today = datetime.now(MOSCOW_TZ)
    start, end = _month_bounds(today.year, today.month)
    counts = await _count_contracts_by_agent(session, start, end)
    return build_level_progress(counts.get(agent_id, 0))


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=MOSCOW_TZ)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=MOSCOW_TZ)
    else:
        end = datetime(year, month + 1, 1, tzinfo=MOSCOW_TZ)
    return start, end


def previous_month(today: datetime) -> tuple[int, int]:
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


async def _count_contracts_by_agent(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[int, int]:
    rows = await session.execute(
        select(Reward.agent_id, func.count())
        .where(
            Reward.reward_type == RewardType.ADVANCE,
            Reward.status != RewardStatus.REJECTED,
            Reward.created_at >= start,
            Reward.created_at < end,
        )
        .group_by(Reward.agent_id)
    )
    return dict(rows.all())


async def _close_month(session: AsyncSession, year: int, month: int) -> None:
    """Fix each agent's level for `year`-`month` from their non-rejected
    ADVANCE rewards signed that month. Skips agents with 0 contracts (no row
    needed - absence means Старт) and rows an admin already hand-set
    (is_manual), so this can safely re-run without clobbering a correction.
    """
    start, end = _month_bounds(year, month)
    counts = await _count_contracts_by_agent(session, start, end)

    for agent_id, count in counts.items():
        existing = await session.scalar(
            select(PartnerLevelMonth).where(
                PartnerLevelMonth.agent_id == agent_id,
                PartnerLevelMonth.year == year,
                PartnerLevelMonth.month == month,
            )
        )
        if existing is not None and existing.is_manual:
            continue
        level = level_for_contracts(count)
        if existing is None:
            session.add(
                PartnerLevelMonth(
                    agent_id=agent_id,
                    year=year,
                    month=month,
                    contracts_count=count,
                    level=level,
                )
            )
        else:
            existing.contracts_count = count
            existing.level = level
    await session.commit()


async def _backfill_main_rewards(session: AsyncSession, year: int, month: int) -> None:
    """A MAIN reward's amount depends on the partner's level for the month
    their contract (the sibling ADVANCE reward, same deal_id+agent_id) was
    signed - unknowable until that month closes, which _close_month just did.
    Fill in `amount` for any MAIN reward left NULL at creation for that
    reason whose origin month is the one just closed.
    """
    start, end = _month_bounds(year, month)
    advance = aliased(Reward)
    stmt = (
        select(Reward)
        .join(
            advance,
            (advance.deal_id == Reward.deal_id)
            & (advance.agent_id == Reward.agent_id)
            & (advance.reward_type == RewardType.ADVANCE),
        )
        .where(
            Reward.reward_type == RewardType.MAIN,
            Reward.amount.is_(None),
            advance.created_at >= start,
            advance.created_at < end,
        )
    )
    rewards = (await session.scalars(stmt)).all()

    for reward in rewards:
        level_month = await session.scalar(
            select(PartnerLevelMonth).where(
                PartnerLevelMonth.agent_id == reward.agent_id,
                PartnerLevelMonth.year == year,
                PartnerLevelMonth.month == month,
            )
        )
        if level_month is None:
            logger.warning(
                "No partner_level_months row for agent_id=%s %s-%s, "
                "can't backfill main reward_id=%s",
                reward.agent_id,
                year,
                month,
                reward.id,
            )
            continue
        rate = await session.get(RewardStageRate, (RewardType.MAIN, level_month.level))
        if rate is not None:
            reward.amount = rate.amount
    await session.commit()


async def _close_quarter_if_due(session: AsyncSession, closed_year: int, closed_month: int) -> None:
    quarter = QUARTER_FOR_CLOSING_MONTH.get(closed_month)
    if quarter is None:
        return
    start, _ = _month_bounds(closed_year, closed_month - 2)
    _, end = _month_bounds(closed_year, closed_month)
    counts = await _count_contracts_by_agent(session, start, end)

    for agent_id, count in counts.items():
        if count < QUARTERLY_BONUS_THRESHOLD:
            continue
        reward = Reward(
            deal_id=f"quarterly:{agent_id}:{closed_year}Q{quarter}",
            application_id=None,
            agent_id=agent_id,
            reward_type=RewardType.QUARTERLY_BONUS,
            amount=QUARTERLY_BONUS_AMOUNT,
        )
        session.add(reward)
        try:
            await session.commit()
        except IntegrityError:
            # Already created on a previous run of this job for the same quarter.
            await session.rollback()


async def run_monthly_level_close() -> None:
    today = datetime.now(MOSCOW_TZ)
    year, month = previous_month(today)
    try:
        async with session_factory() as session:
            await _close_month(session, year, month)
            await _backfill_main_rewards(session, year, month)
            await _close_quarter_if_due(session, year, month)
    except Exception:
        logger.exception("Monthly partner-level close failed for %s-%02d", year, month)
        try:
            await send_partner_level_close_failed_notice(f"{year}-{month:02d}")
        except Exception:
            logger.exception("Failed to send partner-level-close-failure admin notice too")
