from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from pravburo_ref_common.models import Agent, ReferralApplication, Reward, RewardType
from sqlalchemy import BigInteger, cast, func, literal, null, or_, select
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
    parent_id: int | None


@dataclass(frozen=True, slots=True)
class NetworkTreeNode:
    node: NetworkNode
    children: list["NetworkTreeNode"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NetworkSummary:
    direct_invitees: int
    total_network_size: int
    override_paid: Decimal
    override_pending: Decimal


@dataclass(frozen=True, slots=True)
class NetworkBranchEarnings:
    """Override earnings attributed to one direct sub-agent's branch of the
    network, so a payout several levels down doesn't get silently lumped
    into one undifferentiated total for the root agent."""

    agent_id: int
    display_name: str
    paid: Decimal
    pending: Decimal


async def get_network_summary(session: AsyncSession, agent_id: int) -> NetworkSummary:
    direct_invitees = await session.scalar(
        select(func.count(ReferralApplication.id)).where(ReferralApplication.agent_id == agent_id)
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


async def get_network_earnings_by_branch(
    session: AsyncSession, agent_id: int
) -> list[NetworkBranchEarnings]:
    """Override earnings this agent has received, grouped by which direct
    sub-agent's branch actually generated them.

    Without this, an override earned three levels down (agent brought agent
    brought agent brought a paying client) shows up as just one more number
    added to the root agent's total, with no way to tell which of their
    direct invitees' branches it came from.
    """
    tree = await get_descendant_tree(session, agent_id)
    if len(tree) <= 1:
        return []
    node_by_id = {node.id: node for node in tree}
    branch_root_by_id: dict[int, int] = {}
    for node in tree:
        if node.depth == 1:
            branch_root_by_id[node.id] = node.id
        elif node.parent_id in branch_root_by_id:
            branch_root_by_id[node.id] = branch_root_by_id[node.parent_id]

    rows = await session.execute(
        select(Reward.amount, Reward.paid_at, ReferralApplication.agent_id)
        .join(ReferralApplication, Reward.application_id == ReferralApplication.id)
        .where(Reward.agent_id == agent_id, Reward.reward_type == RewardType.OVERRIDE)
    )
    paid_by_branch: dict[int, Decimal] = defaultdict(Decimal)
    pending_by_branch: dict[int, Decimal] = defaultdict(Decimal)
    for amount, paid_at, source_agent_id in rows:
        if amount is None:
            continue
        branch_root = branch_root_by_id.get(source_agent_id)
        if branch_root is None:
            continue
        if paid_at is not None:
            paid_by_branch[branch_root] += amount
        else:
            pending_by_branch[branch_root] += amount

    branch_ids = paid_by_branch.keys() | pending_by_branch.keys()
    branches = [
        NetworkBranchEarnings(
            agent_id=root_id,
            display_name=node_by_id[root_id].display_name
            or node_by_id[root_id].email
            or f"#{root_id}",
            paid=paid_by_branch.get(root_id, Decimal(0)),
            pending=pending_by_branch.get(root_id, Decimal(0)),
        )
        for root_id in branch_ids
    ]
    branches.sort(key=lambda b: b.display_name.lower())
    return branches


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
            cast(null(), BigInteger).label("parent_id"),
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
        base.c.id.label("parent_id"),
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
            parent_id=row.parent_id,
        )
        for row in rows
    ]


def build_network_tree(nodes: list[NetworkNode]) -> NetworkTreeNode | None:
    """Turn the flat (depth, parent_id) list from get_descendant_tree into an
    actual nested structure, for rendering as a connected org-chart rather
    than an indented list.
    """
    if not nodes:
        return None
    tree_nodes = {node.id: NetworkTreeNode(node=node) for node in nodes}
    root: NetworkTreeNode | None = None
    for node in nodes:
        tree_node = tree_nodes[node.id]
        if node.parent_id is None:
            root = tree_node
        elif node.parent_id in tree_nodes:
            tree_nodes[node.parent_id].children.append(tree_node)
    return root


def network_tree_to_dict(tree_node: NetworkTreeNode) -> dict:
    """JSON-serializable form for the D3 tree visualization
    (static/network-tree.js expects this exact shape)."""
    node = tree_node.node
    return {
        "id": node.id,
        "name": node.display_name or node.email or f"#{node.id}",
        "email": node.email,
        "phone": node.phone_normalized,
        "is_active": node.is_active,
        "children": [network_tree_to_dict(child) for child in tree_node.children],
    }
