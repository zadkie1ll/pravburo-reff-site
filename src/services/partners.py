from dataclasses import dataclass
from decimal import Decimal

from pravburo_ref_common.models import Agent, ReferralApplication, Reward
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class PartnerRow:
    agent: Agent
    client_count: int
    total_paid: Decimal


@dataclass(frozen=True, slots=True)
class PartnersPage:
    rows: list[PartnerRow]
    page: int
    total_pages: int
    total_count: int


def _search_filter(stmt, query: str):
    pattern = f"%{query}%"
    return stmt.where(
        or_(
            Agent.display_name.ilike(pattern),
            Agent.email.ilike(pattern),
            Agent.phone_normalized.ilike(pattern),
        )
    )


async def list_partners(session: AsyncSession, q: str = "", page: int = 1) -> PartnersPage:
    query = q.strip()
    page = max(page, 1)

    count_stmt = select(func.count(Agent.id))
    if query:
        count_stmt = _search_filter(count_stmt, query)
    total_count = await session.scalar(count_stmt) or 0
    total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, total_pages)

    stmt = select(Agent).order_by(Agent.created_at.desc())
    if query:
        stmt = _search_filter(stmt, query)
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
    paid_totals = dict(
        (
            await session.execute(
                select(Reward.agent_id, func.coalesce(func.sum(Reward.amount), 0))
                .where(Reward.agent_id.in_(agent_ids), Reward.paid_at.is_not(None))
                .group_by(Reward.agent_id)
            )
        ).all()
    )

    rows = [
        PartnerRow(
            agent=agent,
            client_count=client_counts.get(agent.id, 0),
            total_paid=paid_totals.get(agent.id, Decimal(0)),
        )
        for agent in agents
    ]
    return PartnersPage(rows=rows, page=page, total_pages=total_pages, total_count=total_count)
