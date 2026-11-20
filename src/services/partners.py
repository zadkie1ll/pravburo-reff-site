from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from pravburo_ref_common.models import Agent, ReferralApplication, Reward, RewardStatus
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin_payouts import get_overdue_days

PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class PartnerRow:
    agent: Agent
    client_count: int
    total_paid: Decimal
    overdue_payout_count: int


@dataclass(frozen=True, slots=True)
class PartnersPage:
    rows: list[PartnerRow]
    page: int
    total_pages: int
    total_count: int


STATUS_LABELS = {"active": "Активные", "blocked": "Заблокированные"}


def _search_filter(stmt, query: str):
    pattern = f"%{query}%"
    return stmt.where(
        or_(
            Agent.display_name.ilike(pattern),
            Agent.email.ilike(pattern),
            Agent.phone_normalized.ilike(pattern),
        )
    )


def _status_filter(stmt, status: str):
    if status == "active":
        return stmt.where(Agent.is_active.is_(True))
    if status == "blocked":
        return stmt.where(Agent.is_active.is_(False))
    return stmt


async def list_partners(
    session: AsyncSession, q: str = "", status: str = "", page: int = 1
) -> PartnersPage:
    query = q.strip()
    page = max(page, 1)

    count_stmt = select(func.count(Agent.id))
    if query:
        count_stmt = _search_filter(count_stmt, query)
    count_stmt = _status_filter(count_stmt, status)
    total_count = await session.scalar(count_stmt) or 0
    total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, total_pages)

    stmt = select(Agent).order_by(Agent.created_at.desc())
    if query:
        stmt = _search_filter(stmt, query)
    stmt = _status_filter(stmt, status)
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    agents = (await session.scalars(stmt)).all()
    if not agents:
        return PartnersPage(rows=[], page=page, total_pages=total_pages, total_count=total_count)

    agent_ids = [agent.id for agent in agents]

    client_counts = dict(
        (
            await session.execute(
                select(ReferralApplication.agent_id, func.count(ReferralApplication.id))
                .where(ReferralApplication.agent_id.in_(agent_ids))
                .group_by(ReferralApplication.agent_id)
            )
        ).all()
    )
    today = datetime.now(UTC).date()
    overdue_days = await get_overdue_days(session)
    # For payouts without a specific deadline, the calendar uses the UTC decision date.
    decision_cutoff = datetime.combine(today - timedelta(days=overdue_days), time.min, UTC)
    paid = Reward.paid_at.is_not(None)
    overdue = and_(
        Reward.status == RewardStatus.APPROVED,
        Reward.paid_at.is_(None),
        or_(
            Reward.payout_due_date < today,
            and_(Reward.payout_due_date.is_(None), Reward.decided_at < decision_cutoff),
        ),
    )
    payout_totals = {
        agent_id: (total_paid, overdue_count)
        for agent_id, total_paid, overdue_count in (
            await session.execute(
                select(
                    Reward.agent_id,
                    func.coalesce(func.sum(Reward.amount).filter(paid), 0),
                    func.count().filter(overdue),
                )
                .where(Reward.agent_id.in_(agent_ids), or_(paid, overdue))
                .group_by(Reward.agent_id)
            )
        ).all()
    }

    rows = []
    for agent in agents:
        total_paid, overdue_payout_count = payout_totals.get(agent.id, (Decimal(0), 0))
        rows.append(
            PartnerRow(
                agent=agent,
                client_count=client_counts.get(agent.id, 0),
                total_paid=total_paid,
                overdue_payout_count=overdue_payout_count,
            )
        )
    return PartnersPage(rows=rows, page=page, total_pages=total_pages, total_count=total_count)
