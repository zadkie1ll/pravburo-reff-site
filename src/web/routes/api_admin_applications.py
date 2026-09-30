"""Admin: all applications from partners, their delivery to Bitrix and processing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import DeliveryStatus, ProcessingStatus, ReferralApplication
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin_applications import (
    DELIVERY_STATUS_LABELS,
    PROCESSING_STATUS_LABELS,
    ApplicationRow,
    assign_manager,
    list_applications,
    list_managers,
    set_processing_status,
)
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.api_schemas import OkResponse, OptionOut

router = APIRouter(prefix="/api/v1/site/admin/applications", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ManagerOut(BaseModel):
    id: int
    label: str


class ApplicationOut(BaseModel):
    id: int
    client_name: str
    phone: str
    agent_name: str
    agent_email: str | None
    city: str | None
    debt_amount: str | None
    delivery_label: str
    delivery_error: str | None
    processing_status: ProcessingStatus
    assigned_manager_id: int | None
    created_at_label: str


class ApplicationsResponse(BaseModel):
    rows: list[ApplicationOut]
    page: int
    total_pages: int
    total_count: int
    delivery_statuses: list[OptionOut]
    processing_statuses: list[OptionOut]
    managers: list[ManagerOut]


class ProcessingStatusRequest(BaseModel):
    processing_status: ProcessingStatus


class ManagerRequest(BaseModel):
    manager_id: int | None


def _row(row: ApplicationRow) -> ApplicationOut:
    application = row.application
    return ApplicationOut(
        id=application.id,
        client_name=application.full_name,
        phone=application.phone_normalized,
        agent_name=row.agent_name,
        agent_email=row.agent_email,
        city=application.city,
        debt_amount=application.debt_amount,
        delivery_label=DELIVERY_STATUS_LABELS.get(
            application.delivery_status, application.delivery_status.value
        ),
        delivery_error=application.delivery_error,
        processing_status=application.processing_status,
        assigned_manager_id=application.assigned_manager_id,
        created_at_label=application.created_at.strftime("%d.%m.%Y %H:%M"),
    )


async def _existing_application(session: AsyncSession, application_id: int) -> None:
    if await session.get(ReferralApplication, application_id) is None:
        raise ApiError(404, "not_found", "Заявка не найдена")


@router.get("", response_model=ApplicationsResponse)
async def applications(
    _: ApiAdmin,
    session: Session,
    q: Annotated[str, Query()] = "",
    status: Annotated[DeliveryStatus | None, Query()] = None,
    page: Annotated[int, Query()] = 1,
) -> ApplicationsResponse:
    result = await list_applications(session, q, status.value if status else "", page)
    managers = await list_managers(session)
    return ApplicationsResponse(
        rows=[_row(row) for row in result.rows],
        page=result.page,
        total_pages=result.total_pages,
        total_count=result.total_count,
        delivery_statuses=[
            OptionOut(value=value.value, label=label)
            for value, label in DELIVERY_STATUS_LABELS.items()
        ],
        processing_statuses=[
            OptionOut(value=value.value, label=label)
            for value, label in PROCESSING_STATUS_LABELS.items()
        ],
        managers=[ManagerOut(id=manager.id, label=manager.label) for manager in managers],
    )


@router.post("/{application_id}/status", response_model=OkResponse, dependencies=[CsrfProtected])
async def set_status(
    _: ApiAdmin, session: Session, application_id: int, body: ProcessingStatusRequest
) -> OkResponse:
    await _existing_application(session, application_id)
    await set_processing_status(session, application_id, body.processing_status)
    return OkResponse()


@router.post("/{application_id}/manager", response_model=OkResponse, dependencies=[CsrfProtected])
async def set_manager(
    _: ApiAdmin, session: Session, application_id: int, body: ManagerRequest
) -> OkResponse:
    await _existing_application(session, application_id)
    if body.manager_id is not None:
        managers = await list_managers(session)
        if body.manager_id not in {manager.id for manager in managers}:
            raise ApiError(400, "invalid_manager", "Менеджером может быть только администратор")
    await assign_manager(session, application_id, body.manager_id)
    return OkResponse()
