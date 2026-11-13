"""Explicit admin management of existing Bitrix clients; never creates CRM leads."""

from decimal import Decimal
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, ExistingClientImport, ReferralApplication, Reward
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.bitrix_links import entity_link, parse_deal_reference
from src.services.existing_clients import ExistingClientConflict, import_existing_client
from src.services.payouts import payout_status_slug
from src.site.crm_client import CRMClient
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError

router = APIRouter(prefix="/api/v1/site/admin/clients", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]
DealId = Annotated[str, Field(pattern=r"^[1-9][0-9]{0,63}$")]


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: int = Field(gt=0)
    deal_id: str = Field(min_length=1, max_length=1000)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=20)
    admin_note: str = Field(default="", max_length=2000)
    current_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    @field_validator("deal_id")
    @classmethod
    def normalize_deal(cls, value: str) -> str:
        return parse_deal_reference(value)


class ClientOut(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    agent_email: str | None
    full_name: str
    phone: str
    bitrix_deal_id: str
    bitrix_deal_url: str
    stage_label: str
    current_amount: str | None
    current_status: str | None
    admin_note: str | None
    created_at_label: str


class ClientsList(BaseModel):
    rows: list[ClientOut]
    page: int
    total_pages: int
    total_count: int


def _row(
    record, application, agent, reward, stage_names: dict[str, str] | None = None
) -> ClientOut:
    return ClientOut(
        id=application.id,
        agent_id=agent.id,
        agent_name=agent.display_name,
        agent_email=agent.email,
        full_name=application.full_name,
        phone=application.phone_normalized,
        bitrix_deal_id=record.deal_id,
        bitrix_deal_url=entity_link("deal", record.deal_id),
        stage_label=(stage_names or {}).get(
            application.deal_stage_code, "Название этапа недоступно"
        ),
        current_amount=str(reward.amount) if reward is not None else None,
        current_status=payout_status_slug(reward) if reward is not None else None,
        admin_note=record.admin_note,
        created_at_label=record.created_at.strftime("%d.%m.%Y %H:%M"),
    )


def _query():
    return (
        select(ExistingClientImport, ReferralApplication, Agent, Reward)
        .join(ReferralApplication, ReferralApplication.id == ExistingClientImport.application_id)
        .join(Agent, Agent.id == ReferralApplication.agent_id)
        .outerjoin(Reward, Reward.id == ExistingClientImport.current_reward_id)
    )


async def _snapshot(deal_id: str) -> dict:
    try:
        snapshot = await CRMClient().get_existing_client(deal_id)
        if snapshot.get("deal_id") != deal_id or not snapshot.get("stage_code"):
            raise ValueError("Не удалось определить текущий этап сделки")
        return snapshot
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 404}:
            raise ApiError(
                404, "deal_not_found", "Сделка не найдена или не относится к клиентской воронке"
            ) from exc
        raise ApiError(
            502, "crm_unavailable", "Не удалось проверить сделку в Битриксе. Попробуйте позже"
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ApiError(
            502, "crm_unavailable", "Не удалось проверить сделку в Битриксе. Попробуйте позже"
        ) from exc


async def _stage_names() -> dict[str, str]:
    try:
        return await CRMClient().get_deal_stage_labels()
    except (httpx.HTTPError, ValueError):
        return {}


@router.get("/search")
async def search_clients(
    _: ApiAdmin,
    q: Annotated[str, Query(min_length=3, max_length=200)],
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
):
    query = " ".join(q.split())
    if len(query) < 3:
        raise ApiError(400, "query_too_short", "Введите не менее трёх символов ФИО")
    try:
        data = await CRMClient().search_existing_clients(query, page)
        rows = []
        for row in data["rows"]:
            kind, entity_id = row["kind"], str(row["id"])
            rows.append(
                {
                    "kind": kind,
                    "id": entity_id,
                    "title": str(row.get("title") or ""),
                    "full_name": str(row.get("full_name") or ""),
                    "phone": row.get("phone"),
                    "category_id": row.get("category_id"),
                    "category_label": str(row.get("category_label") or ""),
                    "stage_code": str(row.get("stage_code") or ""),
                    "stage_label": str(row.get("stage_label") or "Название этапа недоступно")
                    if row.get("stage_label") != row.get("stage_code")
                    else "Название этапа недоступно",
                    "url": entity_link(kind, entity_id),
                }
            )
        return {"rows": rows, "page": page, "has_more": bool(data.get("has_more"))}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 422}:
            raise ApiError(
                400, "invalid_search_query", "Введите ФИО буквами: фамилию, имя или отчество"
            ) from exc
        raise ApiError(
            502, "crm_search_unavailable", "Не удалось выполнить поиск в Битриксе. Попробуйте позже"
        ) from exc
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ApiError(
            502, "crm_search_unavailable", "Не удалось выполнить поиск в Битриксе. Попробуйте позже"
        ) from exc


@router.get("/deals/preview")
async def preview_deal(_: ApiAdmin, deal: Annotated[str, Query(min_length=1, max_length=1000)]):
    try:
        deal_id = parse_deal_reference(deal)
    except ValueError as exc:
        raise ApiError(400, "invalid_deal_link", str(exc)) from exc
    return await deal_snapshot(_, deal_id)


@router.get("/deals/{deal_id}")
async def deal_snapshot(_: ApiAdmin, deal_id: DealId):
    data = await _snapshot(deal_id)
    return {
        key: data.get(key)
        for key in (
            "deal_id",
            "full_name",
            "phone",
            "stage_code",
            "category_id",
            "first_payment",
            "paid_in_full",
        )
    } | {
        "stage_label": data.get("stage_label") or "Название этапа недоступно",
        "deal_url": entity_link("deal", deal_id),
    }


@router.get("", response_model=ClientsList)
async def clients(
    _: ApiAdmin,
    session: Session,
    q: str = "",
    page: int = 1,
    agent_id: Annotated[int | None, Query(gt=0)] = None,
):
    query = _query()
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                ReferralApplication.full_name.ilike(pattern),
                ReferralApplication.phone_normalized.ilike(pattern),
                Agent.display_name.ilike(pattern),
                Agent.email.ilike(pattern),
                ExistingClientImport.deal_id.ilike(pattern),
            )
        )
    if agent_id is not None:
        query = query.where(Agent.id == agent_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    pages = max(1, (total + 11) // 12)
    page = min(max(page, 1), pages)
    rows = (
        await session.execute(
            query.order_by(
                ExistingClientImport.created_at.desc(), ExistingClientImport.application_id.desc()
            )
            .offset((page - 1) * 12)
            .limit(12)
        )
    ).all()
    names = await _stage_names() if rows else {}
    return ClientsList(
        rows=[_row(*row, stage_names=names) for row in rows],
        page=page,
        total_pages=pages,
        total_count=total,
    )


@router.post("", response_model=ClientOut, status_code=201, dependencies=[CsrfProtected])
async def import_client(admin: ApiAdmin, session: Session, body: ImportRequest):
    snapshot = await _snapshot(body.deal_id)
    try:
        record = await import_existing_client(
            session,
            admin_id=admin.id,
            snapshot=snapshot,
            agent_id=body.agent_id,
            full_name=body.full_name,
            phone=body.phone,
            admin_note=body.admin_note,
            current_amount=body.current_amount,
        )
    except ExistingClientConflict as exc:
        raise ApiError(409, "client_conflict", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, "invalid_client", str(exc)) from exc
    row = (
        await session.execute(
            _query().where(ExistingClientImport.application_id == record.application_id)
        )
    ).one()
    return _row(
        *row,
        stage_names={
            snapshot["stage_code"]: snapshot.get("stage_label") or "Название этапа недоступно"
        },
    )
