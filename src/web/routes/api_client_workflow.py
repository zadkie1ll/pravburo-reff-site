"""Admin settlement UI API. No external CRM mutations and no historical accrual replay."""

from datetime import UTC, date, datetime, time
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import (
    ExistingClientImport,
    ReferralApplication,
    Reward,
    RewardStatus,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.client_workflow import (
    WorkflowConflict,
    WorkflowInput,
    save_workflow,
    workflow_defaults,
    workflow_view,
)
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.routes.api_admin_payouts import _tell_partner

router = APIRouter(prefix="/api/v1/site/admin/client-workflows", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/defaults")
async def defaults(
    _: ApiAdmin, session: Session, agent_id: Annotated[int, Query(gt=0)], contract_date: date
):
    try:
        return await workflow_defaults(session, agent_id, contract_date)
    except ValueError as exc:
        raise ApiError(400, "invalid_defaults", str(exc)) from exc


async def load(session: AsyncSession, application_id: int, lock=False):
    record = await session.get(ExistingClientImport, application_id, with_for_update=lock)
    if record is None:
        raise ApiError(404, "not_found", "Клиент не найден")
    return record


@router.get("/{application_id}")
async def get_workflow(_: ApiAdmin, session: Session, application_id: int):
    record = await load(session, application_id)
    application = await session.get(ReferralApplication, application_id)
    return dict(
        id=application_id,
        full_name=application.full_name,
        agent_id=application.agent_id,
        workflow=await workflow_view(session, record),
    )


@router.post("/{application_id}", dependencies=[CsrfProtected])
async def update_workflow(
    admin: ApiAdmin, session: Session, application_id: int, body: WorkflowInput
):
    record = await load(session, application_id, True)
    try:
        await save_workflow(session, record, body, admin.id)
        await session.commit()
    except WorkflowConflict as exc:
        raise ApiError(409, "workflow_conflict", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(400, "invalid_workflow", str(exc)) from exc
    return await workflow_view(session, record)


class PayRequest(BaseModel):
    version: int = Field(ge=1)
    paid_on: date


@router.post("/{application_id}/{kind}/pay", dependencies=[CsrfProtected])
async def pay_stage(
    admin: ApiAdmin,
    session: Session,
    application_id: int,
    kind: Literal["advance", "main", "bonus", "curator"],
    body: PayRequest,
):
    record = await load(session, application_id, True)
    data = record.workflow_data
    if not data or data["version"] != body.version:
        raise ApiError(409, "workflow_conflict", "Данные изменились. Обновите страницу")
    if not data["input"].get("contract_date"):
        raise ApiError(409, "contract_required", "Сначала укажите дату подписанного договора")
    contract = date.fromisoformat(data["input"]["contract_date"])
    if not contract <= body.paid_on <= datetime.now(ZoneInfo("Europe/Moscow")).date():
        raise ApiError(
            400, "invalid_date", "Укажите дату выплаты между датой договора и сегодняшним днём"
        )
    keys = [kind, "bonus"] if kind == "main" else [kind]
    paid = []
    for key in keys:
        reward_id = data["reward_ids"].get(key)
        if reward_id is None:
            continue
        reward = await session.get(Reward, reward_id, with_for_update=True, populate_existing=True)
        if reward is not None and reward.paid_at is not None and kind == "main":
            continue
        if reward is None or reward.status != RewardStatus.APPROVED or reward.paid_at is not None:
            raise ApiError(
                409, "not_payable", "Начисление уже выплачено или недоступно для выплаты"
            )
        reward.paid_at = datetime.combine(
            body.paid_on, time(12), ZoneInfo("Europe/Moscow")
        ).astimezone(UTC)
        paid.append(reward)
    if not paid:
        raise ApiError(409, "not_payable", "Нет доступных начислений для выплаты")
    record.workflow_data = {**data, "version": data["version"] + 1}
    await session.commit()
    for reward in paid:
        await _tell_partner(session, reward)
    return await workflow_view(session, record)
