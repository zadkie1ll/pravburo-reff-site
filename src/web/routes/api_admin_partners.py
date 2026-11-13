"""Admin: partners list, notes, blocking."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin_partners import PartnerInput, create_partner, edit_partner
from src.services.partners import STATUS_LABELS, PartnerRow, list_partners
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.api_schemas import OkResponse, OptionOut

router = APIRouter(prefix="/api/v1/site/admin/partners", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PartnerOut(BaseModel):
    id: int
    display_name: str
    email: str | None
    phone: str | None
    is_active: bool
    is_admin: bool
    blocked_reason: str | None
    client_count: int
    # Kept as text exactly as the database sums it (the old page printed it the same way).
    total_paid: str
    payout_details: str | None
    admin_note: str | None


class PartnersResponse(BaseModel):
    rows: list[PartnerOut]
    page: int
    total_pages: int
    total_count: int
    statuses: list[OptionOut]


class NoteRequest(BaseModel):
    note: str = Field(default="", max_length=2000)


class BlockRequest(BaseModel):
    reason: str = Field(max_length=1000)


class PartnerProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=20)
    employment_format: EmploymentFormat
    payout_details: str = Field(min_length=1, max_length=200)
    inn: str = Field(default="", max_length=12)
    admin_note: str = Field(default="", max_length=2000)


class PartnerCreateRequest(PartnerProfileRequest):
    email: str | None = Field(default=None, max_length=254)
    # Leave room for a newline and the automatically generated password note.
    admin_note: str = Field(default="", max_length=1983)


class PartnerDetails(BaseModel):
    id: int
    display_name: str
    email: str | None
    phone: str | None
    employment_format: EmploymentFormat | None
    payout_details: str | None
    inn: str | None
    admin_note: str | None
    is_admin: bool


def _details(agent: Agent) -> PartnerDetails:
    return PartnerDetails(
        id=agent.id,
        display_name=agent.display_name,
        email=agent.email,
        phone=agent.phone_normalized,
        employment_format=agent.employment_format,
        payout_details=agent.payout_details,
        inn=agent.inn,
        admin_note=agent.admin_note,
        is_admin=agent.role == AgentRole.ADMIN,
    )


def _row(row: PartnerRow) -> PartnerOut:
    agent = row.agent
    return PartnerOut(
        id=agent.id,
        display_name=agent.display_name,
        email=agent.email,
        phone=agent.phone_normalized,
        is_active=agent.is_active,
        is_admin=agent.role == AgentRole.ADMIN,
        blocked_reason=agent.blocked_reason,
        client_count=row.client_count,
        total_paid=str(row.total_paid),
        payout_details=agent.payout_details,
        admin_note=agent.admin_note,
    )


async def _agent(session: AsyncSession, agent_id: int) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise ApiError(404, "not_found", "Партнёр не найден")
    return agent


@router.get("", response_model=PartnersResponse)
async def partners(
    _: ApiAdmin,
    session: Session,
    q: Annotated[str, Query()] = "",
    status: Annotated[Literal["active", "blocked"] | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
) -> PartnersResponse:
    result = await list_partners(session, q, status or "", page)
    return PartnersResponse(
        rows=[_row(row) for row in result.rows],
        page=result.page,
        total_pages=result.total_pages,
        total_count=result.total_count,
        statuses=[OptionOut(value=value, label=label) for value, label in STATUS_LABELS.items()],
    )


@router.post("/{agent_id}/note", response_model=OkResponse, dependencies=[CsrfProtected])
async def save_note(_: ApiAdmin, session: Session, agent_id: int, body: NoteRequest) -> OkResponse:
    agent = await _agent(session, agent_id)
    agent.admin_note = body.note.strip() or None
    await session.commit()
    return OkResponse()


@router.post("", response_model=PartnerDetails, status_code=201, dependencies=[CsrfProtected])
async def create(admin: ApiAdmin, session: Session, body: PartnerCreateRequest) -> PartnerDetails:
    try:
        data = PartnerInput(**body.model_dump(exclude={"email"}))
        agent = await create_partner(session, admin.id, body.email, data)
    except ValueError as exc:
        raise ApiError(400, "partner_invalid", str(exc)) from exc
    return _details(agent)


@router.get("/{agent_id}", response_model=PartnerDetails)
async def details(_: ApiAdmin, session: Session, agent_id: int) -> PartnerDetails:
    return _details(await _agent(session, agent_id))


@router.post("/{agent_id}", response_model=PartnerDetails, dependencies=[CsrfProtected])
async def edit(
    admin: ApiAdmin, session: Session, agent_id: int, body: PartnerProfileRequest
) -> PartnerDetails:
    agent = await _agent(session, agent_id)
    try:
        agent = await edit_partner(session, admin.id, agent, PartnerInput(**body.model_dump()))
    except ValueError as exc:
        raise ApiError(400, "partner_invalid", str(exc)) from exc
    return _details(agent)


@router.post("/{agent_id}/block", response_model=OkResponse, dependencies=[CsrfProtected])
async def block(_: ApiAdmin, session: Session, agent_id: int, body: BlockRequest) -> OkResponse:
    reason = body.reason.strip()
    if not reason:
        raise ApiError(
            400, "validation_error", "Укажите причину блокировки", {"reason": "required"}
        )
    agent = await _agent(session, agent_id)
    if agent.role == AgentRole.ADMIN:
        raise ApiError(400, "cannot_block_admin", "Администратора заблокировать нельзя")
    agent.is_active = False
    agent.blocked_reason = reason
    await session.commit()
    return OkResponse()


@router.post("/{agent_id}/unblock", response_model=OkResponse, dependencies=[CsrfProtected])
async def unblock(_: ApiAdmin, session: Session, agent_id: int) -> OkResponse:
    agent = await _agent(session, agent_id)
    agent.is_active = True
    agent.blocked_reason = None
    await session.commit()
    return OkResponse()
