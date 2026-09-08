from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import ProcessingStatus
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token, valid_csrf
from src.services.admin_applications import (
    DELIVERY_STATUS_LABELS,
    PROCESSING_STATUS_LABELS,
    assign_manager,
    list_applications,
    list_managers,
    set_processing_status,
)
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin/applications", tags=["admin applications"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_class=HTMLResponse)
async def applications_page(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    q: str = "",
    status: str = "",
    page: int = 1,
):
    result = await list_applications(session, q, status, page)
    managers = await list_managers(session)
    return templates.TemplateResponse(
        request=request,
        name="admin_applications.html",
        context={
            "q": q,
            "status": status,
            "status_options": DELIVERY_STATUS_LABELS,
            "processing_status_options": PROCESSING_STATUS_LABELS,
            "managers": managers,
            "page_result": result,
            "csrf_token": csrf_token(request.session),
        },
    )


@router.post("/{application_id}/status")
async def applications_set_status(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    application_id: int,
    processing_status: Annotated[str, Form()],
    q: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "",
    page: Annotated[int, Form()] = 1,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        try:
            new_status = ProcessingStatus(processing_status)
        except ValueError:
            new_status = None
        if new_status is not None:
            await set_processing_status(session, application_id, new_status)
    return RedirectResponse(
        f"/admin/applications?{urlencode({'q': q, 'status': status, 'page': page})}",
        status_code=303,
    )


@router.post("/{application_id}/manager")
async def applications_set_manager(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    application_id: int,
    manager_id: Annotated[str, Form()] = "",
    q: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "",
    page: Annotated[int, Form()] = 1,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        parsed_manager_id = int(manager_id) if manager_id.strip().isdigit() else None
        await assign_manager(session, application_id, parsed_manager_id)
    return RedirectResponse(
        f"/admin/applications?{urlencode({'q': q, 'status': status, 'page': page})}",
        status_code=303,
    )
