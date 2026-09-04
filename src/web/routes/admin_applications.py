from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token
from src.services.admin_applications import DELIVERY_STATUS_LABELS, list_applications
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
    return templates.TemplateResponse(
        request=request,
        name="admin_applications.html",
        context={
            "q": q,
            "status": status,
            "status_options": DELIVERY_STATUS_LABELS,
            "page_result": result,
            "csrf_token": csrf_token(request.session),
        },
    )
