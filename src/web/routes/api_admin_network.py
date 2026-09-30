"""Admin: network override rates (and, next to them, the network tree)."""

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, NetworkOverrideRate
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.network import (
    build_network_tree,
    get_descendant_tree,
    network_tree_to_dict,
    search_agents,
)
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError

router = APIRouter(prefix="/api/v1/site/admin/network", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]

LEVEL_LABELS = {
    1: "1 уровень (прямой пригласивший)",
    2: "2 уровень (пригласивший пригласившего)",
    3: "3 уровень (только для цепочки из партнёров)",
}


class RateOut(BaseModel):
    level: int
    label: str
    amount: str


class RatesResponse(BaseModel):
    rates: list[RateOut]


class RatesRequest(BaseModel):
    # Text, not numbers: the admin's input is validated here with the messages the form shows.
    amount_1: str = Field(max_length=32)
    amount_2: str = Field(max_length=32)
    amount_3: str = Field(max_length=32)


async def _rates(session: AsyncSession) -> RatesResponse:
    rows = (
        await session.scalars(select(NetworkOverrideRate).order_by(NetworkOverrideRate.level))
    ).all()
    return RatesResponse(
        rates=[
            RateOut(
                level=row.level,
                label=LEVEL_LABELS.get(row.level, f"{row.level} уровень"),
                amount=str(row.amount),
            )
            for row in rows
        ]
    )


def _parse_amount(text: str, field: str) -> Decimal:
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite():
        raise ApiError(400, "validation_error", "Укажите корректную сумму", {field: "invalid"})
    if value < 0:
        raise ApiError(
            400, "validation_error", "Сумма не может быть отрицательной", {field: "negative"}
        )
    return value


@router.get("/rates", response_model=RatesResponse)
async def rates(_: ApiAdmin, session: Session) -> RatesResponse:
    return await _rates(session)


@router.post("/rates", response_model=RatesResponse, dependencies=[CsrfProtected])
async def save_rates(_: ApiAdmin, session: Session, body: RatesRequest) -> RatesResponse:
    new_values = {
        1: _parse_amount(body.amount_1, "amount_1"),
        2: _parse_amount(body.amount_2, "amount_2"),
        3: _parse_amount(body.amount_3, "amount_3"),
    }
    rows = (await session.scalars(select(NetworkOverrideRate))).all()
    for row in rows:
        if row.level in new_values:
            row.amount = new_values[row.level]
    await session.commit()
    return await _rates(session)


class AgentMatch(BaseModel):
    id: int
    label: str
    email: str | None


class TreeNodeOut(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    is_active: bool
    children: list["TreeNodeOut"]


class RootAgent(BaseModel):
    id: int
    label: str


class NetworkTreeResponse(BaseModel):
    matches: list[AgentMatch]
    root: RootAgent | None
    tree: TreeNodeOut | None


def _label(agent: Agent) -> str:
    return agent.display_name or agent.email or f"#{agent.id}"


@router.get("/tree", response_model=NetworkTreeResponse)
async def network_tree(
    _: ApiAdmin,
    session: Session,
    q: Annotated[str, Query()] = "",
    root: Annotated[int | None, Query()] = None,
) -> NetworkTreeResponse:
    """Search results for ``q`` and, when ``root`` is given, that partner's whole downline."""
    matches = await search_agents(session, q) if q else []
    root_agent = await session.get(Agent, root) if root else None
    nodes = await get_descendant_tree(session, root_agent.id) if root_agent else []
    tree = build_network_tree(nodes)
    return NetworkTreeResponse(
        matches=[
            AgentMatch(id=agent.id, label=_label(agent), email=agent.email) for agent in matches
        ],
        root=RootAgent(id=root_agent.id, label=_label(root_agent)) if root_agent else None,
        tree=TreeNodeOut.model_validate(network_tree_to_dict(tree)) if tree else None,
    )
