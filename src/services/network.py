from dataclasses import dataclass
from decimal import Decimal

from pravburo_ref_common.models import Agent, Reward, RewardType
from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased


@dataclass(frozen=True, slots=True)
class NetworkNode:
    id: int
    display_name: str
    email: str | None
    phone_normalized: str | None
    is_active: bool
    depth: int


@dataclass(frozen=True, slots=True)
class NetworkSummary:
    direct_invitees: int
    total_network_size: int
    override_paid: Decimal
    override_pending: Decimal


async def get_network_summary(session: AsyncSession, agent_id: int) -> NetworkSummary:
    direct_invitees = await session.scalar(
        select(func.count(Agent.id)).where(Agent.invited_by_agent_id == agent_id)
    )
    tree = await get_descendant_tree(session, agent_id)
    override_rows = await session.execute(
        select(Reward.amount, Reward.paid_at).where(
            Reward.agent_id == agent_id, Reward.reward_type == RewardType.OVERRIDE
        )
    )
    paid = Decimal(0)
    pending = Decimal(0)
    for amount, paid_at in override_rows:
        if amount is None:
            continue
        if paid_at is not None:
            paid += amount
        else:
            pending += amount
    return NetworkSummary(
        direct_invitees=direct_invitees or 0,
        total_network_size=max(len(tree) - 1, 0),
        override_paid=paid,
        override_pending=pending,
    )


async def search_agents(session: AsyncSession, query: str, limit: int = 20) -> list[Agent]:
    query = query.strip()
    if not query:
        return []
    pattern = f"%{query}%"
    rows = await session.scalars(
        select(Agent)
        .where(or_(Agent.display_name.ilike(pattern), Agent.email.ilike(pattern)))
        .order_by(Agent.display_name)
        .limit(limit)
    )
    return list(rows.all())


async def get_descendant_tree(session: AsyncSession, root_agent_id: int) -> list[NetworkNode]:
    """Everyone under root_agent_id in the invite chain, root first, depth-first.

    No depth cap here - this is for the admin org-chart view, not payouts
    (override payouts are separately capped in bounty's create_reward_once).
    """
    base = (
        select(
            Agent.id,
            Agent.display_name,
            Agent.email,
            Agent.phone_normalized,
            Agent.is_active,
            literal(0).label("depth"),
        )
        .where(Agent.id == root_agent_id)
        .cte(name="network_tree", recursive=True)
    )
    downline = aliased(Agent)
    recursive = select(
        downline.id,
        downline.display_name,
        downline.email,
        downline.phone_normalized,
        downline.is_active,
        (base.c.depth + 1).label("depth"),
    ).join(base, downline.invited_by_agent_id == base.c.id)
    tree = base.union_all(recursive)

    rows = await session.execute(select(tree).order_by(tree.c.depth, tree.c.display_name))
    return [
        NetworkNode(
            id=row.id,
            display_name=row.display_name,
            email=row.email,
            phone_normalized=row.phone_normalized,
            is_active=row.is_active,
            depth=row.depth,
        )
        for row in rows
    ]
